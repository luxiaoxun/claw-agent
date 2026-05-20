# app/channel/router.py
import hashlib
import json
from typing import Optional
from app.channel.base import NormalizedMessage, IChannelRouter, IMContext
from core.chat.session_manager import SessionManager
from config.logging_config import get_logger

logger = get_logger(__name__)


class ChannelRouter(IChannelRouter):
    """
    Routes normalized IM messages to the appropriate Soma SessionManager.
    Implements the session-per-chat_id model:
    - P2P: session_id = hash(platform + user_id + chat_id)
    - Group: session_id = hash(platform + chat_id)
    """

    def __init__(self):
        self._session_managers: dict[str, SessionManager] = {}

    def _generate_session_id(self, message: NormalizedMessage) -> str:
        """
        Generate a unique session_id based on chat type.

        P2P: hash(platform + user_id + chat_id)
        Group: hash(platform + chat_id)
        """
        if message.is_group:
            # Group chat: all members share the same session
            raw = f"{message.platform}:{message.chat_id}"
        else:
            # P2P: each user in each chat gets unique session
            raw = f"{message.platform}:{message.user_id}:{message.chat_id}"

        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _create_im_context(self, message: NormalizedMessage, session_id: str) -> IMContext:
        """Create IMContext from NormalizedMessage."""
        return IMContext(
            platform=message.platform,
            user_id=message.user_id,
            chat_id=message.chat_id,
            message_id=message.message_id,
            session_id=session_id,
            is_group=message.is_group,
            raw_payload=message.raw_payload
        )

    async def route_message(self, message: NormalizedMessage) -> str:
        """
        Route a normalized message to the appropriate session.

        Args:
            message: NormalizedMessage from an IM platform

        Returns:
            The session_id that handled the message.
        """
        try:
            # Generate session_id based on chat type
            session_id = self._generate_session_id(message)
            logger.info(f"Routing {message.platform} message: session_id={session_id}, is_group={message.is_group}")

            # Get or create SessionManager for this session
            if session_id not in self._session_managers:
                self._session_managers[session_id] = SessionManager(
                    session_id=session_id,
                    user_id=message.user_id
                )
                await self._session_managers[session_id].initialize()

            sm = self._session_managers[session_id]

            # Process the message (non-streaming for IM - we wait for full response)
            response = await sm.process_message(message.content)

            logger.info(f"AI response for session {session_id}: {response[:100]}...")

            # Send response back through the channel
            await self.send_response(session_id, response, message)

            return session_id

        except Exception as e:
            logger.error(f"Error routing message: {e}", exc_info=True)
            return ""

    async def send_response(self, session_id: str, response: str, message: NormalizedMessage):
        """
        Send an AI response back through the appropriate IM channel.

        Args:
            session_id: Soma session ID
            response: AI response text
            message: Original normalized message (to know where to reply)
        """
        try:
            if message.platform == "feishu":
                from app.channel.feishu.feishu_api import FeishuAPI
                from app.channel.feishu.feishu_config import feishu_settings
                api = FeishuAPI(feishu_settings.app_id, feishu_settings.app_secret)
                if message.message_id:
                    api.reply_text(message.message_id, response)
                else:
                    api.send_text("chat_id", message.chat_id, response)

            elif message.platform == "wecom":
                from app.channel.wecom import wecom_adapter as wc_adapter
                await wc_adapter.reply_to_message(message, response)

        except Exception as e:
            logger.error(f"Error sending response: {e}", exc_info=True)

    async def close_session(self, session_id: str):
        """Close and clean up a session manager."""
        if session_id in self._session_managers:
            await self._session_managers[session_id].close()
            del self._session_managers[session_id]


# Global singleton
channel_router = ChannelRouter()
