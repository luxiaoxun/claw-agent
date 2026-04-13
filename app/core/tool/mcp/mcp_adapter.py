from typing import Any, Optional, Type
from pydantic import BaseModel

from core.tool.base.base_elasticsearch_tool import BaseElasticsearchTool
from config.logging_config import get_logger

logger = get_logger(__name__)


class MCPToolAdapter(BaseElasticsearchTool):
    """将MCP工具适配为LangChain工具的适配器"""

    name: str = ""
    description: str = ""
    mcp_session: Any = None
    mcp_tool: Any = None
    args_schema: Optional[Type[BaseModel]] = None

    def __init__(self, mcp_session, mcp_tool):
        """初始化适配器"""
        super().__init__(
            name=mcp_tool.name,
            description=mcp_tool.description or f"MCP工具: {mcp_tool.name}",
            mcp_session=mcp_session,
            mcp_tool=mcp_tool
        )
        logger.debug(f"创建MCP工具适配器: {mcp_tool.name}")

    async def _arun(self, **kwargs) -> str:
        """异步执行MCP工具"""
        try:
            logger.info(f"调用MCP工具: {self.name}, 参数: {kwargs}")

            # 调用MCP工具
            result = await self.mcp_session.call_tool(
                self.mcp_tool.name,
                arguments=kwargs
            )

            # 处理返回结果
            if hasattr(result, 'content'):
                content_parts = []
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        content_parts.append(content_item.text)
                    elif hasattr(content_item, 'type'):
                        if content_item.type == 'text' and hasattr(content_item, 'text'):
                            content_parts.append(content_item.text)

                response = "\n".join(content_parts) if content_parts else str(result)
                logger.info(f"工具 {self.name} 调用成功")
                return response
            else:
                return str(result)

        except Exception as e:
            logger.error(f"调用MCP工具 {self.name} 时出错: {str(e)}")
            return f"调用MCP工具时出错: {str(e)}"
