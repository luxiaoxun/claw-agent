from fastapi import APIRouter, Request, HTTPException
from service.es_query_service import ElasticsearchQueryService
from config.logging_config import get_logger
from typing import Optional
from pydantic import BaseModel

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
        # 使用Pydantic模型自动验证，不需要手动解析JSON
        logger.info(f"测试查询API收到请求: {request.dict()}")

        # 直接await异步方法
        results = await query_service.execute_query(request.dict())

        # FastAPI自动序列化字典
        return results

    except Exception as e:
        logger.error(f"测试查询API失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/spl/parse")
async def test_spl_parse(request: ParseRequest):
    """
    测试SPL解析 - 查看SPL被解析成什么形式的ES查询DSL
    """
    try:
        spl = request.query

        query_dsl = query_service.parse_spl_to_elasticsearch(spl)

        return {
            "spl": spl,
            "elasticsearch_dsl": query_dsl
        }

    except Exception as e:
        logger.error(f"测试解析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
