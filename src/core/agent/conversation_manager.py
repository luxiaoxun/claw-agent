from typing import List, Optional, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage

from core.agent.progressive_agent import ProgressiveAgent
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class ConversationManager:
    """
    对话管理器
    负责会话管理和与Progressive Agent的交互
    """

    def __init__(self):
        self.progressive_agent: Optional[ProgressiveAgent] = None
        self.conversation_history: List[BaseMessage] = []
        self.pending_confirmation: Optional[Dict[str, Any]] = None
        self.pending_operation_message: Optional[str] = None  # 待确认的原始消息

    async def initialize(self):
        """初始化对话管理器"""
        try:
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
            raise RuntimeError("Agent尚未初始化")

        logger.info(f"处理用户消息: {message}")

        # 检查是否有待确认的操作
        if self.pending_confirmation:
            return await self._handle_confirmation(message)

        try:
            # 调用 Agent 处理消息
            result = await self.progressive_agent.process(
                message,
                chat_history=self.conversation_history[
                             -settings.MAX_HISTORY_LENGTH:] if self.conversation_history else None
            )

            # 检查是否需要用户确认
            if self._has_high_risk_tool_calls(result):
                tool_calls = self._get_high_risk_tool_calls(result)
                self.pending_confirmation = {
                    "tool_calls": tool_calls,
                    "result": result
                }
                self.pending_operation_message = message

                # 返回确认提示
                return self._build_confirmation_prompt(tool_calls)

            # 提取响应文本并更新历史
            response_text = self._extract_response_text(result)
            self._update_history(message, response_text, result.get("messages", []))

            return response_text

        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}", exc_info=True)
            return f"处理消息时出错: {str(e)}"

    async def _handle_confirmation(self, message: str) -> str:
        """处理用户确认/取消"""
        message_lower = message.lower().strip()

        if message_lower in ["确认", "confirm", "yes", "是"]:
            # 用户确认执行
            logger.info("用户确认执行高风险操作")

            # 获取待确认的操作
            pending = self.pending_confirmation
            self.pending_confirmation = None

            # 重新执行原始消息（Agent 会自动执行工具）
            if self.pending_operation_message:
                original_message = self.pending_operation_message
                self.pending_operation_message = None

                # 重新执行
                result = await self.progressive_agent.process(
                    original_message,
                    chat_history=self.conversation_history[
                                 -settings.MAX_HISTORY_LENGTH:] if self.conversation_history else None
                )

                response_text = self._extract_response_text(result)
                self._update_history(original_message, response_text, result.get("messages", []))

                return f"操作已确认执行\n\n{response_text}"
            else:
                return "无法重新执行操作，请重新描述您的需求"

        elif message_lower in ["取消", "cancel", "no", "否"]:
            # 用户取消操作
            tool_names = [tc.get('name', 'unknown') for tc in self.pending_confirmation.get("tool_calls", [])]
            logger.info(f"用户取消了高风险操作: {', '.join(tool_names)}")

            cancel_message = f"操作已取消（涉及工具: {', '.join(tool_names)}）"

            # 记录取消到历史
            self.conversation_history.append(AIMessage(content=cancel_message))

            self.pending_confirmation = None
            self.pending_operation_message = None

            return f"{cancel_message}"

        else:
            # 无效输入，重新提示
            tool_calls = self.pending_confirmation.get("tool_calls", [])
            return self._build_confirmation_prompt(tool_calls)

    def _has_high_risk_tool_calls(self, result: Dict[str, Any]) -> bool:
        """检查是否有高风险工具调用"""
        tool_calls = self.progressive_agent.get_tool_calls_from_result(result)

        for tc in tool_calls:
            if tc.get("type") == "request" and tc.get("name") in settings.HIGH_RISK_TOOLS:
                return True

        return False

    def _get_high_risk_tool_calls(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取所有高风险工具调用"""
        high_risk_calls = []
        tool_calls = self.progressive_agent.get_tool_calls_from_result(result)

        for tc in tool_calls:
            if tc.get("type") == "request" and tc.get("name") in settings.HIGH_RISK_TOOLS:
                high_risk_calls.append(tc)

        return high_risk_calls

    def _build_confirmation_prompt(self, tool_calls: List[Dict[str, Any]]) -> str:
        """构建确认提示信息"""
        if not tool_calls:
            return "未检测到需要确认的操作"

        prompt = "**高风险操作确认**\n\n"
        prompt += "您即将执行以下高风险操作：\n\n"

        for i, tc in enumerate(tool_calls, 1):
            tool_name = tc.get("name", "unknown")
            args = tc.get("args", {})

            prompt += f"{i}. **工具**: `{tool_name}`\n"
            if args:
                prompt += f"   **参数**: {self._format_args_for_display(args)}\n"
            prompt += "\n"

        prompt += "请回复 **确认** 以继续执行，或 **取消** 以中止操作。"

        return prompt

    def _format_args_for_display(self, args: Dict[str, Any]) -> str:
        """格式化参数用于显示"""
        if not args:
            return "无"

        # 只显示关键参数，避免过长
        important_keys = ['indexName', 'query', 'path', 'skill_name', 'timeType', 'pageNum']
        formatted = []

        for key in important_keys:
            if key in args:
                value = str(args[key])
                if len(value) > 50:
                    value = value[:50] + "..."
                formatted.append(f"{key}={value}")

        if formatted:
            return ", ".join(formatted)

        # 如果没有关键参数，显示所有参数（截断）
        args_str = str(args)
        if len(args_str) > 100:
            args_str = args_str[:100] + "..."
        return args_str

    def _extract_response_text(self, result: Dict[str, Any]) -> str:
        """从结果中提取最终的响应文本"""
        messages = result.get("messages", [])

        # 从后往前找最后一条 AI 消息
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                return msg.content

        return "无法获取响应内容"

    def _update_history(self, user_message: str, assistant_response: str, messages: List[BaseMessage]):
        """更新对话历史"""
        # 添加用户消息
        self.conversation_history.append(HumanMessage(content=user_message))

        # 添加完整的消息链（保留工具调用等中间信息）
        # 但为了避免历史过长，只保留关键的 AI 响应
        for msg in messages:
            if isinstance(msg, AIMessage):
                # 如果有工具调用，保留完整消息
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    self.conversation_history.append(msg)
                else:
                    # 简单响应，已经通过 assistant_response 添加，避免重复
                    pass
            elif isinstance(msg, ToolMessage):
                # 保留工具执行结果供上下文使用
                self.conversation_history.append(msg)

        # 确保有最终的 AI 响应
        if not any(
                isinstance(msg, AIMessage) and msg.content == assistant_response for msg in self.conversation_history):
            self.conversation_history.append(AIMessage(content=assistant_response))

        # 限制历史记录长度（保留最近 N 轮对话）
        max_history = getattr(settings, 'MAX_HISTORY_LENGTH', 50)
        if len(self.conversation_history) > max_history * 2:
            self.conversation_history = self.conversation_history[-max_history * 2:]

    def reset_history(self):
        """重置对话历史"""
        self.conversation_history = []
        self.pending_confirmation = None
        self.pending_operation_message = None
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

    def get_conversation_summary(self) -> Dict[str, Any]:
        """获取对话摘要信息"""
        return {
            "total_messages": len(self.conversation_history),
            "has_pending_confirmation": self.pending_confirmation is not None,
            "pending_tools": [tc.get('name') for tc in
                              self.pending_confirmation.get("tool_calls", [])] if self.pending_confirmation else [],
            "agent_mode": self.get_agent_mode()
        }
