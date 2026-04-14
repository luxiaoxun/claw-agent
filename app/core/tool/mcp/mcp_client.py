from typing import List, Optional, Dict, Any
from mcp import ClientSession
from mcp.client.sse import sse_client
from langchain_core.tools import StructuredTool, BaseTool
from pydantic import create_model
from config.logging_config import get_logger

logger = get_logger(__name__)


class MCPClientManager:
    """管理MCP客户端连接和工具"""

    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session: Optional[ClientSession] = None
        self.tools: List[BaseTool] = []
        self._client_context = None
        self._session_context = None

    async def initialize(self) -> List[BaseTool]:
        """初始化MCP连接并返回工具列表"""
        logger.info(f"正在连接到MCP服务器: {self.server_url}")

        try:
            # 创建SSE客户端连接
            self._client_context = sse_client(self.server_url)
            read, write = await self._client_context.__aenter__()
            logger.debug("SSE连接建立成功")

            # 创建会话
            self._session_context = ClientSession(read, write)
            self.session = await self._session_context.__aenter__()
            logger.debug("MCP会话创建成功")

            # 初始化会话
            await self.session.initialize()
            logger.debug("会话初始化成功")

            # 获取工具列表
            tools_result = await self.session.list_tools()
            logger.info(f"从MCP服务器获取到 {len(tools_result.tools)} 个工具")

            # 转换为LangChain工具
            for mcp_tool in tools_result.tools:
                try:
                    langchain_tool = await self._create_langchain_tool(mcp_tool)
                    self.tools.append(langchain_tool)
                    logger.debug(f"成功创建工具: {mcp_tool.name}")
                except Exception as e:
                    logger.error(f"跳过工具 {mcp_tool.name}，创建失败: {e}")

            logger.info(f"成功加载 {len(self.tools)} 个MCP工具")
            return self.tools

        except Exception as e:
            logger.error(f"MCP初始化失败: {str(e)}")
            raise

    async def _create_langchain_tool(self, mcp_tool) -> BaseTool:
        """将MCP工具转换为LangChain工具"""
        # 动态创建参数模型
        args_schema = self._create_args_schema(mcp_tool)

        # 创建异步调用函数
        async def call_mcp_tool(**kwargs) -> str:
            """调用MCP工具的实际函数"""
            try:
                logger.info(f"调用MCP工具: {mcp_tool.name}, 参数: {kwargs}")

                # 调用MCP工具
                result = await self.session.call_tool(
                    mcp_tool.name,
                    arguments=kwargs
                )

                # 处理返回结果
                return self._format_tool_result(result)

            except Exception as e:
                error_msg = f"调用MCP工具 {mcp_tool.name} 时出错: {str(e)}"
                logger.error(error_msg)
                return error_msg

        # 使用StructuredTool创建工具
        return StructuredTool.from_function(
            coroutine=call_mcp_tool,
            name=mcp_tool.name,
            description=mcp_tool.description or f"MCP工具: {mcp_tool.name}",
            args_schema=args_schema,
        )

    def _create_args_schema(self, mcp_tool) -> Optional[Any]:
        """根据MCP工具的inputSchema动态创建参数模型"""
        if not mcp_tool.inputSchema or 'properties' not in mcp_tool.inputSchema:
            return None

        properties = mcp_tool.inputSchema.get('properties', {})
        required = mcp_tool.inputSchema.get('required', [])

        if not properties:
            return None

        fields = {}
        for prop_name, prop_info in properties.items():
            prop_type = prop_info.get('type', 'string')
            description = prop_info.get('description', '')
            is_required = prop_name in required

            # 映射JSON类型到Python类型
            field_type = self._map_json_type_to_python(prop_type)

            # 处理枚举值
            if 'enum' in prop_info:
                from enum import Enum
                enum_values = prop_info['enum']
                enum_name = f"{mcp_tool.name}_{prop_name}_enum"
                field_type = Enum(enum_name, {str(v): v for v in enum_values})

            # 添加字段
            if is_required:
                fields[prop_name] = (field_type, ...)
            else:
                from typing import Optional
                fields[prop_name] = (Optional[field_type], None)

        # 动态创建Pydantic模型
        if fields:
            return create_model(f"{mcp_tool.name}_args", **fields)

        return None

    def _map_json_type_to_python(self, json_type: str) -> type:
        """将JSON类型映射为Python类型"""
        type_mapping = {
            'string': str,
            'integer': int,
            'number': float,
            'boolean': bool,
            'array': list,
            'object': dict,
        }
        return type_mapping.get(json_type, str)

    def _format_tool_result(self, result) -> str:
        """格式化MCP工具返回结果"""
        try:
            # 处理MCP的标准返回格式
            if hasattr(result, 'content'):
                content_parts = []
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        content_parts.append(content_item.text)
                    elif hasattr(content_item, 'type'):
                        if content_item.type == 'text' and hasattr(content_item, 'text'):
                            content_parts.append(content_item.text)
                        elif content_item.type == 'image' and hasattr(content_item, 'data'):
                            # 如果是图片，返回数据URI或描述
                            content_parts.append(f"[图片数据: {len(content_item.data)} bytes]")
                        elif content_item.type == 'resource' and hasattr(content_item, 'resource'):
                            content_parts.append(f"[资源: {content_item.resource}]")

                if content_parts:
                    return "\n".join(content_parts)

            # 处理其他格式的返回
            if hasattr(result, 'text'):
                return result.text

            if hasattr(result, 'data'):
                return str(result.data)

            # 默认返回字符串表示
            return str(result)

        except Exception as e:
            logger.warning(f"格式化工具结果时出错: {e}")
            return str(result)

    async def close(self):
        """关闭MCP连接"""
        logger.info("关闭MCP连接...")
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._client_context:
            await self._client_context.__aexit__(None, None, None)
        logger.info("MCP连接已关闭")

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
