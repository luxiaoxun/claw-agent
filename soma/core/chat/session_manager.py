# core/chat/session_manager.py
from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, AIMessage
from soma.core.agent.agent_manager import agent_manager
from soma.service.database_service import database_service
from soma.config.logging_config import get_logger
from soma.config.settings import settings
from soma.core.chat.memory.chat_memory_manager import ChatMemoryManager
from soma.core.chat.memory.chat_file_manager import ChatFileManager
from soma.utils.message_handler import MessageHandler

logger = get_logger(__name__)


class SessionManager:
    """
    对话管理器
    负责会话管理、记忆持久化和文件上下文管理
    以对话轮次为单位管理消息历史
    """

    def __init__(self, session_id: str = None, user_id: str = None):
        self.session_id = session_id
        self.user_id = user_id

        # 聊天记忆管理器
        self.memory_manager = ChatMemoryManager(session_id, user_id)

        # 文件管理器
        self.file_manager = ChatFileManager(session_id, user_id)

        # 初始化标志
        self._initialized = False

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
                self.file_manager.session_id = session_id
            if user_id:
                self.user_id = user_id
                self.memory_manager.user_id = user_id
                self.file_manager.user_id = user_id

            # 初始化文件管理器
            await self.file_manager.initialize(session_id=self.session_id, user_id=self.user_id)

            # 如果有会话ID，加载历史消息
            if self.session_id:
                await self.memory_manager.load_history()
                logger.info(
                    f"加载会话历史: {self.session_id}, 轮次数: {self.memory_manager.current_round_number}, 文件数: {await self.file_manager.count()}")
            else:
                logger.info("创建新会话，等待 session_id")

            self._initialized = True
            logger.info(f"SessionManager初始化完成, session_id: {self.session_id}")
            return self
        except Exception as e:
            logger.error(f"SessionManager初始化失败: {str(e)}")
            raise

    async def _get_enhanced_context(self) -> List[BaseMessage]:
        """
        获取增强的上下文（包含文件信息）

        Returns:
            增强后的消息列表
        """

        # 将最近的 MAX_MSG_HISTORY_LENGTH 次对话轮次转换为消息列表
        context_history = self.memory_manager.get_context_history()

        # 获取文件上下文消息
        file_context_message = await self.file_manager.get_file_context_message()
        if file_context_message:
            # 将文件上下文添加到历史消息后面
            enhanced_context = context_history + [file_context_message] if context_history else [file_context_message]
            logger.info(f"已添加文件上下文到对话中，当前文件数: {await self.file_manager.count()}")
            return enhanced_context

        logger.info(f"获取{len(context_history)}条上下文历史消息")
        return context_history

    # 文件管理相关的便捷方法（委托给 file_manager）
    async def add_file_context(self, file_info: Dict[str, Any]) -> bool:
        """
        添加文件到会话上下文

        Args:
            file_info: 文件信息字典

        Returns:
            bool: 是否添加成功
        """
        if not self._initialized:
            logger.warning(f"SessionManager 未初始化，无法添加文件")
            return False

        return await self.file_manager.add_file(file_info)

    async def get_file_contexts(self) -> List[Dict[str, Any]]:
        """
        获取当前会话的所有文件上下文

        Returns:
            文件信息列表
        """
        if not self._initialized:
            return []

        return await self.file_manager.get_all_files()

    async def get_file_by_name(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        根据文件名获取文件信息

        Args:
            filename: 文件名或保存的文件名

        Returns:
            文件信息字典，如果未找到返回 None
        """
        if not self._initialized:
            return None

        # 先按保存名查找
        file_info = await self.file_manager.get_file(filename, by="saved_name")
        if file_info:
            return file_info

        # 再按原始文件名查找
        return await self.file_manager.get_file(filename, by="original_name")

    async def remove_file_context(self, file_id: str, by: str = "saved_name") -> bool:
        """
        从上下文中移除文件

        Args:
            file_id: 文件标识
            by: 标识类型

        Returns:
            bool: 是否移除成功
        """
        if not self._initialized:
            return False

        return await self.file_manager.remove_file(file_id, by)

    async def clear_file_contexts(self) -> int:
        """
        清空所有文件上下文

        Returns:
            清空的文件数量
        """
        if not self._initialized:
            return 0

        return await self.file_manager.clear()

    async def get_files_summary(self) -> str:
        """
        获取文件摘要信息

        Returns:
            文件摘要文本
        """
        if not self._initialized:
            return "会话未初始化"

        return await self.file_manager.get_files_summary()

    async def _save_current_round(self, user_message: str, ai_message: str, messages: List[BaseMessage]):
        """
        保存当前对话轮次到数据库
        """
        await self.memory_manager.save_current_round(user_message, ai_message, messages)

    async def process_message(self, message: str) -> str:
        """处理用户消息（非流式）"""
        logger.info(f"处理用户消息: {message}")

        try:
            # 获取增强的上下文（包含文件信息）
            enhanced_context = await self._get_enhanced_context()

            # 调用 Agent 处理消息
            result = await self.deep_agent.process(
                message,
                chat_history=enhanced_context
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

        msg_content = MessageHandler.extract_final_ai_response(messages)
        if msg_content:
            return msg_content
        else:
            return "无法获取响应内容"

    async def process_message_stream(self, message: str):
        """
        流式处理用户消息
        Yields: 流式响应块
        """
        logger.info(f"流式处理用户消息: {message[:100]}...")

        try:
            # 重置流式状态
            current_stream_response = ""
            chunk_count = 0
            # 存储本轮的完整消息链
            complete_messages = []

            # 获取增强的上下文（包含文件信息）
            enhanced_context = await self._get_enhanced_context()

            # 调用 Agent 的流式处理
            async for chunk in self.deep_agent.stream_process(
                    message,
                    chat_history=enhanced_context
            ):
                chunk_count += 1

                if isinstance(chunk, dict):
                    chunk_type = chunk.get("type")

                    if chunk_type == "tool_call":
                        logger.debug(f"处理工具调用: {chunk.get('tool_name')}")
                        if settings.MSG_TOOL_OUTPUT_ENABLED:
                            yield {
                                "type": "tool_call",
                                "tool_name": chunk.get("tool_name"),
                                "tool_args": chunk.get("tool_args")
                            }

                    elif chunk_type == "tool_result":
                        logger.debug(f"处理工具结果: {chunk.get('tool_name')}")
                        if settings.MSG_TOOL_OUTPUT_ENABLED:
                            yield {
                                "type": "tool_result",
                                "tool_name": chunk.get("tool_name"),
                                "result": chunk.get("result"),
                                "status": chunk.get("status", "success")
                            }

                    elif chunk_type == "content":
                        content_chunk = chunk.get("content", "")
                        if content_chunk:
                            current_stream_response += content_chunk
                            yield {
                                "type": "content",
                                "content": content_chunk
                            }

                    elif chunk_type == "complete":
                        # 使用后端已经去重过的消息链
                        if chunk.get("messages"):
                            complete_messages = chunk.get("messages")
                            logger.info(f"接收到完整消息链，共 {len(complete_messages)} 条消息")
                            logger.debug(f"消息类型: {[type(m).__name__ for m in complete_messages]}")

                    elif chunk_type == "error":
                        logger.error(f"处理错误: {chunk.get('error')}")
                        yield {
                            "type": "error",
                            "content": chunk.get("error", "未知错误")
                        }

            logger.info(f"流式处理完成，共收到 {chunk_count} 个 chunks，总响应长度: {len(current_stream_response)}")

            # 流式处理完成后，保存当前对话轮次
            if current_stream_response:
                # 如果 complete_messages 为空，构建最简单的消息链
                if not complete_messages:
                    complete_messages = [AIMessage(content=current_stream_response)]

                await self._save_current_round(message, current_stream_response, complete_messages)

            # 发送完成信号
            yield {
                "type": "complete",
                "full_response": current_stream_response
            }

        except Exception as e:
            logger.error(f"流式处理消息失败: {str(e)}", exc_info=True)
            yield {
                "type": "error",
                "content": f"处理消息时出错: {str(e)}"
            }

    async def close(self):
        """关闭连接"""
        if self.memory_manager:
            self.memory_manager.close()

        if self.file_manager:
            await self.file_manager.close()

        self._initialized = False
        logger.info(f"SessionManager 已关闭, session_id: {self.session_id}")

    async def __aenter__(self):
        return await self.initialize()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
