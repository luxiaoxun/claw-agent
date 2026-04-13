# web/dependencies.py
from fastapi import Request, HTTPException


async def get_conversation_manager(request: Request):
    """依赖注入：获取conversation_manager"""
    if request.app.state.conversation_manager is None:
        raise HTTPException(status_code=503, detail="Agent未初始化")
    return request.app.state.conversation_manager
