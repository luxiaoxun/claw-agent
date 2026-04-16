# common/response_code.py
from enum import Enum


class ResponseCode(str, Enum):
    SUCCESS = "200"
    FAIL = "500"
    REQUEST_ERROR = "10106100001"
    REQUEST_DATA_NOT_FOUND = "10106100004"

    @classmethod
    def get_default_message(cls, code: str) -> str:
        """获取默认消息"""
        messages = {
            cls.SUCCESS: "success",
            cls.FAIL: "fail",
            cls.REQUEST_ERROR: "request error",
            cls.REQUEST_DATA_NOT_FOUND: "request data not found"
        }
        return messages.get(code, "unknown error")
