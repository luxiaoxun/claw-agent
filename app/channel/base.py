# app/channel/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable


@dataclass
class NormalizedMessage:
    """Internal message format used by all channel adapters."""
    platform: str                          # "feishu", "wechat", etc.
    user_id: str                            # External user ID on that platform
    chat_id: str                            # Chat/group ID
    message_id: str                         # Platform message ID (for threading)
    message_type: str                        # "text", "image", "file", etc.
    content: str                            # Text content
    is_group: bool                          # True if group chat
    raw_payload: Dict[str, Any] = field(default_factory=dict)  # Original payload


@dataclass
class IMContext:
    """Context passed through the pipeline for response routing."""
    platform: str
    user_id: str
    chat_id: str
    message_id: str
    session_id: str                          # Maps to Soma's session_id
    is_group: bool
    raw_payload: Dict[str, Any] = field(default_factory=dict)


class IChannelAdapter(ABC):
    """Abstract base class for IM platform adapters."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform name, e.g. 'feishu'."""
        pass

    @abstractmethod
    async def start(self):
        """Start the adapter (connect to IM platform)."""
        pass

    @abstractmethod
    async def stop(self):
        """Stop the adapter (disconnect)."""
        pass

    @abstractmethod
    async def send_message(self, chat_id: str, content: str, msg_type: str = "text") -> bool:
        """
        Send a message to the IM platform.

        Args:
            chat_id: Target chat/user ID
            content: Message content
            msg_type: Message type (text, image, etc.)

        Returns:
            True if sent successfully, False otherwise.
        """
        pass

    @abstractmethod
    def get_event_handler(self) -> Callable:
        """Return the event handler callable for this platform."""
        pass


class IChannelRouter:
    """Interface for routing normalized messages to SessionManager."""

    @abstractmethod
    async def route_message(self, message: NormalizedMessage) -> str:
        """
        Route a normalized message to the appropriate session.

        Returns:
            The session_id that handled the message.
        """
        pass

    @abstractmethod
    async def send_response(self, session_id: str, response: str):
        """
        Send an AI response back through the appropriate channel.

        Args:
            session_id: Soma session ID
            response: AI response text
        """
        pass