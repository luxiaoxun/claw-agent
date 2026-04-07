import re
from typing import Optional
from pydantic import BaseModel, validator


class MessageValidator(BaseModel):
    """消息验证器"""
    message: str

    @validator('message')
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError('消息不能为空')
        if len(v) > 10000:
            raise ValueError('消息过长，最大长度10000字符')
        return v.strip()


class IndexNameValidator:
    """索引名称验证器"""

    @staticmethod
    def validate(index_name: str) -> bool:
        """验证索引名称是否合法"""
        if not index_name:
            return False

        # Elasticsearch索引名称规则
        # 不能包含大写字母
        if re.search(r'[A-Z]', index_name):
            return False

        # 不能包含特殊字符
        if re.search(r'[\\/*?"<>|\s,]', index_name):
            return False

        # 不能以_、-、+开头
        if index_name.startswith(('_', '-', '+')):
            return False

        # 长度限制
        if len(index_name) > 255:
            return False

        return True

    @staticmethod
    def sanitize(index_name: str) -> Optional[str]:
        """清理索引名称"""
        # 转换为小写
        index_name = index_name.lower()

        # 移除非法字符
        index_name = re.sub(r'[\\/*?"<>|\s,]', '', index_name)

        # 如果以非法字符开头，添加前缀
        if index_name.startswith(('_', '-', '+')):
            index_name = 'idx_' + index_name

        return index_name if index_name else None