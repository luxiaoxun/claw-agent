# soma/web/dependencies.py
"""
FastAPI 依赖注入函数
"""
from fastapi import Request, HTTPException, status, Depends


def get_current_user_id(request: Request) -> str:
    """
    获取当前用户 ID

    Returns:
        str: 用户 ID
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user["user_id"]
