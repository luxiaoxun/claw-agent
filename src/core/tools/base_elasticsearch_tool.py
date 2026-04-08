from typing import Any, Dict, Optional, Type
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from clients.elasticsearch_client import get_es_client
import asyncio


class BaseElasticsearchTool(BaseTool):
    """Elasticsearch工具基类"""

    # 定义Pydantic模型字段
    name: str = Field(description="工具名称")
    description: str = Field(description="工具描述")
    args_schema: Optional[Type[BaseModel]] = None

    @property
    def es_client(self):
        """获取ES客户端"""
        return get_es_client()

    def _run(self, *args, **kwargs) -> str:
        """同步执行方法 - 必须实现，但我们可以委托给异步方法"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(self._arun(*args, **kwargs))
        finally:
            if not loop.is_running():
                loop.close()

    # _arun 方法由子类实现
    async def _arun(self, *args, **kwargs) -> str:
        """
        异步执行方法 - 子类必须实现
        """
        raise NotImplementedError("子类必须实现 _arun 方法")
