# web/routers/chat_router.py
import json
import uuid
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from common.response import success_response, fail_response
from config.logging_config import get_logger
from core.chat.conversation_manager import ConversationManager
import traceback

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message")
async def chat(request: Request):
    """处理聊天请求"""
    try:
        data = await request.json()
        message = data.get("message")
        if not data or not isinstance(message, str):
            return fail_response(message="请求体不能为空")

        # 会话ID
        conversation_id = data.get('conversation_id')
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())
        conversation_manager = ConversationManager(conversation_id=conversation_id)
        await conversation_manager.initialize()

        # 处理消息
        logger.info(f"处理聊天请求: {message}")

        try:
            response = await conversation_manager.process_message(message)
        except Exception as e:
            logger.error(f"处理消息时异步执行错误: {str(e)}")
            traceback.print_exc()
            return fail_response(message=f"处理消息失败: {str(e)}")

        # 解析response字符串为JSON对象
        try:
            parsed_response = json.loads(response)
        except json.JSONDecodeError:
            parsed_response = response

        # 创建响应
        chat_response = {
            "response": parsed_response,
            "conversation_id": conversation_id
        }

        return success_response(data=chat_response)

    except Exception as e:
        logger.error(f"处理聊天请求时出错: {str(e)}")
        return fail_response()


@router.post("/reset")
async def reset(request: Request):
    """
    重置当前会话的对话历史
    仅重置内存中的历史记录，不删除数据库中的持久化数据
    """
    try:
        # 获取请求体中的 conversation_id
        body = await request.json() if await request.body() else {}
        conversation_id = body.get('conversation_id')

        if not conversation_id:
            return fail_response(message="会话ID不能为空")

        # 如果请求中提供了conversation_id，确保使用正确的管理器
        conversation_manager = ConversationManager(conversation_id=conversation_id)
        await conversation_manager.initialize()

        # 重置历史记录
        await conversation_manager.reset_history()

        logger.info(f"对话历史已重置, conversation_id: {conversation_manager.conversation_id}")

        return success_response(
            data={
                "conversation_id": conversation_manager.conversation_id
            }
        )

    except Exception as e:
        logger.error(f"重置对话历史时出错: {str(e)}")
        return fail_response()


@router.websocket("/ws/message")
async def websocket_chat(websocket: WebSocket):
    """WebSocket 聊天端点 - 支持流式响应"""
    from core.websocket.websocket_manager import ws_connection_manager

    # 连接并获取客户端ID
    client_id = await ws_connection_manager.connect(websocket)
    conversation_manager = None

    try:
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "client_id": client_id,
            "message": "WebSocket 连接成功"
        })

        while True:
            # 接收客户端消息
            data = await websocket.receive_text()

            try:
                message_data = json.loads(data)
                user_message = message_data.get('message', '')
                conversation_id = message_data.get('conversation_id')

                if not user_message:
                    await websocket.send_json({
                        "type": "error",
                        "error": "消息内容不能为空"
                    })
                    continue

                # 如果还没有会话管理器，进行初始化
                if not conversation_manager:
                    conversation_manager = await ws_connection_manager.initialize_manager(
                        client_id=client_id,
                        conversation_id=conversation_id
                    )
                elif conversation_id and conversation_id != ws_connection_manager.get_conversation_id(client_id):
                    # 如果会话ID发生变化，更新管理器的会话ID
                    await ws_connection_manager.update_conversation_id(client_id, conversation_id)
                    conversation_manager = ws_connection_manager.get_manager(client_id)

                # 确保有会话ID（如果还是没有，生成一个新的）
                if not conversation_manager.conversation_id:
                    import uuid
                    new_conversation_id = str(uuid.uuid4())
                    await ws_connection_manager.update_conversation_id(client_id, new_conversation_id)
                    conversation_manager = ws_connection_manager.get_manager(client_id)

                    # 发送会话ID给前端
                    await websocket.send_json({
                        "type": "session",
                        "conversation_id": new_conversation_id
                    })

                logger.info(
                    f"WebSocket 处理消息: {user_message[:100]}..., conversation_id: {conversation_manager.conversation_id}")

                # 流式处理消息
                full_response = ""
                has_tool_calls = False

                async for chunk in conversation_manager.process_message_stream(user_message):
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
                            "conversation_id": conversation_manager.conversation_id
                        })

                    elif chunk_type == "error":
                        await websocket.send_json({
                            "type": "error",
                            "error": chunk.get("content", "未知错误")
                        })
                        break

                # 发送完成消息
                if full_response:
                    await websocket.send_json({
                        "type": "complete",
                        "full_response": full_response,
                        "conversation_id": conversation_manager.conversation_id,
                        "has_tool_calls": has_tool_calls
                    })

                logger.info(f"消息处理完成，响应长度: {len(full_response)}")

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "error": "无效的 JSON 格式"
                })
            except Exception as e:
                logger.error(f"处理 WebSocket 消息时出错: {str(e)}")
                traceback.print_exc()
                await websocket.send_json({
                    "type": "error",
                    "error": f"处理消息失败: {str(e)}"
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket 连接断开, client_id: {client_id}")
        await ws_connection_manager.disconnect_and_cleanup(client_id)
    except Exception as e:
        logger.error(f"WebSocket 连接异常: {str(e)}")
        traceback.print_exc()
        await ws_connection_manager.disconnect_and_cleanup(client_id)
