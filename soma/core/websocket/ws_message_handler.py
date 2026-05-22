# core/websocket/ws_message_handler.py
import json
import traceback
from typing import Callable, Optional
from fastapi import WebSocket
from soma.config.logging_config import get_logger
from soma.core.websocket.websocket_manager import WebSocketConnectionManager

logger = get_logger(__name__)


class TextMessageHandler:
    """文本消息处理器 - 处理聊天消息和流式响应"""

    def __init__(self, connection_manager: WebSocketConnectionManager):
        self.connection_manager = connection_manager

    async def handle(self, websocket: WebSocket, client_id: str, message_data: dict):
        """
        处理文本消息

        Args:
            websocket: WebSocket连接
            client_id: 客户端ID
            message_data: 解析后的JSON消息数据
        """
        try:
            user_message = message_data.get('message', '')
            session_id = message_data.get('session_id')
            user_id = message_data.get('user_id')

            if not user_message:
                await websocket.send_json({
                    "type": "error",
                    "error": "消息内容不能为空"
                })
                return

            # 获取或创建会话管理器
            session_manager = await self.connection_manager.get_or_create_session_manager(
                client_id=client_id,
                session_id=session_id,
                user_id=user_id
            )

            # 如果是新创建的会话，发送会话ID给前端
            if session_id is None:
                await websocket.send_json({
                    "type": "session",
                    "session_id": session_manager.session_id
                })

            logger.info(
                f"WebSocket 处理消息: {user_message[:100]}..., session_id: {session_manager.session_id}")

            # 流式处理消息
            full_response = ""
            has_tool_calls = False

            async for chunk in session_manager.process_message_stream(user_message):
                chunk_type = chunk.get("type", "unknown")

                if chunk_type == "tool_call":
                    has_tool_calls = True
                    await websocket.send_json({
                        "type": "tool_call",
                        "tool_name": chunk.get("tool_name"),
                        "tool_args": chunk.get("tool_args"),
                        "status": "start"
                    })

                elif chunk_type == "tool_result":
                    await websocket.send_json({
                        "type": "tool_result",
                        "tool_name": chunk.get("tool_name"),
                        "result": chunk.get("result"),
                        "status": chunk.get("status", "success")
                    })

                elif chunk_type == "content":
                    content_chunk = chunk.get("content", "")
                    full_response += content_chunk
                    await websocket.send_json({
                        "type": "chunk",
                        "content": content_chunk,
                        "session_id": session_manager.session_id
                    })

                elif chunk_type == "error":
                    await websocket.send_json({
                        "type": "error",
                        "error": chunk.get("content", "Unknown error")
                    })
                    break

            # 发送完成消息
            if full_response:
                await websocket.send_json({
                    "type": "complete",
                    "full_response": full_response,
                    "session_id": session_manager.session_id,
                    "has_tool_calls": has_tool_calls
                })

            logger.info(f"消息处理完成，响应长度: {len(full_response)}")

        except Exception as e:
            logger.error(f"处理文本消息时出错: {str(e)}")
            traceback.print_exc()
            await websocket.send_json({
                "type": "error",
                "error": f"Process message error: {str(e)}"
            })
