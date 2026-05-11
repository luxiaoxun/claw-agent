# web/routers/chat_router.py
from fastapi import APIRouter, Request, WebSocket
from common.response import success_response, fail_response
from config.logging_config import get_logger
from core.websocket.websocket_service import websocket_service
from core.chat.chat_service import chat_service

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message")
async def chat(request: Request):
    """处理聊天请求"""
    try:
        # 1. 解析请求数据
        data = await request.json()
        message = data.get("message")
        session_id = data.get("session_id")

        # 2. 调用聊天服务处理
        response_data, error = await chat_service.process_chat_request(
            message=message,
            session_id=session_id
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
async def websocket_chat(websocket: WebSocket):
    """WebSocket 聊天端点 - 支持流式响应和文件传输"""
    await websocket_service.handle_connection(websocket)
