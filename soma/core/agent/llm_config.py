# core/agent/llm_config.py
from typing import Optional
from pydantic import BaseModel, Field
from soma.config.logging_config import get_logger

logger = get_logger(__name__)


class LLMConfig(BaseModel):
    """LLM 配置类，支持运行时动态更新"""
    model_provider: str = Field(default="openai", description="LLM provider: openai/anthropic/etc")
    model: str = Field(default="gpt-4", description="Model name")
    api_key: Optional[str] = Field(default=None, description="API Key")
    base_url: Optional[str] = Field(default=None, description="API base URL")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)

    def is_configured(self) -> bool:
        """检查必填配置是否完整"""
        return bool(self.api_key and self.model)

    @classmethod
    def from_settings(cls):
        """从 settings 加载默认配置"""
        from soma.config.settings import settings
        return cls(
            model_provider=settings.LLM_MODEL_PROVIDER,
            model=settings.LLM_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            temperature=settings.LLM_TEMPERATURE,
        )

    def to_dict(self) -> dict:
        """转 dict（隐藏 api_key 前4位）"""
        result = self.model_dump()
        if result.get("api_key") and len(result["api_key"]) > 4:
            result["api_key"] = result["api_key"][:4] + "***"
        return result

    def update_from_dict(self, data: dict):
        """从 dict 更新配置，只更新提供的字段"""
        if "model_provider" in data:
            self.model_provider = data["model_provider"]
        if "model" in data:
            self.model = data["model"]
        if "api_key" in data:
            self.api_key = data["api_key"]
        if "base_url" in data:
            self.base_url = data["base_url"]
        if "temperature" in data:
            self.temperature = data["temperature"]
