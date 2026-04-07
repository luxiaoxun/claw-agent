from elasticsearch import AsyncElasticsearch
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class ElasticsearchClient:
    """Elasticsearch客户端管理器 - 单例模式，只用异步客户端"""
    _instance = None
    _async_client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._async_client is None:
            self._init_client()

    def _init_client(self):
        """初始化异步Elasticsearch客户端"""
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

        self._async_client = AsyncElasticsearch(**client_config)
        logger.info(f"Connected to Elasticsearch (async): {hosts}")

    @property
    def async_client(self):
        return self._async_client

    async def close(self):
        """关闭异步客户端连接"""
        if self._async_client:
            await self._async_client.close()


# 创建全局异步客户端实例
_es_client_instance = None


def get_es_client():
    """获取全局ES异步客户端实例"""
    global _es_client_instance
    if _es_client_instance is None:
        _es_client_instance = ElasticsearchClient()
    return _es_client_instance
