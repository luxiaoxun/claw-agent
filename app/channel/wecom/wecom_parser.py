# app/channel/wecom/wecom_parser.py
from typing import Optional
from app.channel.base import NormalizedMessage


class WeComParser:
    """Parse WeCom events into NormalizedMessage format."""

    @staticmethod
    def parse(frame) -> Optional[NormalizedMessage]:
        """
        Parse a WeCom frame (from aibot SDK) into a NormalizedMessage.

        Single chat: chattype=single, from.userid=用户ID, no chatid
        Group chat: chattype=group, from.userid=发送者, chatid=群ID

        Returns:
            NormalizedMessage or None if the event should be ignored.
        """
        try:
            body = frame.get('body', {})

            # Chat type: 'single' or 'group'
            chattype = body.get('chattype', 'single')
            is_group = chattype == 'group'

            # Sender userid (same structure in both single and group)
            from_userid = body.get('from', {}).get('userid', '')

            # Group chat ID (only present in group chat)
            chat_id = body.get('chatid', '') if is_group else ''

            # Message ID
            message_id = body.get('msgid', '')

            # Content
            text_content = body.get('text', {}).get('content', '')
            msg_type = body.get('msgtype', 'text')

            return NormalizedMessage(
                platform="wecom",
                user_id=from_userid,
                chat_id=chat_id,  # empty string for single chat (uses user_id)
                message_id=message_id,
                message_type=msg_type,
                content=text_content,
                is_group=is_group,
                raw_payload={
                    "cmd": frame.get('cmd', ''),
                    "chattype": chattype,
                    "chatid": chat_id,
                    "msgtype": msg_type,
                    "from_userid": from_userid,
                }
            )

        except Exception as e:
            return None