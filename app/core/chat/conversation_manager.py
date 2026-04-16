# core/chat/conversation_manager.py
from typing import List, Optional, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage
from core.agent.agent_manager import agent_manager
from core.chat.session_service import SessionDatabase
from config.settings import settings
from config.logging_config import get_logger
from datetime import datetime

logger = get_logger(__name__)


class ConversationManager:
    """
    对话管理器
    负责会话管理和记忆持久化，通过 AgentManager 共享 Agent 实例
    """

    def __init__(self, conversation_id: str = None, user_id: str = None):
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.conversation_history: List[BaseMessage] = []

        # 数据库管理（延迟初始化）
        self.db: Optional[SessionDatabase] = None

        # 流式处理相关
        self._current_stream_response = ""
        self._streaming_tool_calls = []

        # 初始化标志
        self._initialized = False

    @property
    def deep_agent(self):
        """通过 AgentManager 获取共享的 Agent 实例"""
        return agent_manager.get_agent()

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

            # 初始化数据库
            self.db = SessionDatabase()

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
        """从数据库加载历史消息"""
        if not self.conversation_id:
            logger.warning("未提供conversation_id，无法加载历史")
            return

        if not self.db:
            self.db = SessionDatabase()

        # 获取或创建会话记录
        session = self.db.get_or_create_session(self.conversation_id, self.user_id)
        logger.info(f"加载会话: {session.get('title', '未命名')}")

        # 加载历史消息
        messages = self.db.load_messages(self.conversation_id, limit=settings.MSG_MAX_HISTORY_LENGTH * 2)

        # 转换为LangChain消息格式
        self.conversation_history = []
        for msg in messages:
            msg_type = msg.get('message_type')
            content = msg.get('content', '')
            tool_calls = msg.get('tool_calls', [])

            if msg_type == 'human':
                self.conversation_history.append(HumanMessage(content=content))
            elif msg_type == 'ai':
                ai_msg = AIMessage(content=content)
                if tool_calls:
                    ai_msg.tool_calls = tool_calls
                self.conversation_history.append(ai_msg)
            elif msg_type == 'tool':
                self.conversation_history.append(ToolMessage(content=content))

        logger.info(f"加载了 {len(self.conversation_history)} 条历史消息")

    async def save_conversation(self):
        """保存当前对话到数据库"""
        if not self.conversation_id:
            logger.warning("未提供conversation_id，无法保存对话")
            return

        if not self.db:
            self.db = SessionDatabase()

        # 转换消息为可存储格式
        messages_to_save = []
        for msg in self.conversation_history:
            msg_data = {
                'type': 'human' if isinstance(msg, HumanMessage) else
                'ai' if isinstance(msg, AIMessage) else
                'tool' if isinstance(msg, ToolMessage) else 'unknown',
                'content': msg.content,
                'create_time': datetime.now()
            }

            # 保存工具调用信息
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                msg_data['tool_calls'] = msg.tool_calls

            messages_to_save.append(msg_data)

        # 保存到数据库
        if messages_to_save:
            self.db.save_messages(self.conversation_id, messages_to_save)
            logger.info(f"保存了 {len(messages_to_save)} 条消息到会话 {self.conversation_id}")

    async def process_message(self, message: str) -> str:
        """处理用户消息（非流式）"""
        if not self._initialized:
            raise RuntimeError("ConversationManager尚未初始化")

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
            await self._update_history(message, response_text, result.get("messages", []))

            # 保存到数据库
            await self.save_conversation()

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

    async def _update_history(self, user_message: str, assistant_response: str, messages: List[BaseMessage]):
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
        max_history = getattr(settings, 'MSG_MAX_HISTORY_LENGTH', 50)
        if len(self.conversation_history) > max_history * 2:
            self.conversation_history = self.conversation_history[-max_history * 2:]

    async def process_message_stream(self, message: str):
        """
        流式处理用户消息
        Yields: 流式响应块
        """
        if not self._initialized:
            raise RuntimeError("ConversationManager尚未初始化")

        # 确保有 conversation_id
        if not self.conversation_id:
            import uuid
            self.conversation_id = str(uuid.uuid4())
            logger.info(f"自动生成新的 conversation_id: {self.conversation_id}")

        logger.info(f"流式处理用户消息: {message[:100]}...")

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
                max_history = getattr(settings, 'MSG_MAX_HISTORY_LENGTH', 50)
                if len(self.conversation_history) > max_history * 2:
                    self.conversation_history = self.conversation_history[-max_history * 2:]

                # 保存到数据库
                await self.save_conversation()

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
        """重置当前会话的对话历史"""
        self.conversation_history = []
        logger.info(f"会话 {self.conversation_id} 的对话历史已重置")

    async def clear_session(self):
        """清除整个会话（从数据库中删除）"""
        if self.conversation_id and self.db:
            self.db.delete_session(self.conversation_id)
            self.conversation_history = []
            logger.info(f"会话 {self.conversation_id} 已完全清除")

    async def close(self):
        """关闭连接（不需要关闭 Agent，因为 Agent 是共享的）"""
        if self.db:
            # 数据库连接不需要显式关闭，SQLAlchemy 会管理
            self.db = None
        self._initialized = False
        logger.info(f"ConversationManager 已关闭, conversation_id: {self.conversation_id}")

    async def __aenter__(self):
        return await self.initialize()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def get_tools_info(self) -> List[dict]:
        """获取工具信息"""
        return agent_manager.get_tools_info()
