# core/chat/chat_memory_manager.py
from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage
from config.settings import settings
from config.logging_config import get_logger
from datetime import datetime
from service.database_service import database_service
from utils.message_handler import MessageHandler

logger = get_logger(__name__)


class ChatMemoryManager:
    """
    聊天记忆管理器
    负责会话历史的管理、存储和检索
    以对话轮次为单位管理消息历史
    """

    def __init__(self, session_id: str = None, user_id: str = None):
        self.session_id = session_id
        self.user_id = user_id

        # 存储对话轮次列表，每个元素包含完整的消息轮次
        self.chat_history: List[Dict] = []

        # 下一个轮次序号
        self._next_round_number = 1

    @property
    def session_service(self):
        """获取会话服务（从全局容器）"""
        return database_service.session_service

    @property
    def message_service(self):
        """获取消息服务（从全局容器）"""
        return database_service.message_service

    async def load_history(self, session_id: str = None, max_history_length: int = None):
        """从数据库加载历史对话轮次"""
        if session_id:
            self.session_id = session_id

        if not self.session_id:
            logger.warning("未提供session_id，无法加载历史")
            return

        if not self.session_service or not self.message_service:
            raise RuntimeError("数据库服务未初始化")

        max_length = max_history_length or settings.MSG_MAX_HISTORY_LENGTH

        # 获取或创建会话记录
        session = self.session_service.get_or_create_session(self.session_id, self.user_id)
        session_title = session.get('title', '未命名')
        logger.info(f"加载会话: {session_title}")

        # 加载最近的 max_length 次对话轮次
        rounds_desc = self.message_service.load_messages(
            self.session_id,
            limit=max_length,
            offset=0,
            order_desc=True
        )

        # 按时间正序排列
        rounds_asc = list(reversed(rounds_desc))

        # 清空当前历史
        self.chat_history = []

        # 构建对话轮次列表
        for round_data in rounds_asc:
            # 使用序列化器验证和清理消息链（可选）
            message_chain = round_data.get('message_chain', [])
            if message_chain:
                # 可以在这里验证消息链的有效性
                pass

            self.chat_history.append({
                'id': round_data.get('id'),
                'user_message': round_data.get('user_message'),
                'ai_response': round_data.get('ai_response'),
                'message_chain': message_chain,
                'round_number': round_data.get('round_number'),
                'create_time': round_data.get('create_time')
            })

        # 设置下一个轮次序号
        if self.chat_history:
            self._next_round_number = max(r.get('round_number', 0) for r in self.chat_history) + 1
        else:
            self._next_round_number = 1

        logger.info(
            f"会话:{session_title} 加载了 {len(self.chat_history)} 次对话轮次，下一轮次序号: {self._next_round_number}")

    def get_context_history(self, max_history_length: int = None) -> List[BaseMessage]:
        """
        获取用于 AI 上下文的最近历史消息
        """
        if not self.chat_history:
            return []

        max_length = max_history_length or settings.MSG_MAX_HISTORY_LENGTH
        context_messages = []

        # 取最近的 max_length 次轮次
        recent_rounds = self.chat_history[-max_length:]

        try:
            for round_data in recent_rounds:
                # 添加用户消息
                context_messages.append(HumanMessage(content=round_data['user_message']))

                # 添加完整的消息链（使用序列化器反序列化）
                message_chain = round_data.get('message_chain', [])
                if message_chain:
                    # 使用序列化器反序列化消息链
                    deserialized_messages = MessageHandler.deserialize(message_chain)
                    context_messages.extend(deserialized_messages)
                else:
                    # 兼容旧格式
                    context_messages.append(AIMessage(content=round_data['ai_response']))

        except Exception as e:
            logger.error(f"Get context history error: {e}", exc_info=True)
            return []

        return context_messages

    async def save_current_round(self, user_message: str, ai_response: str,
                                 messages: List[BaseMessage], meta_data: Dict = None) -> Optional[str]:
        """
        保存当前对话轮次到数据库
        """
        if not self.session_id:
            logger.warning("未提供session_id，无法保存对话轮次")
            return None

        if not self.message_service:
            logger.warning("消息服务未初始化")
            return None

        try:
            # 准备元数据
            if meta_data is None:
                meta_data = {}

            meta_data.update({
                'timestamp': datetime.now().isoformat(),
                'message_count': len(messages)
            })

            # 保存对话轮次
            round_id = self.message_service.save_round_message(
                session_id=self.session_id,
                user_message=user_message,
                ai_response=ai_response,
                message_chain=messages,  # 传递原始消息对象，序列化在服务层完成
                round_number=self._next_round_number,
                meta_data=meta_data
            )

            if round_id:
                # 更新内存中的对话轮次列表
                serialized_chain = MessageHandler.serialize(messages)

                self.chat_history.append({
                    'id': round_id,
                    'user_message': user_message,
                    'ai_response': ai_response,
                    'message_chain': serialized_chain,
                    'round_number': self._next_round_number,
                    'create_time': datetime.now().isoformat()
                })

                self._next_round_number += 1

                # 限制内存中的轮次数
                max_rounds = settings.MSG_MAX_HISTORY_LENGTH
                if len(self.chat_history) > max_rounds:
                    self.chat_history = self.chat_history[-max_rounds:]

                logger.info(f"保存对话轮次 {self._next_round_number - 1} 成功")
                return round_id
            else:
                logger.error(f"保存对话轮次失败")
                return None

        except Exception as e:
            logger.error(f"保存对话轮次时出错: {str(e)}", exc_info=True)
            return None

    def reset_history(self):
        """重置对话历史（只重置内存，不清除数据库）"""
        self.chat_history = []
        self._next_round_number = 1
        logger.info(f"会话 {self.session_id} 的对话历史已重置")
