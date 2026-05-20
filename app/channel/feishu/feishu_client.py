# app/channel/feishu/feishu_client.py
import lark_oapi as lark
from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody, CreateMessageRequest, \
    CreateMessageRequestBody
import json
from config.logging_config import get_logger
from typing import Callable

logger = get_logger(__name__)


class FeishuClient:
    """
    Feishu WebSocket client using lark-oapi 1.6.x ws.Client.
    Maintains a persistent connection to Feishu servers for receiving events.
    """

    def __init__(self, app_id: str, app_secret: str, event_handler: Callable):
        self.app_id = app_id
        self.app_secret = app_secret
        self.event_handler = event_handler  # Callback: do_p2_im_message_receive_v1 style

        # Build the SDK client for API calls
        self.sdk_client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

        # Build event dispatcher handler
        self.event_dispatcher = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._on_p2_im_message_receive)
            .build()
        )

        # Build WebSocket/WS client for long-poll connection
        self.ws_client = None

    def _on_p2_im_message_receive(self, data: "lark.P2ImMessageReceiveV1") -> None:
        """
        Handle incoming P2P/group message event.
        data is P2ImMessageReceiveV1 from lark-oapi 1.6.x.
        """
        try:
            logger.info(
                f"Feishu message received: {data.event.message.message_id if data.event.message else 'no message'}")

            # Call the user's event handler
            if self.event_handler:
                self.event_handler(data)

        except Exception as e:
            logger.error(f"Error handling Feishu message: {e}", exc_info=True)

    def start(self):
        """Start the WebSocket client (long-poll connection to Feishu) in a separate thread."""
        import threading
        try:
            self.ws_client = lark.ws.Client(
                self.app_id,
                self.app_secret,
                event_handler=self.event_dispatcher,
                log_level=lark.LogLevel.INFO,
            )

            def run():
                import asyncio
                # Replace the module-level loop so start() uses our fresh loop
                import lark_oapi.ws.client as ws_module
                fresh_loop = asyncio.new_event_loop()
                ws_module.loop = fresh_loop
                asyncio.set_event_loop(fresh_loop)
                try:
                    self.ws_client.start()
                except Exception as e:
                    logger.error(f"Feishu WebSocket error: {e}")
                finally:
                    fresh_loop.close()
                    ws_module.loop = None

            self._thread = threading.Thread(target=run, daemon=True)
            self._thread.start()
            logger.info("Feishu WebSocket client started in background thread")
        except Exception as e:
            logger.error(f"Failed to start Feishu WebSocket client: {e}", exc_info=True)
            raise

    def stop(self):
        """Stop the Feishu WebSocket client."""
        try:
            if hasattr(self, '_thread') and self._thread:
                self._thread = None
            self.ws_client = None
            logger.info("Feishu WebSocket client stopped")
        except Exception as e:
            logger.error(f"Error stopping Feishu WebSocket client: {e}")

    def send_message(self, receive_id_type: str, receive_id: str, msg_type: str, content: str) -> bool:
        """
        Send a message to a Feishu chat.

        Args:
            receive_id_type: "open_id", "user_id", "union_id", "chat_id"
            receive_id: Target ID
            msg_type: Message type (text, image, etc.)
            content: Message content (JSON string for text, etc.)

        Returns:
            True if sent successfully, False otherwise.
        """
        try:
            request = (
                CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(receive_id)
                    .msg_type(msg_type)
                    .content(content)
                    .build()
                )
                .build()
            )

            response = self.sdk_client.im.v1.message.create(request)

            if response.success():
                logger.info(f"Feishu message sent successfully to {receive_id_type}:{receive_id}")
                return True
            else:
                logger.error(
                    f"Feishu API error: code={response.code}, msg={response.msg}, log_id={response.get_log_id()}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Feishu message: {e}")
            return False

    def send_text(self, receive_id_type: str, receive_id: str, text: str) -> bool:
        """Send a text message."""
        content = json.dumps({"text": text})
        return self.send_message(receive_id_type, receive_id, "text", content)

    def reply_message(self, message_id: str, msg_type: str, content: str) -> bool:
        """
        Reply to a specific message (in thread).

        Args:
            message_id: The message ID to reply to
            msg_type: Message type (text, image, etc.)
            content: Message content

        Returns:
            True if sent successfully, False otherwise.
        """
        try:
            if msg_type == "text":
                content = json.dumps({"text": content})

            request = (
                ReplyMessageRequest.builder()
                .message_id(message_id)
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .msg_type(msg_type)
                    .content(content)
                    .build()
                )
                .build()
            )

            response = self.sdk_client.im.v1.message.reply(request)

            if response.success():
                logger.info(f"Feishu reply sent successfully to message_id: {message_id}")
                return True
            else:
                logger.error(
                    f"Feishu reply error: code={response.code}, msg={response.msg}, log_id={response.get_log_id()}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Feishu reply: {e}")
            return False

    def reply_text(self, message_id: str, text: str) -> bool:
        """Reply with text message in thread."""
        return self.reply_message(message_id, "text", text)
