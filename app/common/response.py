# common/response.py
from typing import Optional, Any, Dict, Union
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from common.response_code import ResponseCode


class ApiResponse:
    """统一API响应结构"""

    def __init__(
            self,
            code: Union[str, ResponseCode] = ResponseCode.SUCCESS,
            message: Optional[str] = None,
            data: Optional[Any] = None
    ):
        # 处理枚举值：如果是枚举则取值，否则直接使用字符串
        if isinstance(code, ResponseCode):
            self.code = code.value  # 获取枚举的实际值，如 "200"
        else:
            self.code = str(code)

        # 如果message为None，使用默认消息
        self.message = message if message is not None else ResponseCode.get_default_message(self.code)
        self.data = data if data is not None else {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "code": self.code,
            "message": self.message,
            "data": jsonable_encoder(self.data)
        }

    def to_json_response(self, status_code: int = 200) -> JSONResponse:
        """转换为FastAPI JSONResponse"""
        return JSONResponse(
            status_code=status_code,
            content=self.to_dict()
        )

    @classmethod
    def success(
            cls,
            data: Optional[Any] = None,
            message: Optional[str] = None,
            status_code: int = 200
    ) -> JSONResponse:
        """成功响应"""
        response = cls(code=ResponseCode.SUCCESS, message=message, data=data)
        return response.to_json_response(status_code=status_code)

    @classmethod
    def fail(
            cls,
            data: Optional[Any] = None,
            message: Optional[str] = None,
            status_code: int = 200
    ) -> JSONResponse:
        """失败响应"""
        response = cls(code=ResponseCode.FAIL, message=message, data=data)
        return response.to_json_response(status_code=status_code)

    @classmethod
    def error(
            cls,
            code: Union[str, ResponseCode] = ResponseCode.REQUEST_ERROR,
            message: Optional[str] = None,
            data: Optional[Any] = None,
            status_code: int = 400
    ) -> JSONResponse:
        """错误响应"""
        response = cls(code=code, message=message, data=data)
        return response.to_json_response(status_code=status_code)


# 便捷函数
def success_response(data: Optional[Any] = None, message: Optional[str] = None) -> JSONResponse:
    """成功响应快捷函数"""
    return ApiResponse.success(data=data, message=message)


def fail_response(data: Optional[Any] = None, message: Optional[str] = None) -> JSONResponse:
    """失败响应快捷函数"""
    return ApiResponse.fail(data=data, message=message)


def api_response(
        code: Union[str, ResponseCode] = ResponseCode.SUCCESS,
        message: Optional[str] = None,
        data: Optional[Any] = None,
        status_code: int = 200
) -> JSONResponse:
    """通用API响应函数"""
    response = ApiResponse(code=code, message=message, data=data)
    return response.to_json_response(status_code=status_code)
