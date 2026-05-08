# core/agent/deep_agent.py
from typing import Dict, Any, List, Optional
from langchain.agents import create_agent
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain.chat_models import init_chat_model, BaseChatModel
from core.tool.mcp.mcp_client import MCPClientManager
from core.tool import file_read, file_write, file_edit, file_search, command_execute, doc_parser, search_data, \
    web_fetch, web_search
from core.agent.agent_prompt import AgentPrompt
from utils.message_handler import MessageHandler
from utils.token_usage import extract_token_usage_from_output
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class DeepAgent:
    """
    ReAct Agent
    """

    def __init__(self):
        # 基础工具
        self.base_tools = [file_read, file_write, file_edit, file_search, command_execute, doc_parser, web_fetch,
                           web_search, search_data]

        # MCP相关
        self.mcp_manager: Optional[MCPClientManager] = None
        self.mcp_tools: List = []
        self.use_mcp = settings.USE_MCP

        # Agent
        self.llm: Optional[BaseChatModel] = None
        self.agent = None
        self.system_prompt: Optional[str] = None

        # 提示词管理器
        self.prompt_manager = AgentPrompt()

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
            model_provider=settings.LLM_MODEL_PROVIDER,
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

        # 统计 LLM 调用的 token 消耗
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0

        for msg in result.get("messages", []):
            token_usage = extract_token_usage_from_output(msg)
            if token_usage:
                total_input_tokens += token_usage.get("input", 0) if token_usage else 0
                total_output_tokens += token_usage.get("output", 0) if token_usage else 0
                total_tokens += token_usage.get("total", 0) if token_usage else 0

        logger.info(
            f"本次请求 Token 总消耗 - Input: {total_input_tokens}, Output: {total_output_tokens}, Total: {total_tokens}"
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

        # 验证消息链
        logger.debug(f"消息链长度: {len(messages)}")
        for i, msg in enumerate(messages):
            logger.debug(f"消息 {i}: {type(msg).__name__} - {str(getattr(msg, 'content', ''))[:50]}")
            if isinstance(msg, ToolMessage):
                logger.debug(f"  ToolMessage: tool_call_id={msg.tool_call_id}, name={getattr(msg, 'name', 'N/A')}")

        try:
            logger.info("开始流式处理")

            # 统计 LLM 调用的 token 消耗
            total_input_tokens = 0
            total_output_tokens = 0
            total_tokens = 0

            # 收集完整的消息链
            collected_messages = []
            # 流式状态
            pending_content_parts = []
            pending_tool_calls = {}

            async for event in self.agent.astream_events(
                    {"messages": messages},
                    version="v2"
            ):
                event_type = event.get("event")

                # 工具调用开始
                if event_type == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_args = event.get("data", {}).get("input", {})
                    logger.info(f"工具调用开始: {tool_name}, {tool_args}")
                    yield {
                        "type": "tool_call",
                        "tool_name": tool_name,
                        "tool_args": tool_args
                    }

                # 工具调用结束
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = event.get("data", {}).get("output")
                    logger.info(f"工具调用结束: {tool_name}")

                    # 保存之前的 AIMessage
                    if pending_content_parts or pending_tool_calls:
                        ai_msg = MessageHandler.build_ai_message(pending_content_parts, pending_tool_calls)
                        if ai_msg:
                            collected_messages.append(ai_msg)
                        pending_content_parts = []
                        pending_tool_calls = {}

                    # 收集 ToolMessage
                    if tool_output and isinstance(tool_output, ToolMessage):
                        collected_messages.append(tool_output)

                    yield {
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "result": str(tool_output) if tool_output else "",
                        "status": "success",
                        "message": tool_output
                    }

                # 工具错误
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

                # LLM 流式输出
                elif event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk:
                        # 处理内容
                        if hasattr(chunk, "content") and chunk.content:
                            pending_content_parts.append(chunk.content)
                            yield {"type": "content", "content": chunk.content}

                        # 处理 tool_calls
                        if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                            for tc in chunk.tool_calls:
                                tc_id = tc.get('id', '')
                                if not tc_id or not tc.get('name'):
                                    continue

                                if tc_id not in pending_tool_calls:
                                    pending_tool_calls[tc_id] = {
                                        'name': tc.get('name'),
                                        'args': tc.get('args', {}),
                                        'id': tc_id
                                    }
                                else:
                                    # 合并参数
                                    pending_tool_calls[tc_id]['args'].update(tc.get('args', {}))

                # LLM 结束
                elif event_type == "on_chat_model_end":
                    # Extract token usage
                    event_data = event.get("data", {})
                    output = event_data.get("output")
                    token_usage = extract_token_usage_from_output(output)
                    if token_usage:
                        total_input_tokens += token_usage.get("input", 0) if token_usage else 0
                        total_output_tokens += token_usage.get("output", 0) if token_usage else 0
                        total_tokens += token_usage.get("total", 0) if token_usage else 0

                    if pending_content_parts or pending_tool_calls:
                        ai_msg = MessageHandler.build_ai_message(pending_content_parts, pending_tool_calls)
                        if ai_msg:
                            collected_messages.append(ai_msg)
                        pending_content_parts = []
                        pending_tool_calls = {}

            logger.info("流式处理完成")
            logger.info(f"收集到 {len(collected_messages)} 条消息: {[type(m).__name__ for m in collected_messages]}")
            logger.info(
                f"本次请求 Token 总消耗 - Input: {total_input_tokens}, Output: {total_output_tokens}, Total: {total_tokens}"
            )

            # 发送完成信号和消息链
            yield {
                "type": "complete",
                "full_response": "",
                "messages": collected_messages
            }

        except Exception as e:
            logger.error(f"流式处理失败: {str(e)}", exc_info=True)
            yield {"type": "error", "error": str(e)}

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
