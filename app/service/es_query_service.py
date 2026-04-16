from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from clients.elasticsearch_client import ElasticsearchClient
from config.settings import settings
from config.logging_config import get_logger
import re
import json

logger = get_logger(__name__)


# 时间类型枚举
class TimeType:
    TODAY = 1
    RECENT_7_DAY = 2
    RECENT_14_DAY = 3
    RECENT_30_DAY = 4
    CUSTOM = 5


class ElasticsearchQueryService:
    """Elasticsearch查询服务"""

    def __init__(self):
        self.es_client = ElasticsearchClient()

    async def execute_query(self, params: Dict) -> Dict:
        """
        执行Elasticsearch查询

        Args:
            params: 查询参数，支持以下字段：
                - indexName: 索引类型
                - query: SPL查询语句
                - timeType: 时间类型
                - timeLimit: 自定义时间范围
                - pageNum: 页码
                - pageSize: 每页数量
                - sortField: 排序字段（可选）
                - sortOrder: 排序方式 asc/desc（可选，默认desc）
                - timeField: 时间字段（可选，自动获取）

        Returns:
            查询结果
        """
        try:
            # 解析参数
            time_type = params.get("timeType", TimeType.CUSTOM)
            time_limit = params.get("timeLimit")
            raw_spl = params.get("query", "")
            index_name = params.get("indexName")
            page_num = params.get("pageNum", 1)
            page_size = min(params.get("pageSize", 10), settings.ES_MAX_RESULTS)

            # 排除字段参数
            exclude_fields = params.get("excludeFields", ["payload2s", "payload2c"])

            # 排序参数
            sort_field = params.get("sortField")  # 可选
            sort_order = params.get("sortOrder", "desc").lower()  # 默认降序

            if not index_name:
                return {"error": "必须提供索引名称"}

            # 1. 预处理SPL
            processed_spl = self._preprocess_spl_for_es(raw_spl)

            # 2. 获取索引模式和时间字段
            index_pattern = self._get_index_pattern(index_name)
            time_field = self._get_index_time_field(index_name)
            start_time, end_time = self._parse_time_range(time_type, time_limit)

            # 3. 构建最终的 query_string 查询
            time_query_part = f"{time_field}: [{start_time} TO {end_time}]"

            if processed_spl and processed_spl != "*":
                final_query_string = f"({time_query_part}) AND ({processed_spl})"
            else:
                final_query_string = time_query_part

            # 4. 构建排序规则
            sort_rules = []

            if sort_field:
                # 使用用户指定的排序字段
                sort_rules.append({sort_field: {"order": sort_order}})
                logger.debug(f"使用自定义排序: {sort_field} {sort_order}")
            else:
                # 默认按时间字段降序
                sort_rules.append({time_field: {"order": "desc"}})
                logger.debug(f"使用默认时间排序: {time_field} desc")

            # 5. 构建搜索请求体
            from_ = (page_num - 1) * page_size
            search_body = {
                "query": {
                    "query_string": {
                        "query": final_query_string,
                        "default_operator": "AND",
                        "analyze_wildcard": True
                    }
                },
                "size": page_size,
                "from": from_,
                "sort": sort_rules,
                "track_total_hits": True  # 准确统计总数
            }

            # 添加字段排除功能
            if exclude_fields:
                # 使用 _source 排除指定字段
                search_body["_source"] = {
                    "excludes": exclude_fields
                }
                logger.debug(f"排除字段: {exclude_fields}")

            logger.info(f"执行 query_string 查询 - 索引: {index_pattern}")
            logger.info(f"最终 search_body: {search_body}")

            # 6. 执行搜索
            response = self.es_client.client.search(
                index=index_pattern,
                body=search_body
            )

            return {
                "total": response['hits']['total']['value'],
                "hits": response['hits']['hits'],
                "page_num": page_num,
                "page_size": page_size,
                "sort": sort_rules
            }

        except Exception as e:
            logger.error(f"查询执行失败: {str(e)}")
            return {"error": f"查询执行失败: {str(e)}"}

    def _preprocess_spl_for_es(self, raw_spl: str) -> str:
        """
        将原始SPL语句预处理为Elasticsearch query_string兼容的格式
        修复look-behind错误
        """
        if not raw_spl or not raw_spl.strip():
            return "*"

        query = raw_spl

        # 1. id字段处理
        query = re.sub(r'\bid\b\s*:', '_id:', query)

        # 2. 逻辑操作符大写
        query = re.sub(r'\s+and\s+', ' AND ', query, flags=re.IGNORECASE)
        query = re.sub(r'\s+or\s+', ' OR ', query, flags=re.IGNORECASE)
        query = re.sub(r'\s+not\s+', ' NOT ', query, flags=re.IGNORECASE)
        query = re.sub(r'^not\s+', 'NOT ', query, flags=re.IGNORECASE)

        # 3. 移除范围操作符后的空格 - 分开处理避免变长后顾断言
        # 处理 >= 后的空格
        query = re.sub(r'(>=)\s+', r'\1', query)
        # 处理 > 后的空格
        query = re.sub(r'(>)\s+', r'\1', query)
        # 处理 <= 后的空格
        query = re.sub(r'(<=)\s+', r'\1', query)
        # 处理 < 后的空格
        query = re.sub(r'(<)\s+', r'\1', query)

        # 4. 为前面没有冒号的范围操作符添加冒号
        # 使用多个正则表达式分开处理
        # 处理 >=
        query = re.sub(r'(?<!:)(>=)', r':\1', query)
        # 处理 >
        query = re.sub(r'(?<!:)(>)(?![:=])', r':\1', query)  # 确保不是>=的一部分
        # 处理 <=
        query = re.sub(r'(?<!:)(<=)', r':\1', query)
        # 处理 <
        query = re.sub(r'(?<!:)(<)(?!=)', r':\1', query)  # 确保不是<=的一部分

        # 清理空格
        query = re.sub(r'\s+', ' ', query).strip()

        return query

    def _parse_time_range(self, time_type: int, time_limit: str = None) -> Tuple[int, int]:
        """
        解析时间范围

        Args:
            time_type: 时间类型枚举
            time_limit: 自定义时间范围 "start,end" (格式为时间戳或日期字符串)

        Returns:
            (开始时间毫秒值, 结束时间毫秒值) 的元组
        """
        now = datetime.now()

        if time_type == TimeType.TODAY:
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            return int(start_time.timestamp() * 1000), int(end_time.timestamp() * 1000)

        elif time_type == TimeType.RECENT_7_DAY:
            start_time = now - timedelta(days=7)
            return int(start_time.timestamp() * 1000), int(now.timestamp() * 1000)

        elif time_type == TimeType.RECENT_14_DAY:
            start_time = now - timedelta(days=14)
            return int(start_time.timestamp() * 1000), int(now.timestamp() * 1000)

        elif time_type == TimeType.RECENT_30_DAY:
            start_time = now - timedelta(days=30)
            return int(start_time.timestamp() * 1000), int(now.timestamp() * 1000)

        elif time_type == TimeType.CUSTOM and time_limit:
            parts = time_limit.split(',')
            if len(parts) == 2:
                # 尝试解析自定义时间范围
                try:
                    # 如果是数字，直接作为毫秒时间戳
                    if parts[0].strip().isdigit() and parts[1].strip().isdigit():
                        return int(parts[0].strip()), int(parts[1].strip())
                    else:
                        # 如果是日期字符串，转换为毫秒时间戳
                        start_dt = datetime.strptime(parts[0].strip(), "%Y-%m-%d %H:%M:%S")
                        end_dt = datetime.strptime(parts[1].strip(), "%Y-%m-%d %H:%M:%S")
                        return int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)
                except ValueError:
                    pass

        # 默认返回最近24小时
        start_time = now - timedelta(hours=24)
        return int(start_time.timestamp() * 1000), int(now.timestamp() * 1000)

    def _get_index_pattern(self, index_name: str) -> str:
        """
        根据索引名称获取实际的索引模式

        Args:
            index_name: 输入的索引名称（如 xdr_tdp_event）

        Returns:
            实际的索引模式（如 xdr_tdp_event-*）
        """
        index_patterns = {
            "xdr_tdp_event": "xdr_tdp_event-*",
            "xdr_tdp_attack": "xdr_tdp_attack-*",
            "xdr_tdp_incident": "xdr_tdp_incident-*"
        }
        return index_patterns.get(index_name, f"{index_name}-*")

    def _get_index_time_field(self, index_name: str) -> str:
        """
        根据索引名称获取实际的时间字段

        Args:
            index_name: 输入的索引名称（如 xdr_tdp_event）

        Returns:
            实际的时间字段（如 event_time）
        """
        index_patterns = {
            "xdr_tdp_event": "event_time",
            "xdr_tdp_attack": "end_time",
            "xdr_tdp_incident": "end_time"
        }
        return index_patterns.get(index_name, "event_time")

    def parse_spl_to_elasticsearch(self, spl_query: str) -> str:
        """
        将SPL语句转换为Elasticsearch查询DSL

        Args:
            spl_query: SPL查询语句

        Returns:
            Elasticsearch查询DSL
        """
        if not spl_query or spl_query.strip() == "":
            return ""
        processed_spl = self._preprocess_spl_for_es(spl_query)
        return processed_spl

    def format_results(self, results: Dict, max_fields: int = 5) -> str:
        """格式化查询结果为可读文本"""
        if "error" in results:
            return results["error"]

        total = results["total"]
        hits = results["hits"]
        page_num = results["page_num"]
        page_size = results["page_size"]

        if total == 0:
            return f"没有找到匹配的文档"

        lines = [
            f"找到 {total} 个文档（第{page_num}页，每页{page_size}条，显示前{len(hits)}个）:\n"
        ]

        for i, hit in enumerate(hits, 1):
            source = hit['_source']
            index = hit.get('_index', 'unknown')

            # 简化显示
            simplified = {}
            for key, value in list(source.items())[:max_fields]:
                if value is None:
                    simplified[key] = "null"
                elif isinstance(value, (str, int, float, bool)):
                    if isinstance(value, str) and len(value) > 50:
                        simplified[key] = value[:50] + "..."
                    else:
                        simplified[key] = value
                elif isinstance(value, dict):
                    simplified[key] = "{...}"
                elif isinstance(value, list):
                    simplified[key] = f"[{len(value)} items]"
                else:
                    simplified[key] = str(value)[:50]

            lines.append(f"{i}. 索引: {index}, _id: {hit['_id']}")
            lines.append(f"   数据: {json.dumps(simplified, ensure_ascii=False, default=str)}")
            if len(source) > max_fields:
                lines.append(f"   ... 还有 {len(source) - max_fields} 个字段")
            lines.append("")

        lines.append(f"查询耗时: {results['took']}ms")
        return "\n".join(lines)
