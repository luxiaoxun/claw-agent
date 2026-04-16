# web/routers/query_router.py
from fastapi import APIRouter
from service.es_query_service import ElasticsearchQueryService
from config.logging_config import get_logger
from typing import Optional
from pydantic import BaseModel
from common.response import success_response, fail_response

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["query"])

# 创建查询服务实例
query_service = ElasticsearchQueryService()


# 定义请求模型
class QueryRequest(BaseModel):
    timeType: int = 1
    timeLimit: Optional[str] = None
    query: str
    indexName: str
    pageNum: int = 1
    pageSize: int = 10


class ParseRequest(BaseModel):
    query: str


@router.post("/data")
async def es_query(request: QueryRequest):
    """
    测试查询API - 直接使用SPL查询Elasticsearch，不经过AI

    请求体格式：
    {
        "timeType": 5,
        "timeLimit": "2026-03-16 00:00:00,2026-03-16 23:59:59",
        "query": "(src_ip >= 172.19.1.1 and src_ip < 172.19.1.25) and ...",
        "indexName": "xdr_tdp_event",
        "pageNum": 1,
        "pageSize": 10
    }
    """
    try:
        logger.info(f"测试查询API收到请求: {request.dict()}")

        # 直接await异步方法
        result = await query_service.execute_query(request.dict())

        # 检查查询结果是否成功
        if result.get("error") is not None:
            return fail_response(
                message=result.get("error")
            )
        else:
            return success_response(
                data=result
            )

    except Exception as e:
        logger.error(f"测试查询API失败: {str(e)}")
        return fail_response()


@router.post("/spl/parse")
async def test_spl_parse(request: ParseRequest):
    """
    测试SPL解析 - 查看SPL被解析成什么形式的ES查询DSL
    """
    try:
        spl = request.query
        logger.info(f"测试SPL解析: {spl}")

        query_dsl = query_service.parse_spl_to_elasticsearch(spl)

        parse_data = {
            "spl": spl,
            "elasticsearch_dsl": query_dsl
        }

        return success_response(
            data=parse_data,
            message="SPL解析成功"
        )

    except Exception as e:
        logger.error(f"测试SPL解析失败: {str(e)}")
        return fail_response()
