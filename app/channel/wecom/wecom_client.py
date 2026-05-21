# app/channel/wecom/wecom_client.py
import asyncio
from aibot import WSClient, WSClientOptions, generate_req_id
from typing import Callable
from config.logging_config import get_logger

logger = get_logger(__name__)


class WeComClient:
    """
    WeCom WebSocket client using aibot SDK.
    Maintains a persistent connection to WeCom servers for receiving events.
    """

    def __init__(self, bot_id: str, bot_secret: str, event_handler: Callable):
        self.bot_id = bot_id
        self.bot_secret = bot_secret
        self.event_handler = event_handler  # Callback for received messages

        # Build WebSocket client
        self.ws_client = WSClient(
            WSClientOptions(
                bot_id=bot_id,
                secret=bot_secret,
                logger=logger,
            )
        )

        # Register event handlers
        self.ws_client.on('authenticated', self._on_authenticated)
        self.ws_client.on('message.text', self._on_text_message)
        self.ws_client.on('event.enter_chat', self._on_enter_chat)

    def _on_authenticated(self):
        """Called when authentication succeeds."""
        logger.info("WeCom client authenticated successfully")

    async def _on_text_message(self, frame):
        """Handle incoming text message."""
        try:
            logger.info(f"WeCom text message received: {frame}")

            # Call the user's event handler
            if self.event_handler:
                self.event_handler(frame)

        except Exception as e:
            logger.error(f"Error handling WeCom message: {e}", exc_info=True)

    async def _on_enter_chat(self, frame):
        """Handle enter chat event (welcome)."""
        try:
            logger.info(f"WeCom enter chat event: {frame}")
            await self.ws_client.reply_welcome(frame, {
                'msgtype': 'text',
                'text': {'content': '您好！我是智能助手，有什么可以帮您的吗？'},
            })
        except Exception as e:
            logger.error(f"Error handling WeCom enter_chat: {e}")

    def start(self):
        """Start the WeCom WebSocket client (blocking, runs in thread)."""
        try:
            self.ws_client.run()
            logger.info("WeCom WebSocket client started")
        except Exception as e:
            logger.error(f"Failed to start WeCom WebSocket client: {e}", exc_info=True)
            raise

    def stop(self):
        """Stop the WebSocket client."""
        try:
            self.ws_client.disconnect()
            self.ws_client = None
            logger.info("WeCom WebSocket client stopped")
        except Exception as e:
            logger.error(f"Error stopping WeCom WebSocket client: {e}")

    async def reply_stream(self, frame, stream_id: str, content: str, is_final: bool):
        """
        Send a stream reply to WeCom.

        Args:
            frame: Original message frame
            stream_id: Stream ID from generate_req_id()
            content: Text content to send
            is_final: True if this is the final message in the stream
        """
        try:
            await self.ws_client.reply_stream(frame, stream_id, content, is_final)
        except Exception as e:
            logger.error(f"Error sending WeCom stream reply: {e}")
