from core.tools.es_search_data_tool import SearchDataTool
from config.logging_config import get_logger

logger = get_logger(__name__)


# 工具工厂函数
def create_local_es_tools():
    """创建本地Elasticsearch工具列表"""
    logger.info("创建本地Elasticsearch工具")
    return [
        SearchDataTool()
    ]
