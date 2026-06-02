# soma/web/middlewares/auth.py
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from soma.config.logging_config import get_logger

logger = get_logger(__name__)

# 公开端点，不需要认证
PUBLIC_PATHS = [
    "/docs",
    "/openapi.json",
    "/redoc",
]


class AuthMiddleware(BaseHTTPMiddleware):
    """认证中间件"""

    async def dispatch(self, request: Request, call_next):
        # 跳过 OPTIONS 预检请求
        if request.method == "OPTIONS":
            return await call_next(request)

        # 跳过公开端点
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # 进行认证
        user = await self._authenticate(request)
        request.state.user = user

        response = await call_next(request)
        return response

    def _is_public_path(self, path: str) -> bool:
        """检查是否是公开端点"""
        return path in PUBLIC_PATHS

    async def _authenticate(self, request: Request) -> dict:
        """从请求头 X-Token 获取并验证用户信息"""
        # 从请求头获取 token
        token = request.headers.get("X-Token")

        # 如果没有 token，尝试从 query 参数获取（用于 WebSocket）
        if not token:
            token = request.query_params.get("token")

        if not token:
            logger.warning(f"缺少 X-Token header: {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Token header"
            )

        # 使用 AuthService 验证 token 并获取 user_id
        from soma.service.auth_service import auth_service
        user_id = await auth_service.verify_token(token)

        if not user_id:
            logger.warning(f"Token 验证失败: {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        logger.debug(f"认证成功: user_id={user_id}")
        return {"user_id": user_id, "token": token}
