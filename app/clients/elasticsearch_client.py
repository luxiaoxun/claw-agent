from elasticsearch import Elasticsearch
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class ElasticsearchClient:
    """Elasticsearch客户端管理器 - 单例模式，使用同步客户端"""
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._init_client()

    def _init_client(self):
        """初始化同步Elasticsearch客户端"""
        hosts = [host.strip() for host in settings.ES_HOSTS.split(",")]

        client_config = {
            "hosts": hosts,
            "timeout": settings.ES_TIMEOUT,
            "max_retries": 3,
            "retry_on_timeout": True
        }

        # 添加认证
        if settings.ES_USERNAME and settings.ES_PASSWORD:
            client_config["basic_auth"] = (settings.ES_USERNAME, settings.ES_PASSWORD)

        # 添加SSL配置
        if settings.ES_CA_CERTS:
            client_config["ca_certs"] = settings.ES_CA_CERTS
            client_config["verify_certs"] = True
        else:
            client_config["verify_certs"] = False
            client_config["ssl_show_warn"] = False

        self._client = Elasticsearch(**client_config)
        logger.info(f"Connected to Elasticsearch (sync): {hosts}")

    @property
    def client(self):
        return self._client

    def close(self):
        """关闭同步客户端连接"""
        if self._client:
            self._client.close()


# 创建全局同步客户端实例
_es_client_instance = None


def get_es_client():
    """获取全局ES同步客户端实例"""
    global _es_client_instance
    if _es_client_instance is None:
        _es_client_instance = ElasticsearchClient()
    return _es_client_instance