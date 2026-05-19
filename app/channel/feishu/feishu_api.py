# app/channel/feishu/feishu_api.py
import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody, ReplyMessageRequest, ReplyMessageRequestBody
from config.logging_config import get_logger
import json

logger = get_logger(__name__)


class FeishuAPI:
    """Feishu REST API client for sending messages."""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

    def send_message(self, receive_id_type: str, receive_id: str, msg_type: str, content: str) -> bool:
        """
        Send a message to a Feishu user or chat.

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

            response = self.client.im.v1.message.create(request)

            if response.success():
                logger.info(f"Feishu message sent successfully to {receive_id_type}:{receive_id}")
                return True
            else:
                logger.error(f"Feishu API error: code={response.code}, msg={response.msg}, log_id={response.get_log_id()}")
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

            response = self.client.im.v1.message.reply(request)

            if response.success():
                logger.info(f"Feishu reply sent successfully to message_id: {message_id}")
                return True
            else:
                logger.error(f"Feishu reply error: code={response.code}, msg={response.msg}, log_id={response.get_log_id()}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Feishu reply: {e}")
            return False

    def reply_text(self, message_id: str, text: str) -> bool:
        """Reply with text message in thread."""
        return self.reply_message(message_id, "text", text)