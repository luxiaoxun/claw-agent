import os
import sys
from typing import Optional, List
from pydantic_settings import BaseSettings
from dotenv import load_dotenv


def get_work_dir():
    """获取程序的工作目录（项目根目录）"""
    if getattr(sys, 'frozen', False):
        # 打包后的exe，返回exe所在目录
        return os.path.dirname(sys.executable)
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        work_dir = os.path.dirname(os.path.dirname(current_dir))
        return work_dir


# 根目录和工作目录
WORK_DIR = get_work_dir()
WORKSPACE_DIR = os.path.join(WORK_DIR, "workspace")

# 加载 .env 文件（从工作目录加载）
env_path = os.path.join(WORK_DIR, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()  # 使用默认路径


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "Claw Agent"
    APP_DESCRIPTION: str = "A simple AI agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 5000

    # LLM配置
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL: Optional[str] = os.getenv("OPENAI_BASE_URL")
    LLM_TEMPERATURE: float = 0.1

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
    AGENT_MAX_ITERATIONS: int = 10
    MSG_MAX_HISTORY_LENGTH: int = 10
    MSG_TOOL_OUTPUT_ENABLED: bool = os.getenv("MSG_TOOL_OUTPUT_ENABLED", "true").lower() == "true"

    # 安全配置
    HIGH_RISK_TOOLS: List[str] = ["block_ips"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
