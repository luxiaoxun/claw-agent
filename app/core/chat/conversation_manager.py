# core/chat/conversation_manager.py
from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage
from core.agent.agent_manager import agent_manager
from service.database_service import database_service
from config.settings import settings
from config.logging_config import get_logger
from datetime import datetime
import uuid
import hashlib

logger = get_logger(__name__)


class ConversationManager:
    """
    对话管理器
    负责会话管理和记忆持久化，通过 AgentManager 共享 Agent 实例
    使用全局单例的数据库服务
    """

    def __init__(self, conversation_id: str = None, user_id: str = None):
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.conversation_history: List[BaseMessage] = []

        # 记录已保存的消息ID集合，用于去重
        self._saved_message_ids: set = set()

        # 流式处理相关
        self._current_stream_response = ""
        self._streaming_tool_calls = []

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

    async def initialize(self, conversation_id: str = None, user_id: str = None):
        """
        初始化对话管理器

        Args:
            conversation_id: 会话ID（可选）
            user_id: 用户ID（可选）
        """
        if self._initialized:
            logger.debug(f"ConversationManager 已初始化，conversation_id: {self.conversation_id}")
            return self

        try:
            # 更新ID
            if conversation_id:
                self.conversation_id = conversation_id
            if user_id:
                self.user_id = user_id

            # 确保数据库服务已初始化
            if not database_service.is_initialized():
                logger.warning("数据库服务未初始化，正在自动初始化...")
                database_service.initialize()

            # 确保 Agent 已初始化（通过 AgentManager）
            if not agent_manager.is_initialized():
                await agent_manager.initialize()

            # 如果有会话ID，加载历史消息
            if self.conversation_id:
                await self.load_history()
                logger.info(f"加载会话历史: {self.conversation_id}, 消息数: {len(self.conversation_history)}")
            else:
                logger.info("创建新会话，等待 conversation_id")

            self._initialized = True
            logger.info(f"ConversationManager初始化完成, conversation_id: {self.conversation_id}")
            return self
        except Exception as e:
            logger.error(f"ConversationManager初始化失败: {str(e)}")
            raise

    async def load_history(self):
        """
        从数据库加载历史消息
        1. 按时间倒序加载最近的 MSG_MAX_HISTORY_LENGTH 条消息
        2. 在内存中按时间正序构建 conversation_history
        """
        if not self.conversation_id:
            logger.warning("未提供conversation_id，无法加载历史")
            return

        if not self.session_service or not self.message_service:
            raise RuntimeError("数据库服务未初始化")

        # 获取或创建会话记录
        session = self.session_service.get_or_create_session(self.conversation_id, self.user_id)
        logger.info(f"加载会话: {session.get('title', '未命名')}")

        # 加载最近的 MSG_MAX_HISTORY_LENGTH 条历史消息（按时间倒序）
        messages_desc = self.message_service.load_messages(
            self.conversation_id,
            limit=settings.MSG_MAX_HISTORY_LENGTH,
            offset=0,
            order_desc=True  # 按时间倒序加载
        )

        # 将消息按时间正序排列（从旧到新）
        messages_asc = list(reversed(messages_desc))

        # 清空当前历史
        self.conversation_history = []
        self._saved_message_ids.clear()

        # 转换为LangChain消息格式，并记录已保存的消息ID
        for msg in messages_asc:
            msg_type = msg.get('message_type')
            content = msg.get('content', '')
            tool_calls = msg.get('tool_calls', [])
            msg_id = msg.get('id')

            # 记录已保存的消息ID（使用数据库ID或内容哈希）
            if msg_id:
                self._saved_message_ids.add(msg_id)
            else:
                # 如果没有ID，使用内容哈希作为标识
                msg_hash = self._generate_message_hash(msg_type, content, tool_calls)
                self._saved_message_ids.add(msg_hash)

            if msg_type == 'human':
                self.conversation_history.append(HumanMessage(content=content))
            elif msg_type == 'ai':
                ai_msg = AIMessage(content=content)
                if tool_calls:
                    ai_msg.tool_calls = tool_calls
                self.conversation_history.append(ai_msg)
            elif msg_type == 'tool':
                self.conversation_history.append(ToolMessage(content=content))

        logger.info(
            f"加载了 {len(self.conversation_history)} 条历史消息（最近 {settings.MSG_MAX_HISTORY_LENGTH} 条），已记录 {len(self._saved_message_ids)} 个消息标识")

    def _get_context_history(self) -> List[BaseMessage]:
        """
        获取用于 AI 上下文的最近历史消息
        返回最近的 MSG_MAX_HISTORY_LENGTH 条消息（按时间正序）
        """
        if not self.conversation_history:
            return []

        # 获取最近的 MSG_MAX_HISTORY_LENGTH 条消息
        context_length = min(settings.MSG_MAX_HISTORY_LENGTH, len(self.conversation_history))
        return self.conversation_history[-context_length:]

    def _generate_message_hash(self, msg_type: str, content: str, tool_calls: List = None) -> str:
        """生成消息的唯一哈希值（用于去重）"""
        import json
        message_str = f"{msg_type}|{content}|{json.dumps(tool_calls, sort_keys=True) if tool_calls else ''}"
        return hashlib.md5(message_str.encode()).hexdigest()

    async def _save_new_messages(self, messages: List[BaseMessage]):
        """保存新消息到数据库（只保存未保存过的消息）"""
        if not self.conversation_id:
            logger.warning("未提供conversation_id，无法保存消息")
            return

        if not self.message_service:
            logger.warning("消息服务未初始化")
            return

        # 转换消息为可存储格式，并过滤已存在的消息
        messages_to_save = []
        for msg in messages:
            # 生成消息标识
            msg_type = 'human' if isinstance(msg, HumanMessage) else \
                'ai' if isinstance(msg, AIMessage) else \
                    'tool' if isinstance(msg, ToolMessage) else 'unknown'

            # 生成消息哈希
            tool_calls = None
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                tool_calls = msg.tool_calls
            elif isinstance(msg, ToolMessage):
                tool_calls = None

            msg_hash = self._generate_message_hash(msg_type, msg.content, tool_calls)

            # 检查消息是否已保存
            if msg_hash in self._saved_message_ids:
                logger.debug(f"消息已存在，跳过保存: {msg_hash[:8]}")
                continue

            # 准备保存的消息数据
            msg_data = {
                'type': msg_type,
                'content': msg.content,
                'create_time': datetime.now()
            }

            # 保存工具调用信息
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                msg_data['tool_calls'] = msg.tool_calls

            messages_to_save.append((msg_data, msg_hash))

        # 保存新消息到数据库
        if messages_to_save:
            # 提取消息数据列表
            msg_data_list = [msg_data for msg_data, _ in messages_to_save]
            success = self.message_service.save_messages(self.conversation_id, msg_data_list)

            if success:
                # 记录已保存的消息ID
                for _, msg_hash in messages_to_save:
                    self._saved_message_ids.add(msg_hash)
                logger.info(f"保存了 {len(messages_to_save)} 条新消息到会话 {self.conversation_id}")
            else:
                logger.error(f"保存消息到会话 {self.conversation_id} 失败")

    async def _update_history_and_save(self, user_message: str, assistant_response: str, messages: List[BaseMessage]):
        """更新对话历史并立即保存新消息"""
        new_messages = []

        # 添加用户消息
        user_msg = HumanMessage(content=user_message)
        self.conversation_history.append(user_msg)
        new_messages.append(user_msg)

        # 添加完整的消息链（保留工具调用等中间信息）
        for msg in messages:
            if isinstance(msg, AIMessage):
                # 如果有工具调用，保留完整消息
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    self.conversation_history.append(msg)
                    new_messages.append(msg)
            elif isinstance(msg, ToolMessage):
                # 保留工具执行结果供上下文使用
                self.conversation_history.append(msg)
                new_messages.append(msg)

        # 确保有最终的 AI 响应
        final_ai_msg = None
        if not any(
                isinstance(msg, AIMessage) and msg.content == assistant_response for msg in self.conversation_history):
            final_ai_msg = AIMessage(content=assistant_response)
            self.conversation_history.append(final_ai_msg)
            new_messages.append(final_ai_msg)

        # 立即保存新消息到数据库
        if new_messages:
            await self._save_new_messages(new_messages)

        # 限制历史记录长度（保留最近 N 轮对话）
        # 注意：这里只截断内存中的历史，不影响数据库
        # 数据库中的完整历史通过 load_history 的 limit 来控制加载数量
        max_history = settings.MSG_MAX_HISTORY_LENGTH
        if len(self.conversation_history) > max_history:
            # 保留最近的消息
            self.conversation_history = self.conversation_history[-max_history:]
            logger.debug(f"截断对话历史到 {max_history} 条消息")

    async def process_message(self, message: str) -> str:
        """处理用户消息（非流式）"""
        if not self._initialized:
            raise RuntimeError("ConversationManager尚未初始化")

        logger.info(f"处理用户消息: {message}")

        try:
            # 获取用于上下文的最近历史消息
            context_history = self._get_context_history()

            # 调用 Agent 处理消息
            result = await self.deep_agent.process(
                message,
                chat_history=context_history
            )

            # 提取响应文本并更新历史
            response_text = self._extract_response_text(result)
            await self._update_history_and_save(message, response_text, result.get("messages", []))

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
        if not self._initialized:
            raise RuntimeError("ConversationManager尚未初始化")

        # 确保有 conversation_id
        if not self.conversation_id:
            self.conversation_id = str(uuid.uuid4())
            logger.info(f"自动生成新的 conversation_id: {self.conversation_id}")

        logger.info(f"流式处理用户消息: {message[:100]}...")

        try:
            # 重置流式状态
            self._current_stream_response = ""
            self._streaming_tool_calls = []

            chunk_count = 0
            all_messages = []  # 收集完整的消息链

            # 获取用于上下文的最近历史消息
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

            # 流式处理完成后，更新对话历史并保存
            if self._current_stream_response:
                # 准备新消息列表
                new_messages = []

                # 添加用户消息
                user_msg = HumanMessage(content=message)
                self.conversation_history.append(user_msg)
                new_messages.append(user_msg)

                # 添加 AI 响应
                ai_msg = AIMessage(content=self._current_stream_response)
                self.conversation_history.append(ai_msg)
                new_messages.append(ai_msg)

                # 如果有工具调用相关的消息，也一并添加
                for msg in all_messages:
                    if isinstance(msg, (AIMessage, ToolMessage)):
                        # 避免重复添加
                        if msg not in self.conversation_history:
                            self.conversation_history.append(msg)
                            new_messages.append(msg)

                # 立即保存新消息到数据库
                if new_messages:
                    await self._save_new_messages(new_messages)

                # 限制历史记录长度
                max_history = settings.MSG_MAX_HISTORY_LENGTH
                if len(self.conversation_history) > max_history:
                    self.conversation_history = self.conversation_history[-max_history:]

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
        self.conversation_history = []
        self._saved_message_ids.clear()
        logger.info(f"会话 {self.conversation_id} 的对话历史已重置")

    async def clear_session(self):
        """清除整个会话（从数据库中删除）"""
        if self.conversation_id and self.session_service:
            success = self.session_service.delete_session(self.conversation_id)
            if success:
                self.conversation_history = []
                self._saved_message_ids.clear()
                logger.info(f"会话 {self.conversation_id} 已完全清除")
            else:
                logger.error(f"清除会话 {self.conversation_id} 失败")

    async def close(self):
        """关闭连接（不需要关闭数据库服务，因为是全局共享的）"""
        self._initialized = False
        logger.info(f"ConversationManager 已关闭, conversation_id: {self.conversation_id}")

    async def __aenter__(self):
        return await self.initialize()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def get_tools_info(self) -> List[dict]:
        """获取工具信息"""
        return agent_manager.get_tools_info()
