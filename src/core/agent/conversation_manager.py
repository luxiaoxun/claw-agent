from typing import List, Optional, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from core.agent.progressive_agent import ProgressiveAgent
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class ConversationManager:
    """
    对话管理器
    负责会话管理和与ProgressiveAgent的交互
    """

    def __init__(self):
        self.progressive_agent: Optional[ProgressiveAgent] = None
        self.conversation_history: List[BaseMessage] = []
        self.pending_confirmation: Optional[Dict[str, Any]] = None

    async def initialize(self):
        """初始化对话管理器"""
        try:
            # 初始化渐进式Agent（内部处理MCP和LLM）
            self.progressive_agent = ProgressiveAgent(skills_dir="skills")
            await self.progressive_agent.initialize()

            logger.info(f"ConversationManager初始化完成，模式: {self.progressive_agent.get_mode()}")
            return self

        except Exception as e:
            logger.error(f"ConversationManager初始化失败: {str(e)}")
            raise

    async def process_message(self, message: str) -> str:
        """处理用户消息"""
        if not self.progressive_agent:
            raise RuntimeError("ProgressiveAgent尚未初始化")

        logger.info(f"处理用户消息: {message}")

        # 检查是否有待确认的操作
        if self.pending_confirmation:
            return await self._handle_confirmation(message)

        try:
            # 使用 ProgressiveAgent 处理消息
            result = await self.progressive_agent.process(
                message,
                chat_history=self.conversation_history[-settings.MAX_HISTORY_LENGTH:]
            )

            # 检查是否有高风险操作需要确认
            if self._needs_confirmation(result):
                self.pending_confirmation = {
                    "operation": self._extract_operation(result),
                    "original_response": result["output"]
                }
                return f"【需要确认】\n\n您即将执行高风险操作: {self.pending_confirmation['operation']}\n\n请回复 '确认' 以继续，或 '取消' 以中止。"

            # 更新对话历史
            self._update_history(message, result["output"])

            return result["output"]

        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}")
            return f"处理消息时出错: {str(e)}"

    async def _handle_confirmation(self, message: str) -> str:
        """处理用户确认"""
        message_lower = message.lower().strip()

        if message_lower in ["确认", "confirm", "yes", "是"]:
            self.pending_confirmation = None
            return "操作已确认执行，请稍候..."

        elif message_lower in ["取消", "cancel", "no", "否"]:
            self.pending_confirmation = None
            return "操作已取消"

        else:
            return f"请确认是否执行高风险操作: {self.pending_confirmation['operation']}\n\n回复 '确认' 或 '取消'"

    def _needs_confirmation(self, result: Dict[str, Any]) -> bool:
        """检查是否需要用户确认"""
        intermediate_steps = result.get("intermediate_steps", [])
        for step in intermediate_steps:
            if step and len(step) > 0:
                tool_name = getattr(step[0], 'tool', None)
                if tool_name and tool_name in settings.HIGH_RISK_TOOLS:
                    return True
        return False

    def _extract_operation(self, result: Dict[str, Any]) -> str:
        """提取高风险操作信息"""
        intermediate_steps = result.get("intermediate_steps", [])
        for step in intermediate_steps:
            if step and len(step) > 0:
                tool_name = getattr(step[0], 'tool', None)
                tool_input = getattr(step[0], 'tool_input', {})
                if tool_name and tool_name in settings.HIGH_RISK_TOOLS:
                    return f"{tool_name}({tool_input})"
        return "未知操作"

    def _update_history(self, message: str, response: str):
        """更新对话历史"""
        self.conversation_history.append(HumanMessage(content=message))
        self.conversation_history.append(AIMessage(content=response))

    def reset_history(self):
        """重置对话历史"""
        self.conversation_history = []
        self.pending_confirmation = None
        logger.info("对话历史已重置")

    async def close(self):
        """关闭连接"""
        if self.progressive_agent:
            await self.progressive_agent.close()

    async def __aenter__(self):
        return await self.initialize()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def get_tools_info(self) -> List[dict]:
        """获取工具信息"""
        if not self.progressive_agent:
            return []
        return self.progressive_agent.get_tools_info()

    def get_agent_mode(self) -> str:
        """获取当前Agent模式"""
        if not self.progressive_agent:
            return "uninitialized"
        return self.progressive_agent.get_mode()
