# soma/service/auth_service.py
from typing import Optional, Dict
from soma.config.logging_config import get_logger

logger = get_logger(__name__)


class AuthService:
    """
    认证服务

    提供 token 验证功能，支持多种验证方式：
    1. 调用外部认证服务（如 SSO、JWT 验证服务）
    2. 查询数据库验证 token
    3. 验证 JWT token 并解析 payload

    由集成方根据实际需求补充 verify_token 的实现
    """

    async def verify_token(self, token: str) -> Optional[str]:
        """
        验证 token 并返回 user_id

        Args:
            token: 认证 token

        Returns:
            str: user_id（验证成功）
            None: 验证失败
        """
        # TODO: 由集成方补充实际的 token 验证逻辑
        #
        # 示例实现：
        #
        # 方案1: JWT 验证
        # import jwt
        # try:
        #     payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        #     return payload.get("user_id")
        # except jwt.InvalidTokenError:
        #     return None
        #
        # 方案2: 调用外部 SSO 服务
        # import httpx
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         "https://sso.example.com/verify",
        #         json={"token": token}
        #     )
        #     if response.status_code == 200:
        #         return response.json().get("user_id")
        #     return None
        #
        # 方案3: 数据库查询
        # user = await db.query("SELECT user_id FROM tokens WHERE token = ?", [token])
        # return user["user_id"] if user else None

        # 开发调试用：直接使用 token 作为 user_id
        # 生产环境必须替换为实际的验证逻辑
        if not token:
            return None

        return token

    async def get_user_info(self, user_id: str) -> Optional[Dict]:
        """
        根据 user_id 获取用户信息（可选）

        Args:
            user_id: 用户ID

        Returns:
            dict: 用户信息，包含 user_id, username, roles 等
            None: 用户不存在
        """
        return {
            "user_id": user_id,
            "roles": ["admin"] if user_id == "admin" else ["user"]
        }


# 全局单例
auth_service = AuthService()
