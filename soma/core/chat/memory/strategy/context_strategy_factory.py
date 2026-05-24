# core/chat/memory/strategy/context_strategy_factory.py
from soma.config.settings import settings
from soma.config.logging_config import get_logger
from soma.core.chat.memory.strategy.context_strategy import (ContextStrategy,
                                                             RoundBasedContextStrategy,
                                                             TokenBasedContextStrategy,
                                                             MessageCountBasedContextStrategy,
                                                             SemanticMemoryContextStrategy,
                                                             HybridContextStrategy)

logger = get_logger(__name__)


class ContextStrategyFactory:
    """
    上下文策略工厂
    根据配置创建对应的策略实例
    """

    _strategies = {
        "round": RoundBasedContextStrategy,
        "token": TokenBasedContextStrategy,
        "message_count": MessageCountBasedContextStrategy,
        "semantic": SemanticMemoryContextStrategy,
        "hybrid": HybridContextStrategy,
    }

    @classmethod
    def create(cls, strategy_type: str, **kwargs) -> ContextStrategy:
        """
        创建策略实例

        Args:
            strategy_type: 策略类型
                - "round": 基于轮次
                - "token": 基于 Token
                - "message_count": 基于消息条数
                - "semantic": 语义记忆
                - "hybrid": 混合策略
            **kwargs: 策略特定参数

        Returns:
            策略实例
        """
        strategy_class = cls._strategies.get(strategy_type)
        if not strategy_class:
            logger.warning(f"未知策略类型: {strategy_type}，使用默认的 token 策略")
            strategy_class = TokenBasedContextStrategy

        logger.info(f"上下文策略：{strategy_type}")
        return strategy_class(**kwargs)

    @classmethod
    def create_from_settings(cls) -> ContextStrategy:
        """根据 settings 配置创建策略"""
        strategy_type = getattr(settings, 'CONTEXT_STRATEGY', 'round')

        strategy_configs = {
            "round": {
                "max_rounds": getattr(settings, 'MAX_MSG_HISTORY_LENGTH', 10)
            },
            "token": {
                "max_tokens": getattr(settings, 'MAX_CONTEXT_TOKENS', 4000),
                "strategy": getattr(settings, 'CONTEXT_STRATEGY_LAST', "last"),
                "token_counter": getattr(settings, 'TOKEN_COUNTER_MODE', "auto")
            },
            "message_count": {
                "max_messages": getattr(settings, 'MAX_CONTEXT_MESSAGES', 20)
            },
            "semantic": {
                "max_tokens": getattr(settings, 'MAX_CONTEXT_TOKENS', 4000)
            },
            "hybrid": {
                "max_tokens": getattr(settings, 'MAX_CONTEXT_TOKENS', 4000),
                "min_rounds": getattr(settings, 'MIN_CONTEXT_ROUNDS', 3)
            }
        }

        config = strategy_configs.get(strategy_type, {})
        return cls.create(strategy_type, **config)
