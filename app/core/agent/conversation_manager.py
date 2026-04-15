from typing import List, Optional, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage

from core.agent.deep_agent import DeepAgent
from config.settings import settings, WORKSPACE_DIR
from config.logging_config import get_logger

logger = get_logger(__name__)


class ConversationManager:
    """
    对话管理器
    负责会话管理和与Deep Agent的交互
    """

    def __init__(self):
        self.deep_agent: Optional[DeepAgent] = None
        self.conversation_history: List[BaseMessage] = []

        # 流式处理相关
        self._current_stream_response = ""
        self._streaming_tool_calls = []

    async def initialize(self):
        """初始化对话管理器"""
        try:
            import os
            self.deep_agent = DeepAgent(WORKSPACE_DIR)
            await self.deep_agent.initialize()
            logger.info(f"ConversationManager初始化完成")
            return self
        except Exception as e:
            logger.error(f"ConversationManager初始化失败: {str(e)}")
            raise

    async def process_message(self, message: str) -> str:
        """处理用户消息（非流式）"""
        if not self.deep_agent:
            raise RuntimeError("Agent尚未初始化")

        logger.info(f"处理用户消息: {message}")

        try:
            # 调用 Agent 处理消息
            result = await self.deep_agent.process(
                message,
                chat_history=self.conversation_history[
                             -settings.MSG_MAX_HISTORY_LENGTH:] if self.conversation_history else None
            )

            # 提取响应文本并更新历史
            response_text = self._extract_response_text(result)
            self._update_history(message, response_text, result.get("messages", []))

            return response_text

        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}", exc_info=True)
            return f"处理消息时出错: {str(e)}"

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
        for msg in messages:
            if isinstance(msg, AIMessage):
                # 如果有工具调用，保留完整消息
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    self.conversation_history.append(msg)
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

    async def process_message_stream(self, message: str):
        """
        流式处理用户消息
        Yields: 流式响应块
        """
        if not self.deep_agent:
            raise RuntimeError("Agent尚未初始化")

        logger.info(f"流式处理用户消息: {message}")

        try:
            # 重置流式状态
            self._current_stream_response = ""
            self._streaming_tool_calls = []

            chunk_count = 0
            # 调用 Agent 的流式处理
            async for chunk in self.deep_agent.stream_process(
                    message,
                    chat_history=self.conversation_history[
                                 -settings.MSG_MAX_HISTORY_LENGTH:] if self.conversation_history else None
            ):
                chunk_count += 1

                # 直接处理 chunk
                if isinstance(chunk, dict):
                    chunk_type = chunk.get("type")

                    if chunk_type == "tool_call":
                        logger.info(f"处理工具调用: {chunk.get('tool_name')}")
                        yield {
                            "type": "tool_call",
                            "tool_name": chunk.get("tool_name"),
                            "tool_args": chunk.get("tool_args")
                        }
                    elif chunk_type == "tool_result":
                        logger.info(f"处理工具结果: {chunk.get('tool_name')}")
                        yield {
                            "type": "tool_result",
                            "tool_name": chunk.get("tool_name"),
                            "result": chunk.get("result"),
                            "status": chunk.get("status", "success")
                        }
                    elif chunk_type == "content":
                        content_chunk = chunk.get("content", "")
                        if content_chunk:
                            self._current_stream_response += content_chunk
                            logger.debug(f"处理内容块: {content_chunk[:50]}...")
                            yield {
                                "type": "content",
                                "content": content_chunk
                            }
                    elif chunk_type == "error":
                        logger.error(f"处理错误: {chunk.get('error')}")
                        yield {
                            "type": "error",
                            "content": chunk.get("error", "未知错误")
                        }
                    else:
                        logger.warning(f"未知的 chunk 类型: {chunk_type}")
                else:
                    logger.warning(f"非字典类型的 chunk: {type(chunk)} - {chunk}")

            logger.info(f"流式处理完成，共收到 {chunk_count} 个 chunks，总响应长度: {len(self._current_stream_response)}")

            # 流式处理完成后，更新对话历史
            if self._current_stream_response:
                self.conversation_history.append(HumanMessage(content=message))
                self.conversation_history.append(AIMessage(content=self._current_stream_response))

                # 限制历史记录长度
                max_history = getattr(settings, 'MAX_HISTORY_LENGTH', 50)
                if len(self.conversation_history) > max_history * 2:
                    self.conversation_history = self.conversation_history[-max_history * 2:]

            # 发送完成信号
            yield {
                "type": "complete",
                "full_response": self._current_stream_response
            }

        except Exception as e:
            logger.error(f"流式处理消息失败: {str(e)}", exc_info=True)
            yield {
                "type": "error",
                "content": f"处理消息时出错: {str(e)}"
            }

    def reset_history(self):
        """重置对话历史"""
        self.conversation_history = []
        logger.info("对话历史已重置")

    async def close(self):
        """关闭连接"""
        if self.deep_agent:
            await self.deep_agent.close()

    async def __aenter__(self):
        return await self.initialize()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def get_tools_info(self) -> List[dict]:
        """获取工具信息"""
        if not self.deep_agent:
            return []
        return self.deep_agent.get_tools_info()
