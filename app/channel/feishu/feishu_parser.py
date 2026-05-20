# app/channel/feishu/feishu_parser.py
import lark_oapi as lark
import json
from typing import Optional
from app.channel.base import NormalizedMessage


class FeishuParser:
    """Parse Feishu P2ImMessageReceiveV1 events into NormalizedMessage format."""

    @staticmethod
    def parse(data: "lark.P2ImMessageReceiveV1") -> Optional[NormalizedMessage]:
        """
        Parse a Feishu P2ImMessageReceiveV1 event into a NormalizedMessage.

        Args:
            data: P2ImMessageReceiveV1 event from lark-oapi (from feishu_test.py)

        Returns:
            NormalizedMessage or None if the event should be ignored.
        """
        try:
            event = data.event
            if not event or not event.message:
                return None

            message = event.message

            # Determine chat type - chat_type is on message, not event
            chat_type = getattr(message, 'chat_type', None)
            is_group = chat_type == "group" if chat_type else False

            # Extract content based on message type
            content = ""
            msg_type = getattr(message, 'message_type', None) or "text"

            if msg_type == "text":
                try:
                    content_obj = json.loads(message.content)
                    content = content_obj.get("text", "")
                except Exception:
                    content = message.content or ""
            elif msg_type in ("image", "file", "audio", "media"):
                content = f"[{msg_type.upper()}消息]"
            elif msg_type == "post":
                content = "[富文本消息]"
            elif msg_type == "share_chat":
                content = "[转发消息]"
            else:
                content = message.content or ""

            # Extract user_id from sender.sender_id.open_id
            user_id = ""
            sender = getattr(event, 'sender', None)
            if sender and hasattr(sender, 'sender_id'):
                sender_id = sender.sender_id
                user_id = getattr(sender_id, 'open_id', None) or getattr(sender_id, 'user_id', None) or ""

            return NormalizedMessage(
                platform="feishu",
                user_id=user_id,
                chat_id=getattr(message, 'chat_id', None) or "",
                message_id=getattr(message, 'message_id', None) or "",
                message_type=msg_type,
                content=content,
                is_group=is_group,
                raw_payload={
                    "event": "P2ImMessageReceiveV1",
                    "chat_type": chat_type,
                    "message_type": msg_type,
                }
            )

        except Exception as e:
            return None
