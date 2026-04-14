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
            logger.info(f"ConversationManager初始化完成，模式: {self.deep_agent.get_mode()}")
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
                             -settings.MAX_HISTORY_LENGTH:] if self.conversation_history else None
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

            # 调用 Agent 的流式处理
            async for chunk in self.deep_agent.stream_process(
                    message,
                    chat_history=self.conversation_history[
                                 -settings.MAX_HISTORY_LENGTH:] if self.conversation_history else None
            ):
                # 解析 chunk
                for chunk_type, chunk_data in self._parse_stream_chunk(chunk):
                    if chunk_type == "tool_call":
                        # 发送工具调用信息
                        yield {
                            "type": "tool_call",
                            "tool_name": chunk_data.get("tool_name"),
                            "tool_args": chunk_data.get("tool_args")
                        }

                    elif chunk_type == "tool_result":
                        # 发送工具结果
                        yield {
                            "type": "tool_result",
                            "tool_name": chunk_data.get("tool_name"),
                            "result": chunk_data.get("result"),
                            "status": chunk_data.get("status", "success")
                        }

                    elif chunk_type == "content":
                        # 累积响应
                        self._current_stream_response += chunk_data
                        yield {
                            "type": "content",
                            "content": chunk_data
                        }

                    elif chunk_type == "error":
                        yield {
                            "type": "error",
                            "content": chunk_data
                        }

            # 流式处理完成后，更新对话历史
            if self._current_stream_response:
                # 注意：这里简化了历史更新，实际可能需要从流式数据中重建完整消息
                # 对于流式响应，我们可以只保存最终的响应文本
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

    def _parse_stream_chunk(self, chunk):
        """
        解析 Agent 流式输出的 chunk
        返回: (type, data) 元组
        """
        # 处理错误信息
        if isinstance(chunk, dict) and chunk.get("type") == "error":
            yield "error", chunk.get("error", "未知错误")
            return

        # 处理字典类型的 chunk
        if isinstance(chunk, dict):
            # 检查是否有 messages 字段
            if "messages" in chunk:
                messages = chunk["messages"]
                if messages:
                    last_message = messages[-1]

                    # AI 消息
                    if hasattr(last_message, "type") and last_message.type == "ai":
                        # 检查是否有工具调用
                        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                            for tool_call in last_message.tool_calls:
                                yield "tool_call", {
                                    "tool_name": tool_call.get("name"),
                                    "tool_args": tool_call.get("args", {})
                                }

                        # 内容流
                        if hasattr(last_message, "content") and last_message.content:
                            yield "content", last_message.content

                    # 工具消息
                    elif hasattr(last_message, "type") and last_message.type == "tool":
                        yield "tool_result", {
                            "tool_name": getattr(last_message, "name", "unknown"),
                            "result": last_message.content,
                            "status": "success"
                        }

            # 直接的 chunk 内容
            elif "content" in chunk:
                yield "content", chunk["content"]

        # 字符串类型的 chunk
        elif isinstance(chunk, str):
            yield "content", chunk

        # 检查是否是 AIMessageChunk
        elif hasattr(chunk, "content") and chunk.content:
            yield "content", chunk.content

        # 检查工具调用
        elif hasattr(chunk, "tool_calls") and chunk.tool_calls:
            for tool_call in chunk.tool_calls:
                yield "tool_call", {
                    "tool_name": tool_call.get("name"),
                    "tool_args": tool_call.get("args", {})
                }

        # 检查是否是 ToolMessage
        elif hasattr(chunk, "type") and chunk.type == "tool":
            yield "tool_result", {
                "tool_name": getattr(chunk, "name", "unknown"),
                "result": chunk.content if hasattr(chunk, "content") else str(chunk),
                "status": "success"
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

    def get_agent_mode(self) -> str:
        """获取当前Agent模式"""
        if not self.deep_agent:
            return "uninitialized"
        return self.deep_agent.get_mode()

    def get_conversation_summary(self) -> Dict[str, Any]:
        """获取对话摘要信息"""
        return {
            "total_messages": len(self.conversation_history),
            "agent_mode": self.get_agent_mode()
        }
