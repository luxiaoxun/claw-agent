# soma/web/middlewares/auth.py
"""
认证中间件，支持两种鉴权模式：
- shared: 共享模式，从请求头 X-User-Id 获取用户ID（集成部署时使用）
- standalone: 独立模式，使用 API Key 认证，绑定默认用户 admin
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from soma.config.settings import settings
from soma.config.logging_config import get_logger

logger = get_logger(__name__)

# 公开端点，不需要认证
PUBLIC_PATHS = [
    "/api/health/status",
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

        # 根据模式进行认证
        user = await self._authenticate(request)
        request.state.user = user

        response = await call_next(request)
        return response

    def _is_public_path(self, path: str) -> bool:
        """检查是否是公开端点"""
        return path in PUBLIC_PATHS

    async def _authenticate(self, request: Request) -> dict:
        """
        根据 AUTH_MODE 进行认证
        - shared: 从请求头获取 X-User-Id
        - standalone: 验证 API Key
        """
        if settings.AUTH_MODE == "shared":
            return self._auth_shared(request)
        else:
            return self._auth_standalone(request)

    def _auth_shared(self, request: Request) -> dict:
        """共享模式: 从请求头或 query 参数获取用户ID"""
        # 优先从 headers 获取
        user_id = request.headers.get("X-User-Id")
        # WebSocket 连接无法使用 headers，从 query 参数获取
        if not user_id:
            user_id = request.query_params.get("user_id")

        if not user_id:
            logger.warning(f"Shared 模式缺少 X-User-Id header: {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-User-Id header"
            )

        # 可选: 验证 Token（如果配置了 VERIFY_SHARED_TOKEN）
        if settings.VERIFY_SHARED_TOKEN:
            token = request.headers.get("X-Token")
            if not token:
                logger.warning(f"Shared 模式缺少 X-Token header: {request.url.path}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing X-Token header"
                )
            # Token 验证逻辑可根据具体需求实现
            # 例如: 调用父系统验证接口，或验证特定格式的 token
            logger.debug(f"Shared 模式 Token 验证（当前为简单检查）: {token[:10]}...")

        logger.debug(f"Shared 模式认证成功: user_id={user_id}")
        return {"user_id": user_id, "mode": "shared"}

    def _auth_standalone(self, request: Request) -> dict:
        """独立模式: API Key 认证，绑定 admin 用户"""
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            logger.warning(f"Standalone 模式缺少 X-API-Key header: {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-API-Key header"
            )

        if api_key != settings.API_KEY:
            logger.warning(f"Standalone 模式 API Key 无效: {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key"
            )

        logger.debug(f"Standalone 模式认证成功: user_id=admin")
        return {"user_id": "admin", "mode": "standalone"}
