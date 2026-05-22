# core/chat/memory/strategy/context_strategy.py
from typing import List, Optional, Callable
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.messages.utils import trim_messages, count_tokens_approximately
from soma.config.settings import settings
from soma.config.logging_config import get_logger
from abc import ABC, abstractmethod
from soma.core.chat.memory.strategy.database_chat_message_history import DatabaseChatMessageHistory

logger = get_logger(__name__)


class ContextStrategy(ABC):
    """
    上下文管理策略抽象基类
    定义获取上下文的统一接口
    """

    @abstractmethod
    def get_context(self, history: 'DatabaseChatMessageHistory') -> List[BaseMessage]:
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        pass


class RoundBasedContextStrategy(ContextStrategy):
    """
    基于对话轮次的上下文策略
    保留最近的 N 轮对话
    """

    def __init__(self, max_rounds: int = None):
        self.max_rounds = max_rounds or settings.MSG_MAX_HISTORY_LENGTH

    def get_context(self, history: 'DatabaseChatMessageHistory') -> List[BaseMessage]:
        if not history.initialized:
            return []

        # 如果轮次数未超过限制，返回全部
        if len(history.chat_rounds) <= self.max_rounds:
            return history.messages.copy()

        # 只保留最近 max_rounds 轮，只用 user_message + ai_message
        recent_rounds = history.chat_rounds[-self.max_rounds:]
        messages = []
        for round_data in recent_rounds:
            messages.append(HumanMessage(content=round_data['user_message']))
            if round_data.get('ai_message'):
                messages.append(AIMessage(content=round_data['ai_message']))
        return messages

    def get_strategy_name(self) -> str:
        return f"RoundBasedStrategy(max_rounds={self.max_rounds})"


class TokenBasedContextStrategy(ContextStrategy):
    """
    基于 Token 数量的上下文策略
    使用 trim_messages 智能裁剪消息
    """

    def __init__(
            self,
            max_tokens: int = 4000,
            strategy: str = "last",
            include_system: bool = True,
            start_on: str = "human",
            allow_partial: bool = False,
            token_counter: Optional[str or Callable] = "auto"
    ):
        self.max_tokens = max_tokens
        self.strategy = strategy
        self.include_system = include_system
        self.start_on = start_on
        self.allow_partial = allow_partial
        self.token_counter_mode = token_counter
        self._token_counter = None  # 懒加载

    def get_token_counter(self) -> Callable:
        """获取 Token 计数器（懒加载）"""
        if self._token_counter is None:
            self._token_counter = self._resolve_token_counter(self.token_counter_mode)
        return self._token_counter

    def _resolve_token_counter(self, token_counter):
        """解析 token_counter 配置"""
        if callable(token_counter):
            return token_counter

        if isinstance(token_counter, str):
            if token_counter == "approximate":
                logger.debug("使用近似Token计数")
                return count_tokens_approximately
            elif token_counter == "tiktoken":
                logger.debug("使用tiktoken计数")
                return self._create_tiktoken_counter()
            elif token_counter == "auto":
                logger.debug("使用auto计数")
                return self._create_auto_counter()

        return count_tokens_approximately

    def _create_tiktoken_counter(self) -> Callable:
        """创建 tiktoken 计数器"""
        try:
            import tiktoken
            model_name = getattr(settings, 'LLM_MODEL', 'gpt-4o')
            encoding_name = self._get_encoding_for_model(model_name)
            encoding = tiktoken.get_encoding(encoding_name)

            def tiktoken_counter(messages: List[BaseMessage]) -> int:
                total = 0
                for msg in messages:
                    content = msg.content
                    if isinstance(content, str):
                        total += len(encoding.encode(content))
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                total += len(encoding.encode(item.get("text", "")))
                    total += 4
                return total

            logger.info("tiktoken 精确计数器初始化成功")
            return tiktoken_counter
        except ImportError:
            logger.warning("tiktoken 未安装，回退到近似计数")
            return count_tokens_approximately
        except Exception as e:
            logger.error(f"tiktoken 初始化失败: {e}，回退到近似计数")
            return count_tokens_approximately

    def _create_auto_counter(self) -> Callable:
        """创建自动计数器"""
        try:
            return self._create_tiktoken_counter()
        except Exception:
            logger.info("自动选择: 使用近似计数")
            return count_tokens_approximately

    def _get_encoding_for_model(self, model_name: str) -> str:
        """获取模型对应的编码"""
        model_to_encoding = {
            'gpt-4o': 'o200k_base', 'gpt-4o-mini': 'o200k_base',
            'gpt-4': 'cl100k_base', 'gpt-4-turbo': 'cl100k_base',
            'gpt-4-32k': 'cl100k_base', 'gpt-3.5-turbo': 'cl100k_base',
        }
        for pattern, encoding in model_to_encoding.items():
            if pattern in model_name.lower():
                return encoding
        return 'cl100k_base'

    def get_context(self, history: 'DatabaseChatMessageHistory') -> List[BaseMessage]:
        all_messages = history.messages
        if not all_messages:
            return []

        trim_params = {
            "messages": all_messages,
            "max_tokens": self.max_tokens,
            "strategy": self.strategy,
            "token_counter": self.get_token_counter(),
            "include_system": self.include_system,
            "allow_partial": self.allow_partial,
        }

        if self.strategy == "last" and self.start_on:
            trim_params["start_on"] = self.start_on

        try:
            trimmed = trim_messages(**trim_params)
            logger.debug(f"Token 裁剪完成: {len(all_messages)} -> {len(trimmed)}")
            return trimmed
        except Exception as e:
            logger.error(f"Token 裁剪失败: {e}，返回原始消息")
            return all_messages

    def get_strategy_name(self) -> str:
        return f"TokenBasedStrategy(max_tokens={self.max_tokens})"


class MessageCountBasedContextStrategy(ContextStrategy):
    """
    基于消息条数的上下文策略
    保留最近 N 条消息
    """

    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages

    def get_context(self, history: 'DatabaseChatMessageHistory') -> List[BaseMessage]:
        all_messages = history.messages
        if not all_messages:
            return []

        trimmed = trim_messages(
            messages=all_messages,
            max_tokens=self.max_messages,
            strategy="last",
            token_counter=len,
            include_system=True,
            start_on="human",
            allow_partial=False,
        )
        logger.debug(f"消息条数裁剪: {len(all_messages)} -> {len(trimmed)}")
        return trimmed

    def get_strategy_name(self) -> str:
        return f"MessageCountStrategy(max_messages={self.max_messages})"


class SemanticMemoryContextStrategy(ContextStrategy):
    """
    语义记忆策略
    保留重要的语义片段，压缩非关键信息
    """

    def __init__(self, max_tokens: int = 4000, importance_threshold: float = 0.7):
        self.max_tokens = max_tokens
        self.importance_threshold = importance_threshold

    def get_context(self, history: 'DatabaseChatMessageHistory') -> List[BaseMessage]:
        """
        简化实现：优先保留包含工具调用的消息，
        普通对话消息可以被压缩或省略
        """
        all_messages = history.messages
        if not all_messages:
            return []

        # 标记重要消息（包含工具调用的 AIMessage 及其相关的 ToolMessage）
        important_indices = set()

        for i, msg in enumerate(all_messages):
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                important_indices.add(i)
                # 查找对应的 ToolMessage
                for j, tool_msg in enumerate(all_messages[i + 1:]):
                    if isinstance(tool_msg, ToolMessage):
                        important_indices.add(i + 1 + j)
                        break

        # 构建重要消息 + 最近的部分消息
        result = []
        for i, msg in enumerate(all_messages):
            if i in important_indices or len(result) < 5:  # 至少保留前5条
                result.append(msg)
            elif len(all_messages) - i <= 3:  # 保留最后3条
                result.append(msg)

        if result:
            token_counter = count_tokens_approximately
            total_tokens = token_counter(result)
            # 如果还是超过 token 限制，进一步裁剪
            if total_tokens > self.max_tokens:
                result = trim_messages(
                    messages=result,
                    max_tokens=self.max_tokens,
                    strategy="last",
                    token_counter=token_counter,
                )

        return result

    def get_strategy_name(self) -> str:
        return f"SemanticMemoryStrategy(max_tokens={self.max_tokens})"


class HybridContextStrategy(ContextStrategy):
    """
    混合策略：结合多种策略的优势
    优先使用 token 限制，但保留重要轮次
    """

    def __init__(
            self,
            max_tokens: int = 4000,
            min_rounds: int = 3,
            token_counter_mode: str = "approximate"
    ):
        self.max_tokens = max_tokens
        self.min_rounds = min_rounds
        self.token_counter_mode = token_counter_mode
        self._token_strategy = TokenBasedContextStrategy(
            max_tokens=max_tokens,
            token_counter=token_counter_mode
        )

    def get_context(self, history: 'DatabaseChatMessageHistory') -> List[BaseMessage]:
        if not history.initialized:
            return []

        # 1. 先确保至少保留 min_rounds 轮（只用 user_message + ai_message）
        min_messages = []
        if len(history.chat_rounds) > self.min_rounds:
            min_rounds_data = history.chat_rounds[-self.min_rounds:]
            for round_data in min_rounds_data:
                min_messages.append(HumanMessage(content=round_data['user_message']))
                if round_data.get('ai_message'):
                    min_messages.append(AIMessage(content=round_data['ai_message']))
        else:
            min_messages = history.messages.copy()

        # 2. 使用 token 策略裁剪
        if self._token_strategy.get_token_counter()(min_messages) > self.max_tokens:
            return self._token_strategy.get_context(history)

        return min_messages

    def get_strategy_name(self) -> str:
        return f"HybridStrategy(max_tokens={self.max_tokens}, min_rounds={self.min_rounds})"
