# app/channel/wecom/wecom_config.py
from pydantic_settings import BaseSettings


class WeComSettings(BaseSettings):
    """WeCom/企业微信 configuration from environment variables."""

    bot_id: str = ""
    bot_secret: str = ""

    class Config:
        env_prefix = "WECHAT_"
        case_sensitive = False


wecom_settings = WeComSettings()