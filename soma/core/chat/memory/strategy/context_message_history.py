# core/chat/memory/strategy/context_message_history.py
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.chat_history import BaseChatMessageHistory
from soma.config.settings import settings
from soma.config.logging_config import get_logger
from datetime import datetime
from soma.service.database_service import database_service
from soma.utils.message_handler import MessageHandler

if TYPE_CHECKING:
    # 仅用于类型提示，避免循环导入
    pass

logger = get_logger(__name__)


class ContextChatMessageHistory(BaseChatMessageHistory):
    """
    符合 LangChain 标准的数据库消息历史
    """

    def __init__(self, session_id: str = None, user_id: str = None):
        self.session_id = session_id
        self.user_id = user_id
        self._initialized = False

        # 缓存的消息列表
        self._messages: List[BaseMessage] = []

        # 缓存的轮次数据
        self._chat_rounds: List[Dict] = []
        self._next_round_number: int = 1

    @property
    def message_service(self):
        return database_service.message_service

    @property
    def messages(self) -> List[BaseMessage]:
        """实现 BaseChatMessageHistory 的 messages 属性"""
        if not self._initialized:
            return []
        return self._messages.copy()

    @property
    def current_round_number(self) -> int:
        """获取当前已保存的轮次数"""
        return self._next_round_number - 1

    @property
    def chat_rounds(self) -> List[Dict]:
        """获取轮次数据"""
        return self._chat_rounds.copy()

    @property
    def initialized(self) -> bool:
        return self._initialized

    def add_message(self, message: BaseMessage) -> None:
        raise NotImplementedError("请使用 add_messages_with_round() 方法以轮次为单位保存")

    def add_messages(self, messages: List[BaseMessage]) -> None:
        raise NotImplementedError("请使用 add_messages_with_round() 方法以轮次为单位保存")

    async def add_messages_with_round(self, user_message: str, ai_response: str,
                                      message_chain: List[BaseMessage]) -> None:
        """以对话轮次为单位添加消息"""
        if not self.session_id:
            logger.error("未提供 session_id，无法保存对话轮次")
            return

        # 只保存当前轮的 ToolMessage
        tool_messages = [msg for msg in message_chain if isinstance(msg, ToolMessage)]

        round_id = await self._save_round_to_db(
            user_message=user_message,
            ai_response=ai_response,
            message_chain=tool_messages  # 只存 ToolMessage
        )

        if round_id:
            # 更新内存缓存（只用 user_message + ai_message）
            self._messages.append(HumanMessage(content=user_message))
            if ai_response:
                self._messages.append(AIMessage(content=ai_response))

            # 更新轮次缓存（message_chain 只存 ToolMessage）
            self._chat_rounds.append({
                'id': round_id,
                'user_message': user_message,
                'ai_message': ai_response,
                'message_chain': MessageHandler.serialize(tool_messages),
                'round_number': self._next_round_number,
                'create_time': datetime.now().isoformat()
            })

            # 限制内存中的轮次数
            max_rounds = settings.MAX_MSG_HISTORY_LENGTH
            if len(self._chat_rounds) > max_rounds:
                self._chat_rounds = self._chat_rounds[-max_rounds:]
                self._messages = self._rebuild_messages_from_rounds()

            self._next_round_number += 1
            logger.info(f"保存对话轮次 {self._next_round_number - 1} 成功")

    async def load_history(self, session_id: str = None, max_rounds: int = None) -> None:
        """从数据库加载历史对话轮次"""
        if session_id:
            self.session_id = session_id

        if not self.session_id:
            logger.warning("未提供 session_id，无法加载历史")
            return

        if not self.message_service:
            raise RuntimeError("消息服务未初始化")

        max_rounds = max_rounds or settings.MAX_MSG_HISTORY_LENGTH

        total_count = self.message_service.get_message_rounds_count(self.session_id)
        if total_count == 0:
            self._chat_rounds = []
        elif total_count <= max_rounds:
            self._chat_rounds = self.message_service.load_messages(
                self.session_id,
                order_desc=False
            )
        else:
            self._chat_rounds = self.message_service.load_messages(
                self.session_id,
                limit=max_rounds,
                offset=total_count - max_rounds,
                order_desc=False
            )
        self._messages = self._rebuild_messages_from_rounds()

        if self._chat_rounds:
            self._next_round_number = max(r.get('round_number', 0) for r in self._chat_rounds) + 1
        else:
            self._next_round_number = 1

        self._initialized = True
        logger.info(f"加载会话历史完成: session_id={self.session_id}, "
                    f"总轮次数={total_count}, "
                    f"上下文轮次数={len(self._chat_rounds)}, 上下文消息数={len(self._messages)}, "
                    f"下一轮次={self._next_round_number}")

    def _rebuild_messages_from_rounds(self, rounds: List[Dict] = None) -> List[BaseMessage]:
        """从轮次数据重建消息列表（只用 user_message + ai_message）"""
        if rounds is None:
            rounds = self._chat_rounds

        messages = []
        for round_data in rounds:
            messages.append(HumanMessage(content=round_data['user_message']))
            if round_data.get('ai_message'):
                messages.append(AIMessage(content=round_data['ai_message']))
        return messages

    def _append_to_messages(self, user_message: str, message_chain: List[BaseMessage]) -> None:
        """将新的轮次追加到 _messages 中"""
        self._messages.append(HumanMessage(content=user_message))
        self._messages.extend(message_chain)

    async def _save_round_to_db(self, user_message: str, ai_response: str,
                                message_chain: List[BaseMessage]) -> Optional[str]:
        """保存对话轮次到数据库"""
        if not self.message_service:
            logger.warning("消息服务未初始化")
            return None

        try:
            meta_data = {
                'timestamp': datetime.now().isoformat(),
                'message_count': len(message_chain)
            }

            round_id = self.message_service.save_round_message(
                session_id=self.session_id,
                user_message=user_message,
                ai_message=ai_response,
                message_chain=message_chain,
                round_number=self._next_round_number,
                meta_data=meta_data
            )
            return round_id
        except Exception as e:
            logger.error(f"保存对话轮次时出错: {str(e)}", exc_info=True)
            return None

    def clear(self) -> None:
        """清空历史（只清空内存，不清除数据库）"""
        self._messages = []
        self._chat_rounds = []
        self._next_round_number = 1
        self._initialized = False
        logger.debug(f"会话 {self.session_id} 的消息历史已清空")
