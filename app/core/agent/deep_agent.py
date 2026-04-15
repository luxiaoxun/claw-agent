import os
from typing import Dict, Any, List, Optional
from langchain.agents import create_agent
from langchain_core.messages import BaseMessage, HumanMessage
from langchain.chat_models import init_chat_model, BaseChatModel
from core.skill.skill_loader import SkillLoader
from core.tool.mcp.mcp_client import MCPClientManager
from core.tool import file_read, file_write, command_execute, search_data, web_fetch
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class DeepAgent:
    """
    ReAct Agent
    """

    def __init__(self, workspace_dir):
        self.skill_loader = SkillLoader(os.path.join(workspace_dir, "skills"))
        self.skill_loader.load_all_skills()

        # 基础工具（始终可用）
        self.base_tools = [file_read, file_write, command_execute, web_fetch, search_data]

        # MCP相关
        self.mcp_manager: Optional[MCPClientManager] = None
        self.mcp_tools: List = []
        self.use_mcp = settings.USE_MCP

        # Agent
        self.llm: Optional[BaseChatModel] = None
        self.agent = None  # Runnable agent
        self.system_prompt: Optional[str] = None

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
        all_skills = self.skill_loader.get_all_skill_descriptions()

        prompt = f"""你是一个智能助手，能够处理各种数据查询和分析任务。

    ## 工作流程

    **重要：你需要按照以下步骤工作：**

    ### 第一步：选择技能
    分析用户的问题，判断应该使用哪个技能来处理。你需要从下面的技能列表中选择最合适的技能。如果找不到合适的技能或工具，就基于内置知识和对用户提供内容的理解进行回答，不可以随便瞎编答案。

    ### 第二步：加载技能
    使用 `file_read` 工具读取选中技能的 SKILL.md 文件。
    - 格式: `{{"path": "SKILL.md", "skill_name": "技能名称"}}`

    ### 第三步：执行任务
    技能文件会告诉你：
    - 这个技能的具体作用
    - 如何使用（是否需要调用工具）
    - 返回结果的格式要求

    ### 第四步：返回结果
    严格按照技能文件中定义的输出格式返回结果。

    ## 注意事项
    - **必须**先加载技能文件，再执行任务
    - 技能文件中的指令优先级最高
    - 严格按照技能文件要求的格式返回结果

    ## 可用技能列表

    以下是所有可用的技能，每个技能都有特定的用途：

    """
        for skill in all_skills:
            prompt += f"- **{skill['name']}**: {skill['description']}\n"

        self.system_prompt = prompt

    async def process(self, message: str, chat_history: Optional[List[BaseMessage]] = None) -> Dict[str, Any]:
        """
        处理用户消息（非流式）

        Returns:
            包含 messages 列表的字典，符合 LangChain 1.0 标准
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
                    tool_input = event.get("data", {}).get("input", {})
                    logger.info(f"工具调用开始: {tool_name}")

                    # 根据配置决定是否输出工具调用信息
                    if settings.MSG_TOOL_OUTPUT_ENABLED:
                        yield {
                            "type": "tool_call",
                            "tool_name": tool_name,
                            "tool_args": tool_input
                        }

                # 处理工具调用结束
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = event.get("data", {}).get("output")
                    logger.info(f"工具调用结束: {tool_name}")

                    # 根据配置决定是否输出工具结果信息
                    if settings.MSG_TOOL_OUTPUT_ENABLED:
                        yield {
                            "type": "tool_result",
                            "tool_name": tool_name,
                            "result": str(tool_output) if tool_output else "无输出",
                            "status": "success"
                        }

                # 处理工具错误
                elif event_type == "on_tool_error":
                    tool_name = event.get("name", "unknown")
                    error = event.get("data", {}).get("error", "未知错误")
                    logger.error(f"工具调用错误: {tool_name} - {error}")

                    # 根据配置决定是否输出工具错误信息
                    if settings.MSG_TOOL_OUTPUT_ENABLED:
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
                        # 获取内容
                        content = None
                        if hasattr(chunk, "content") and chunk.content:
                            content = chunk.content
                        elif isinstance(chunk, dict) and "content" in chunk:
                            content = chunk["content"]

                        if content:
                            logger.debug(f"LLM 输出块: {content[:50]}...")
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
