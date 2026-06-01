# soma/channel/wecom/wecom_adapter.py
from typing import Callable
from soma.channel.base import IChannelAdapter, NormalizedMessage
from soma.channel.wecom.wecom_client import WeComClient
from soma.config.logging_config import get_logger

logger = get_logger(__name__)


class WeComAdapter(IChannelAdapter):
    """
    WeCom/企业微信 channel adapter implementing IChannelAdapter.
    Uses the aibot SDK WebSocket client for event receiving.
    """

    def __init__(self):
        self._client: WeComClient = None
        self._started = False
        self._frame_cache: dict = {}
        self._channel_id: int = None
        self._config: dict = None

    @property
    def platform_name(self) -> str:
        return "wecom"

    def start(self):
        """Start the WeCom WebSocket client using config from DB or env."""
        if self._started:
            return

        bot_id = None
        bot_secret = None

        if self._config:
            bot_id = self._config.get('bot_id')
            bot_secret = self._config.get('bot_secret')

        if not bot_id or not bot_secret:
            logger.warning("WeCom bot_id or bot_secret not configured, skipping start")
            return

        self._client = WeComClient(
            bot_id=bot_id,
            bot_secret=bot_secret,
            event_handler=self._on_wecom_event
        )
        import threading
        self._thread = threading.Thread(target=self._client.start, daemon=True)
        self._thread.start()
        self._started = True
        logger.info("WeComAdapter started")

    def start_with_config(self, config: dict):
        """Start with config from database."""
        self._config = config
        self.start()

    def stop(self):
        """Stop the WeCom WebSocket client."""
        if self._client:
            self._client.stop()
            self._started = False
            logger.info("WeComAdapter stopped")

    def send_message(self, chat_id: str, content: str, msg_type: str = "text") -> bool:
        """
        Send a message to WeCom chat.
        For group chat, chat_id is roomid.
        """
        return False

    def _on_wecom_event(self, frame):
        """
        Callback when WeCom sends an event.
        Parses the raw frame into NormalizedMessage and routes to ChannelRouter.

        Args:
            frame: WeCom frame from aibot SDK
        """
        from soma.channel.router import channel_router
        from soma.channel.wecom.wecom_parser import WeComParser

        try:
            normalized = WeComParser.parse(frame)
            if not normalized:
                logger.warning(f"Could not parse WeCom event: {frame}")
                return

            if not normalized.content:
                logger.info(f"WeCom event has no content (may be system event): {frame.get('type')}")
                return

            logger.info(
                f"WeCom event: user_id={normalized.user_id}, chat_id={normalized.chat_id}, content={normalized.content[:50]}...")

            # Cache frame for response routing
            msg_id = normalized.message_id or f"{normalized.user_id}_{normalized.chat_id}"
            self._frame_cache[msg_id] = frame

            import asyncio
            asyncio.create_task(channel_router.route_message(normalized))

        except Exception as e:
            logger.error(f"Error handling WeCom event: {e}", exc_info=True)

    async def reply_to_message(self, message: NormalizedMessage, response: str):
        """Reply to a WeCom message using the cached frame."""
        try:
            if not self._client or not self._client.ws_client:
                logger.error("WeCom client not initialized")
                return

            msg_id = message.message_id or f"{message.user_id}_{message.chat_id}"
            frame = self._frame_cache.get(msg_id)
            stream_id = f"wecom_{msg_id}"

            await self._client.ws_client.reply_stream(frame, stream_id, response, True)

            # Clean up cached frame
            if msg_id in self._frame_cache:
                del self._frame_cache[msg_id]

        except Exception as e:
            logger.error(f"Error sending WeCom reply: {e}", exc_info=True)

    def get_event_handler(self) -> Callable:
        """Return the event handler for this adapter."""
        return self._on_wecom_event


# Global singleton - used by router.py
wecom_adapter = WeComAdapter()
