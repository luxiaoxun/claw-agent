# soma/channel/__init__.py
from soma.channel.base import (
    IChannelAdapter,
    IChannelRouter,
    NormalizedMessage,
    IMContext,
)
from soma.channel.router import channel_router

__all__ = [
    "IChannelAdapter",
    "IChannelRouter",
    "NormalizedMessage",
    "IMContext",
    "channel_router",
]