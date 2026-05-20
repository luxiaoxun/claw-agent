# app/channel/wecom/__init__.py
from app.channel.wecom.wecom_adapter import WeComAdapter, wecom_adapter
from app.channel.wecom.wecom_client import WeComClient
from app.channel.wecom.wecom_config import wecom_settings

__all__ = ["WeComAdapter", "WeComClient", "wecom_settings", "wecom_adapter"]