from typing import List, Optional
from mcp import ClientSession
from mcp.client.sse import sse_client

from core.tool.mcp.mcp_adapter import MCPToolAdapter
from core.tool.base.base_elasticsearch_tool import BaseElasticsearchTool
from config.logging_config import get_logger

logger = get_logger(__name__)


class MCPClientManager:
    """管理MCP客户端连接和工具"""

    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session: Optional[ClientSession] = None
        self.tools: List[BaseElasticsearchTool] = []
        self._client_context = None
        self._session_context = None

    async def initialize(self) -> List[BaseElasticsearchTool]:
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
                    langchain_tool = MCPToolAdapter(self.session, mcp_tool)
                    self.tools.append(langchain_tool)
                    logger.debug(f"成功创建工具: {mcp_tool.name}")
                except Exception as e:
                    logger.error(f"跳过工具 {mcp_tool.name}，创建失败: {e}")

            logger.info(f"成功加载 {len(self.tools)} 个MCP工具")
            return self.tools

        except Exception as e:
            logger.error(f"MCP初始化失败: {str(e)}")
            raise

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
