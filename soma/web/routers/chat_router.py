# web/routers/chat_router.py
from fastapi import APIRouter, Request, WebSocket, Depends, Query
from soma.common.response import success_response, fail_response
from soma.config.logging_config import get_logger
from soma.core.websocket.websocket_service import websocket_service
from soma.core.chat.chat_service import chat_service
from soma.web.dependencies import get_current_user_id

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message")
async def chat(
        request: Request,
        current_user_id: str = Depends(get_current_user_id)
):
    """处理聊天请求"""
    try:
        # 1. 解析请求数据
        data = await request.json()
        message = data.get("message")
        session_id = data.get("session_id")

        # 2. 调用聊天服务处理
        response_data, error = await chat_service.process_chat_request(
            message=message,
            session_id=session_id,
            user_id=current_user_id
        )

        # 3. 处理错误情况
        if error:
            return fail_response(message=error)

        # 4. 返回成功响应
        return success_response(data=response_data)

    except Exception as e:
        logger.error(f"处理聊天请求时出错: {str(e)}", exc_info=True)
        return fail_response(message=f"处理请求失败: {str(e)}")


@router.websocket("/ws/message")
async def websocket_chat(
        websocket: WebSocket,
        token: str = Query(default=None)
):
    """WebSocket 聊天端点 - 支持流式响应和文件传输"""
    # 使用 AuthService 验证 token 并获取 user_id
    from soma.service.auth_service import auth_service
    user_id = await auth_service.verify_token(token)

    # 将 user_id 存储在 websocket state 中，供后续处理使用
    websocket.state.user_id = user_id
    await websocket_service.handle_connection(websocket)
