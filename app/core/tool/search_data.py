from typing import Optional, Type, Dict, Any
from pydantic import BaseModel, Field

from core.tool.base.base_elasticsearch_tool import BaseElasticsearchTool
from config.logging_config import get_logger

logger = get_logger(__name__)


class SearchDataInput(BaseModel):
    """搜索文档工具的输入参数模型"""

    indexName: str = Field(
        description="索引类型: event(日志)/attack(告警)/incident(安全事件)"
    )

    query: str = Field(
        default="",
        description="SPL查询语句，如: src_ip:172.17.6.1 AND severity>=3"
    )

    timeType: int = Field(
        default=1,
        description="时间范围: 1=今日,2=近7天,3=近14天,4=近30天,5=自定义"
    )

    timeLimit: Optional[str] = Field(
        default=None,
        description="自定义时间，格式: '2026-03-16 00:00:00,2026-03-16 23:59:59'，仅当timeType=5时使用"
    )

    pageNum: int = Field(
        default=1,
        description="页码，从1开始"
    )

    pageSize: int = Field(
        default=10,
        description="每页数量，建议不超过20"
    )

    sortField: Optional[str] = Field(
        default=None,
        description="排序字段，如: severity"
    )

    sortOrder: str = Field(
        default="desc",
        description="排序方向: desc降序/asc升序"
    )


class SearchDataTool(BaseElasticsearchTool):
    """
    搜索Elasticsearch数据工具。
    支持日志、告警、安全事件三种数据源，使用SPL语法查询。
    """

    # 工具元数据 - 精简但关键
    name: str = "search_data"
    description: str = (
        "搜索日志/告警/安全事件。"
        "参数: indexName(数据源), query(SPL语句), timeType(时间范围), pageNum(页码), pageSize(每页数)"
    )
    args_schema: Type[BaseModel] = SearchDataInput

    def __init__(self, **kwargs):
        # 直接调用父类__init__，不需要传入参数
        # 父类会自动从类属性中获取name和description
        super().__init__(**kwargs)

    async def _arun(
            self,
            indexName: str,
            query: str = "",
            timeType: int = 1,
            timeLimit: Optional[str] = None,
            pageNum: int = 1,
            pageSize: int = 10,
            sortField: Optional[str] = None,
            sortOrder: str = "desc",
            **kwargs
    ) -> Dict[str, Any]:
        """
        执行搜索
        """
        try:
            logger.info(f"Search data - index:{indexName}, time:{timeType}, page:{pageNum}/{pageSize}")

            from service.es_query_service import ElasticsearchQueryService
            query_service = ElasticsearchQueryService()

            # 映射indexName到完整索引名
            index_mapping = {
                "event": "xdr_tdp_event",
                "attack": "xdr_tdp_attack",
                "incident": "xdr_tdp_incident"
            }
            full_index = index_mapping.get(indexName, indexName)

            params = {
                "indexName": full_index,
                "query": query,
                "timeType": timeType,
                "timeLimit": timeLimit,
                "pageNum": pageNum,
                "pageSize": pageSize
            }

            if sortField:
                params["sortField"] = sortField
                params["sortOrder"] = sortOrder

            results = await query_service.execute_query(params)

            if "error" in results:
                return {"spl": query, "result": {"error": results["error"]}}

            return {
                "spl": query,
                "result": {
                    "total": results.get("total", 0),
                    "hits": results.get("hits", [])[:pageSize],
                    "page": pageNum,
                    "page_size": pageSize
                }
            }

        except Exception as e:
            logger.error(f"Search error: {e}")
            return {"spl": query, "result": {"error": str(e)}}
