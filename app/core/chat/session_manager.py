# core/chat/session_manager.py
from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, AIMessage
from core.agent.agent_manager import agent_manager
from service.database_service import database_service
from config.logging_config import get_logger
from core.chat.chat_memory_manager import ChatMemoryManager

logger = get_logger(__name__)


class SessionManager:
    """
    对话管理器
    负责会话管理和记忆持久化
    以对话轮次为单位管理消息历史
    """

    def __init__(self, session_id: str = None, user_id: str = None):
        self.session_id = session_id
        self.user_id = user_id

        # 聊天记忆管理器
        self.memory_manager = ChatMemoryManager(session_id, user_id)

        # 流式处理相关
        self._current_stream_response = ""
        self._streaming_tool_calls = []

        # 初始化标志
        self._initialized = False

    @property
    def chat_history(self) -> List[Dict]:
        """向后兼容：提供chat_history属性访问"""
        return self.memory_manager.chat_history

    @property
    def deep_agent(self):
        """通过 AgentManager 获取共享的 Agent 实例"""
        return agent_manager.get_agent()

    @property
    def session_service(self):
        """获取会话服务（从全局容器）"""
        return database_service.session_service

    @property
    def message_service(self):
        """获取消息服务（从全局容器）"""
        return database_service.message_service

    async def initialize(self, session_id: str = None, user_id: str = None):
        """
        初始化对话管理器

        Args:
            session_id: 会话ID（可选）
            user_id: 用户ID（可选）
        """
        if self._initialized:
            logger.debug(f"SessionManager 已初始化，session_id: {self.session_id}")
            return self

        try:
            # 更新ID
            if session_id:
                self.session_id = session_id
                self.memory_manager.session_id = session_id
            if user_id:
                self.user_id = user_id
                self.memory_manager.user_id = user_id

            # 确保数据库服务已初始化
            if not database_service.is_initialized():
                logger.warning("数据库服务未初始化，正在自动初始化...")
                database_service.initialize()

            # 确保 Agent 已初始化（通过 AgentManager）
            if not agent_manager.is_initialized():
                await agent_manager.initialize()

            # 如果有会话ID，加载历史消息
            if self.session_id:
                await self.memory_manager.load_history()
                logger.info(f"加载会话历史: {self.session_id}, 轮次数: {len(self.memory_manager.chat_history)}")
            else:
                logger.info("创建新会话，等待 session_id")

            self._initialized = True
            logger.info(f"SessionManager初始化完成, session_id: {self.session_id}")
            return self
        except Exception as e:
            logger.error(f"SessionManager初始化失败: {str(e)}")
            raise

    def _get_context_history(self) -> List[BaseMessage]:
        """
        获取用于 AI 上下文的最近历史消息
        将最近的 MSG_MAX_HISTORY_LENGTH 次对话轮次转换为消息列表
        """
        return self.memory_manager.get_context_history()

    async def _save_current_round(self, user_message: str, ai_response: str, messages: List[BaseMessage]):
        """
        保存当前对话轮次到数据库
        """
        await self.memory_manager.save_current_round(user_message, ai_response, messages)

    async def process_message(self, message: str) -> str:
        """处理用户消息（非流式）"""
        logger.info(f"处理用户消息: {message}")

        try:
            # 获取用于上下文的最近历史
            context_history = self._get_context_history()

            # 调用 Agent 处理消息
            result = await self.deep_agent.process(
                message,
                chat_history=context_history
            )

            # 提取响应文本
            response_text = self._extract_response_text(result)

            # 获取完整的消息链
            messages = result.get("messages", [])

            # 保存当前对话轮次
            await self._save_current_round(message, response_text, messages)

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

    async def process_message_stream(self, message: str):
        """
        流式处理用户消息
        Yields: 流式响应块
        """
        logger.info(f"流式处理用户消息: {message[:100]}...")

        try:
            # 重置流式状态
            self._current_stream_response = ""
            self._streaming_tool_calls = []

            chunk_count = 0
            all_messages = []  # 收集完整的消息链

            # 获取用于上下文的最近历史
            context_history = self._get_context_history()

            # 调用 Agent 的流式处理
            async for chunk in self.deep_agent.stream_process(
                    message,
                    chat_history=context_history
            ):
                chunk_count += 1

                # 直接处理 chunk
                if isinstance(chunk, dict):
                    chunk_type = chunk.get("type")

                    if chunk_type == "tool_call":
                        logger.debug(f"处理工具调用: {chunk.get('tool_name')}")
                        yield {
                            "type": "tool_call",
                            "tool_name": chunk.get("tool_name"),
                            "tool_args": chunk.get("tool_args")
                        }
                    elif chunk_type == "tool_result":
                        logger.debug(f"处理工具结果: {chunk.get('tool_name')}")
                        yield {
                            "type": "tool_result",
                            "tool_name": chunk.get("tool_name"),
                            "result": chunk.get("result"),
                            "status": chunk.get("status", "success")
                        }
                        # 收集工具结果消息
                        if 'message' in chunk:
                            all_messages.append(chunk['message'])
                    elif chunk_type == "content":
                        content_chunk = chunk.get("content", "")
                        if content_chunk:
                            self._current_stream_response += content_chunk
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
                    elif chunk_type == "complete" and 'messages' in chunk:
                        # 收集完整的消息链
                        all_messages = chunk.get('messages', [])
                    else:
                        logger.warning(f"未知的 chunk 类型: {chunk_type}")
                else:
                    logger.warning(f"非字典类型的 chunk: {type(chunk)} - {chunk}")

            logger.info(f"流式处理完成，共收到 {chunk_count} 个 chunks，总响应长度: {len(self._current_stream_response)}")

            # 流式处理完成后，保存当前对话轮次
            if self._current_stream_response:
                await self._save_current_round(message, self._current_stream_response, all_messages)

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

    async def reset_history(self):
        """重置当前会话的对话历史（只重置内存，不清除数据库）"""
        self.memory_manager.reset_history()
        logger.info(f"会话 {self.session_id} 的对话历史已重置")

    async def clear_session(self):
        """清除整个会话（从数据库中删除）"""
        if self.session_id and self.session_service:
            success = self.session_service.delete_session(self.session_id)
            if success:
                await self.reset_history()
                logger.info(f"会话 {self.session_id} 已完全清除")
            else:
                logger.error(f"清除会话 {self.session_id} 失败")

    async def close(self):
        """关闭连接"""
        self._initialized = False
        logger.info(f"SessionManager 已关闭, session_id: {self.session_id}")

    async def __aenter__(self):
        return await self.initialize()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def get_tools_info(self) -> List[dict]:
        """获取工具信息"""
        return agent_manager.get_tools_info()
