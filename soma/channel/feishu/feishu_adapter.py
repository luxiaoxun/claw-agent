# soma/channel/feishu/feishu_adapter.py
from typing import Callable
from soma.channel.base import IChannelAdapter, NormalizedMessage, IMContext
from soma.channel.feishu.feishu_client import FeishuClient
from soma.config.logging_config import get_logger

logger = get_logger(__name__)


class FeishuAdapter(IChannelAdapter):
    """
    Feishu/Lark channel adapter implementing IChannelAdapter.
    Uses the lark-oapi ws.Client for event receiving (long connection).
    """

    def __init__(self):
        self._client: FeishuClient = None
        self._started = False
        self._channel_id: int = None
        self._config: dict = None

    @property
    def platform_name(self) -> str:
        return "feishu"

    def start(self):
        """Start the Feishu WebSocket client using config from DB or env."""
        if self._started:
            return

        app_id = None
        app_secret = None

        # Use config from DB if available
        if self._config:
            app_id = self._config.get('app_id')
            app_secret = self._config.get('app_secret')

        if not app_id or not app_secret:
            logger.warning("Feishu app_id or app_secret not configured, skipping start")
            return

        self._client = FeishuClient(
            app_id=app_id,
            app_secret=app_secret,
            event_handler=self._on_feishu_event
        )
        self._client.start()
        self._started = True
        logger.info("FeishuAdapter started")

    def start_with_config(self, config: dict):
        """Start with config from database."""
        self._config = config
        self.start()

    def stop(self):
        """Stop the Feishu WebSocket client."""
        if self._client:
            self._client.stop()
            self._started = False
            logger.info("FeishuAdapter stopped")

    def send_message(self, chat_id: str, content: str, msg_type: str = "text") -> bool:
        """
        Send a message to a Feishu chat.
        For p2p chat, use open_id as receive_id; for group, use chat_id.
        """
        if not self._client:
            logger.error("Feishu client not started")
            return False

        return self._client.send_text("chat_id", chat_id, content)

    def _on_feishu_event(self, data: "lark.P2ImMessageReceiveV1"):
        """
        Callback when Feishu sends a P2P message event.
        Parses the raw data into NormalizedMessage and routes to ChannelRouter.

        Args:
            data: P2ImMessageReceiveV1 event from lark-oapi
        """
        from soma.channel.router import channel_router
        from soma.channel.feishu.feishu_parser import FeishuParser

        try:
            # Parse Feishu event into NormalizedMessage
            normalized = FeishuParser.parse(data)
            if not normalized:
                logger.warning(f"Could not parse Feishu event: {data}")
                return

            logger.info(
                f"Feishu event: user={normalized.user_id}, chat={normalized.chat_id}, content={normalized.content[:50]}...")

            # Route the message asynchronously (non-blocking for Feishu event callback)
            import asyncio
            asyncio.create_task(channel_router.route_message(normalized))

        except Exception as e:
            logger.error(f"Error handling Feishu event: {e}", exc_info=True)

    def get_event_handler(self) -> Callable:
        """Return the event handler for this adapter."""
        return self._on_feishu_event
