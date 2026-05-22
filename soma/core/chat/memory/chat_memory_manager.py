# core/chat/memory/chat_memory_manager.py
from typing import List, Optional, Dict, Any, Callable
from langchain_core.messages import BaseMessage
from soma.config.logging_config import get_logger
from soma.core.chat.memory.strategy.database_chat_message_history import DatabaseChatMessageHistory
from soma.core.chat.memory.strategy.context_strategy import (
    ContextStrategy, RoundBasedContextStrategy, TokenBasedContextStrategy, MessageCountBasedContextStrategy)
from soma.core.chat.memory.strategy.context_strategy_factory import ContextStrategyFactory

logger = get_logger(__name__)


class ChatMemoryManager:
    def __init__(
            self,
            session_id: str = None,
            user_id: str = None,
            context_strategy: Optional[ContextStrategy] = None
    ):
        self.session_id = session_id
        self.user_id = user_id
        self._history = DatabaseChatMessageHistory(session_id, user_id)
        self._context_strategy = context_strategy or ContextStrategyFactory.create_from_settings()

    @property
    def messages(self) -> List[BaseMessage]:
        return self._history.messages

    @property
    def current_round_number(self) -> int:
        return self._history.current_round_number

    @property
    def context_strategy(self) -> ContextStrategy:
        return self._context_strategy

    @context_strategy.setter
    def context_strategy(self, strategy: ContextStrategy):
        self._context_strategy = strategy
        logger.info(f"上下文策略已切换: {strategy.get_strategy_name()}")

    def set_strategy(self, strategy_type: str, **kwargs):
        self._context_strategy = ContextStrategyFactory.create(strategy_type, **kwargs)
        logger.info(f"上下文策略已切换: {self._context_strategy.get_strategy_name()}")

    async def load_history(self, session_id: str = None, max_history_length: int = None):
        if session_id:
            self.session_id = session_id
        await self._history.load_history(self.session_id, max_history_length)

    def get_context_history(self, max_history_length: int = None) -> List[BaseMessage]:
        if max_history_length is not None:
            current_strategy = self._context_strategy
            strategy_name = current_strategy.get_strategy_name()

            if "RoundBased" in strategy_name:
                temp_strategy = RoundBasedContextStrategy(max_rounds=max_history_length)
                return temp_strategy.get_context(self._history)
            elif "TokenBased" in strategy_name:
                temp_strategy = TokenBasedContextStrategy(max_tokens=max_history_length)
                return temp_strategy.get_context(self._history)
            elif "MessageCount" in strategy_name:
                temp_strategy = MessageCountBasedContextStrategy(max_messages=max_history_length)
                return temp_strategy.get_context(self._history)

        return self._context_strategy.get_context(self._history)

    async def save_current_round(
            self,
            user_message: str,
            ai_message: str,
            messages: List[BaseMessage],
            meta_data: Dict = None
    ):
        await self._history.add_messages_with_round(
            user_message=user_message,
            ai_response=ai_message,
            message_chain=messages
        )
        return self._history.current_round_number  # 使用 property

    def reset_history(self):
        self._history.clear()

    def get_context_by_tokens(
            self,
            max_tokens: int = 4000,
            strategy: str = "last",
            include_system: bool = True,
            start_on: str = "human",
            allow_partial: bool = False,
            token_counter: Optional[str or Callable] = "auto"
    ) -> List[BaseMessage]:
        temp_strategy = TokenBasedContextStrategy(
            max_tokens=max_tokens,
            strategy=strategy,
            include_system=include_system,
            start_on=start_on,
            allow_partial=allow_partial,
            token_counter=token_counter
        )
        return temp_strategy.get_context(self._history)

    def get_context_by_message_count(self, max_messages: int = 20) -> List[BaseMessage]:
        temp_strategy = MessageCountBasedContextStrategy(max_messages=max_messages)
        return temp_strategy.get_context(self._history)

    def get_round_based_context(self, max_rounds: int = None) -> List[BaseMessage]:
        temp_strategy = RoundBasedContextStrategy(max_rounds=max_rounds)
        return temp_strategy.get_context(self._history)

    def get_strategy_info(self) -> Dict[str, Any]:
        return {
            "current_strategy": self._context_strategy.get_strategy_name(),
            "available_strategies": ["round", "token", "message_count", "semantic", "hybrid"],
            "session_id": self.session_id,
            "total_messages": len(self._history.messages),
            "total_rounds": len(self._history.chat_rounds)
        }
