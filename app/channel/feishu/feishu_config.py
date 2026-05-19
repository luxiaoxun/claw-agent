# app/channel/feishu/feishu_config.py
from pydantic_settings import BaseSettings
from typing import Optional


class FeishuSettings(BaseSettings):
    """Feishu/Lark configuration from environment variables."""

    app_id: str = ""
    app_secret: str = ""
    verification_token: str = ""
    encrypt_key: str = ""
    webhook_host: str = ""  # Public host for callbacks, e.g. https://your-domain.com

    # IM settings
    im_enabled: bool = False
    im_default_platform: str = "feishu"

    class Config:
        env_prefix = "FEISHU_"
        case_sensitive = False


feishu_settings = FeishuSettings()