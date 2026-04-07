import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "Claw Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 5000

    # LLM配置
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    LLM_TEMPERATURE: float = 0.0

    # MCP配置
    USE_MCP: bool = os.getenv("USE_MCP", "false").lower() == "true"
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/sse")

    # Elasticsearch 连接配置
    ES_HOSTS: str = os.getenv("ES_HOSTS", "http://localhost:9200")
    ES_USERNAME: Optional[str] = os.getenv("ES_USERNAME")
    ES_PASSWORD: Optional[str] = os.getenv("ES_PASSWORD")
    ES_CA_CERTS: Optional[str] = os.getenv("ES_CA_CERTS")
    ES_TIMEOUT: int = int(os.getenv("ES_TIMEOUT", "30"))
    ES_MAX_RESULTS: int = int(os.getenv("ES_MAX_RESULTS", "100"))

    # Agent配置
    MAX_ITERATIONS: int = 10
    MAX_HISTORY_LENGTH: int = 10

    # 安全配置
    HIGH_RISK_TOOLS: List[str] = Field(
        default_factory=lambda: [
            "delete_document", "block_ips"
        ],
        description="高风险操作列表，需要用户确认"
    )

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
