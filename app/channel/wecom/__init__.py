# app/channel/wecom/__init__.py
from app.channel.wecom.wecom_adapter import WeComAdapter, wecom_adapter
from app.channel.wecom.wecom_client import WeComClient

__all__ = ["WeComAdapter", "WeComClient", "wecom_adapter"]
