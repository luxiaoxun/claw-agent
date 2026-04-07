from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from config.logging_config import get_logger

logger = get_logger(__name__)


def register_error_handlers(app: FastAPI):
    """注册错误处理中间件 - FastAPI版本"""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """处理HTTP异常"""
        status_code = exc.status_code

        if status_code == 400:
            logger.warning(f"400错误: {exc.detail}")
            return JSONResponse(
                status_code=status_code,
                content={"error": "请求格式错误", "details": exc.detail}
            )
        elif status_code == 404:
            logger.warning(f"404错误: {exc.detail}")
            return JSONResponse(
                status_code=status_code,
                content={"error": "资源不存在"}
            )
        elif status_code == 405:
            logger.warning(f"405错误: {exc.detail}")
            return JSONResponse(
                status_code=status_code,
                content={"error": "方法不允许"}
            )
        elif status_code == 500:
            logger.error(f"500错误: {exc.detail}")
            return JSONResponse(
                status_code=status_code,
                content={"error": "服务器内部错误"}
            )
        else:
            # 其他HTTP状态码的默认处理
            return JSONResponse(
                status_code=status_code,
                content={"error": exc.detail}
            )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求验证错误（Pydantic模型验证失败）"""
        logger.warning(f"请求验证错误: {exc.errors()}")

        # 提取详细的验证错误信息
        error_details = []
        for error in exc.errors():
            error_details.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "请求参数验证失败",
                "details": error_details
            }
        )

    @app.exception_handler(500)
    async def internal_server_error_handler(request: Request, exc: Exception):
        """处理500内部服务器错误"""
        logger.error(f"500错误: {str(exc)}")
        # 记录完整的异常堆栈
        logger.exception("详细错误信息:")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "服务器内部错误"}
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理所有未捕获的异常"""
        # 避免重复记录已处理的异常
        if isinstance(exc, (StarletteHTTPException, RequestValidationError)):
            raise exc

        logger.exception(f"未处理的异常: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "服务器内部错误"}
        )