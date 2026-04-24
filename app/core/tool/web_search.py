from typing import Optional, Dict, Any, List
from langchain.tools import tool
from pydantic import BaseModel, Field
from itertools import islice
from ddgs import DDGS
from config.logging_config import get_logger

logger = get_logger(__name__)


class WebSearchInput(BaseModel):
    """Web搜索工具的输入参数模型"""
    query: str = Field(
        description="搜索关键词，如: '东南大学' 或 'Python教程'"
    )
    max_results: int = Field(
        default=10,
        description="最大结果数，范围1-50，默认10"
    )
    timeout: Optional[int] = Field(
        default=30,
        description="请求超时时间（秒），默认30秒"
    )


@tool("web_search", args_schema=WebSearchInput)
async def web_search(
        query: str,
        max_results: int = 10,
        timeout: int = 30
) -> Dict[str, Any]:
    """
    Search the web using web search engine.

    This tool performs web searches and returns relevant results including titles, URLs, and snippets.
    Useful for finding current information, news, documentation, and general web content.

    Usage:
        Search for information on the web based on keywords. Results include title, URL, and body text.

    Args:
        query: Search keywords, e.g., '东南大学' or 'Python tutorial'
        max_results: Maximum number of results to return, range 1-50, default 10
        timeout: Request timeout in seconds, default 30
    """
    try:
        logger.info(f"Web search - query: '{query}', max_results: {max_results}, timeout: {timeout}s")

        # 固定参数（使用默认值）
        region = "wt-wt"  # 全球搜索
        safesearch = "off"  # 关闭安全搜索
        timelimit = "y"  # 过去一年的内容

        # 参数验证
        if max_results < 1 or max_results > 50:
            max_results = 10
            logger.warning(f"max_results out of range, set to default 10")

        # 设置超时时间（秒）
        timeout_seconds = timeout if timeout > 0 else 30

        # 执行搜索
        results = []
        try:
            # 方法1: 在 DDGS 初始化时设置超时
            with DDGS(timeout=timeout_seconds) as ddgs:
                ddgs_gen = ddgs.text(
                    query,
                    region=region,
                    safesearch=safesearch,
                    timelimit=timelimit
                )
                for r in islice(ddgs_gen, max_results):
                    results.append(r)
        except TimeoutError as e:
            logger.error(f"Search timeout after {timeout_seconds}s: {e}")
            return {
                "query": query,
                "success": False,
                "error": f"Search timeout after {timeout_seconds} seconds. Please try again later or reduce max_results.",
                "results": []
            }
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return {
                "query": query,
                "success": False,
                "error": f"Search failed: {str(e)}",
                "results": []
            }

        if not results:
            logger.info(f"No results found for query: {query}")
            return {
                "query": query,
                "success": True,
                "total_results": 0,
                "results": []
            }

        # 格式化输出结果
        formatted_results = []
        for result in results:
            formatted_result = {
                "title": result.get("title", ""),
                "url": result.get("href", result.get("url", "")),
                "snippet": result.get("body", result.get("snippet", "")),
            }
            # 添加可选的额外信息
            if "source" in result:
                formatted_result["source"] = result["source"]
            formatted_results.append(formatted_result)

        logger.info(f"Search completed - found {len(formatted_results)} results")

        return {
            "query": query,
            "success": True,
            "total_results": len(formatted_results),
            "results": formatted_results
        }

    except Exception as e:
        logger.error(f"Web search error: {e}")
        return {
            "query": query,
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "results": []
        }


if __name__ == "__main__":
    result = web_search.invoke("东南大学", max_results=5)
    print(f"搜索完成: {result['total_results']} 个结果")
    for r in result['results']:
        print(f"\n标题: {r['title']}")
        print(f"链接: {r['url']}")
        print(f"摘要: {r['snippet'][:100]}...")
