# core/agent/deep_agent.py
import os
from typing import Dict, Any, List, Optional
from langchain.agents import create_agent
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain.chat_models import init_chat_model, BaseChatModel
from core.skill.skill_manager import SkillManager
from core.tool.mcp.mcp_client import MCPClientManager
from core.tool import file_read, file_write, file_edit, file_search, command_execute, doc_parser, search_data, \
    web_fetch, web_search
from core.agent.agent_prompt import AgentPrompt
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class DeepAgent:
    """
    ReAct Agent
    """

    def __init__(self, workspace_dir):
        self.skill_loader = SkillManager(os.path.join(workspace_dir, "skills"))
        self.skill_loader.load_all_skills()

        # 基础工具（始终可用）
        self.base_tools = [file_read, file_write, file_edit, file_search, command_execute, doc_parser, web_fetch,
                           web_search, search_data]

        # MCP相关
        self.mcp_manager: Optional[MCPClientManager] = None
        self.mcp_tools: List = []
        self.use_mcp = settings.USE_MCP

        # Agent
        self.llm: Optional[BaseChatModel] = None
        self.agent = None  # Runnable agent
        self.system_prompt: Optional[str] = None

        # 提示词管理器
        self.prompt_manager = AgentPrompt(self.skill_loader)

    async def initialize(self):
        """初始化Agent"""
        try:
            self._init_llm()

            if self.use_mcp:
                await self._load_mcp_tools()

            self._build_base_system_prompt()

            # 创建Agent
            all_tools = self.base_tools + self.mcp_tools
            self._create_agent(all_tools)

            logger.info(f"Agent初始化完成，工具数: {len(all_tools)}")
            return self

        except Exception as e:
            logger.error(f"Agent初始化失败: {str(e)}")
            raise

    def _init_llm(self):
        """初始化LLM"""
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY 未设置")

        self.llm = init_chat_model(
            model_provider="openai",
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )
        logger.info(f"LLM初始化成功: {settings.LLM_MODEL}")

    async def _load_mcp_tools(self):
        """加载MCP工具"""
        try:
            logger.info(f"正在连接到MCP服务器: {settings.MCP_SERVER_URL}")
            self.mcp_manager = MCPClientManager(settings.MCP_SERVER_URL)
            self.mcp_tools = await self.mcp_manager.initialize()
            logger.info(f"从MCP加载了 {len(self.mcp_tools)} 个工具")
        except Exception as e:
            logger.error(f"MCP连接失败: {str(e)}")
            self.use_mcp = False
            logger.warning("MCP连接失败，将仅使用本地工具")

    def _create_agent(self, tools: List):
        from langchain.agents.middleware import ToolRetryMiddleware

        self.agent = create_agent(
            model=self.llm,
            tools=tools,
            system_prompt=self.system_prompt,
            middleware=[
                ToolRetryMiddleware(max_retries=2),  # 工具调用失败时自动重试
            ]
        )
        logger.debug(f"Agent创建完成")

    def _build_base_system_prompt(self):
        """构建基础系统提示词"""
        self.system_prompt = self.prompt_manager.build_base_system_prompt()

    async def process(self, message: str, chat_history: Optional[List[BaseMessage]] = None) -> Dict[str, Any]:
        """
        处理用户消息（非流式）

        Returns:
            包含 messages 列表的字典
        """
        if not self.agent:
            raise RuntimeError("Agent未初始化")

        if chat_history is None:
            chat_history = []

        # 构建消息列表
        messages = chat_history + [HumanMessage(content=message)]

        # 调用 Agent
        result = await self.agent.ainvoke(
            {"messages": messages}
        )

        # 返回标准格式
        return {
            "messages": result.get("messages", []),
            "input_message": message
        }

    async def stream_process(self, message: str, chat_history: Optional[List[BaseMessage]] = None):
        """
        流式处理用户消息
        提供更细粒度的流式输出，包括工具调用和内容
        """
        if not self.agent:
            raise RuntimeError("Agent未初始化")

        if chat_history is None:
            chat_history = []

        messages = chat_history + [HumanMessage(content=message)]

        try:
            logger.info("开始流式处理")

            async for event in self.agent.astream_events(
                    {"messages": messages},
                    version="v2"
            ):
                event_type = event.get("event")

                # 处理工具调用开始
                if event_type == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_args = event.get("data", {}).get("input", {})
                    logger.info(f"工具调用开始: {tool_name}, {tool_args}")
                    yield {
                        "type": "tool_call",
                        "tool_name": tool_name,
                        "tool_args": tool_args
                    }

                # 处理工具调用结束
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = event.get("data", {}).get("output")
                    logger.info(f"工具调用结束: {tool_name}")
                    yield {
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "result": str(tool_output) if tool_output else "",
                        "status": "success",
                        "message": tool_output
                    }

                # 处理工具错误
                elif event_type == "on_tool_error":
                    tool_name = event.get("name", "unknown")
                    error = event.get("data", {}).get("error", "Unknown error")
                    logger.error(f"工具调用错误: {tool_name} - {error}")
                    yield {
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "result": str(error),
                        "status": "error"
                    }

                # 处理 LLM 流式输出（内容）- 始终输出，不受配置控制
                elif event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk:
                        content = None
                        if hasattr(chunk, "content") and chunk.content:
                            content = chunk.content
                        elif isinstance(chunk, dict) and "content" in chunk:
                            content = chunk["content"]
                        if content:
                            yield {
                                "type": "content",
                                "content": content
                            }

            logger.info("流式处理完成")

        except Exception as e:
            logger.error(f"流式处理失败: {str(e)}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e)
            }

    async def close(self):
        """关闭连接"""
        if self.mcp_manager:
            await self.mcp_manager.close()
            logger.info("MCP连接已关闭")

    def get_tools_info(self) -> List[dict]:
        """获取所有工具信息"""
        tools_info = []

        for tool in self.base_tools:
            tools_info.append({
                "name": getattr(tool, 'name', str(tool)),
                "description": getattr(tool, 'description', 'No description'),
                "type": "base_tool"
            })

        for tool in self.mcp_tools:
            tools_info.append({
                "name": getattr(tool, 'name', str(tool)),
                "description": getattr(tool, 'description', 'No description'),
                "type": "mcp_tool"
            })

        return tools_info
