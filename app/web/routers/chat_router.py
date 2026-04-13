import json
import uuid
from fastapi import APIRouter, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from core.models.chat import ChatRequest, ChatResponse
from config.logging_config import get_logger
from web.dependencies import get_conversation_manager
import traceback

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message")
async def chat(
        request: Request,
        conversation_manager=Depends(get_conversation_manager)
):
    """处理聊天请求"""
    try:
        data = await request.json()
        if not data:
            return JSONResponse({"error": "请求体不能为空"}, status_code=400)

        # 会话ID
        conversation_id = data.get('conversation_id')
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        # 验证请求
        try:
            chat_request = ChatRequest(
                message=data.get('message', ''),
                conversation_id=conversation_id,
                stream=data.get('stream', False)
            )
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

        # 处理消息
        logger.info(f"处理聊天请求: {chat_request.message}")

        try:
            response = await conversation_manager.process_message(chat_request.message)
        except Exception as e:
            logger.error(f"处理消息时异步执行错误: {str(e)}")
            traceback.print_exc()
            return JSONResponse({"error": f"处理消息失败: {str(e)}"}, status_code=500)

        # 解析response字符串为JSON对象
        try:
            parsed_response = json.loads(response)
        except json.JSONDecodeError:
            parsed_response = response

        # 创建响应
        chat_response = ChatResponse(
            response=parsed_response,
            conversation_id=chat_request.conversation_id
        )

        return chat_response.to_dict()

    except Exception as e:
        logger.error(f"处理聊天请求时出错: {str(e)}")
        traceback.print_exc()
        return JSONResponse({"error": f"内部错误: {str(e)}"}, status_code=500)


@router.post("/reset")
async def reset(
        conversation_manager=Depends(get_conversation_manager)
):
    """重置对话历史"""
    try:
        conversation_manager.reset_history()
        logger.info("对话历史已重置")
        return {"status": "对话历史已重置"}
    except Exception as e:
        logger.error(f"重置对话历史时出错: {str(e)}")
        return JSONResponse({"error": f"内部错误: {str(e)}"}, status_code=500)


@router.websocket("/ws/message")
async def websocket_chat(
        websocket: WebSocket,
):
    """WebSocket 聊天端点 - 支持流式响应"""
    from core.websocket.websocket_manager import ws_connection_manager

    # 连接并获取客户端ID
    client_id = await ws_connection_manager.connect(websocket)

    conversation_id = None

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

                # 获取该客户端的会话管理器
                conversation_manager = ws_connection_manager.get_manager(client_id)

                if not conversation_manager:
                    await websocket.send_json({
                        "type": "error",
                        "error": "会话管理器未找到"
                    })
                    continue

                if not user_message:
                    await websocket.send_json({
                        "type": "error",
                        "error": "消息内容不能为空"
                    })
                    continue

                # 生成或使用现有的会话ID
                if not conversation_id:
                    conversation_id = str(uuid.uuid4())
                    await websocket.send_json({
                        "type": "session",
                        "conversation_id": conversation_id
                    })

                logger.info(f"WebSocket 处理消息: {user_message}, conversation_id: {conversation_id}")

                # 流式处理消息
                full_response = ""
                has_tool_calls = False

                async for chunk in conversation_manager.process_message_stream(user_message):
                    chunk_type = chunk.get("type", "unknown")

                    if chunk_type == "tool_call":
                        # 工具调用开始
                        has_tool_calls = True
                        await websocket.send_json({
                            "type": "tool_call",
                            "tool_name": chunk.get("tool_name"),
                            "tool_args": chunk.get("tool_args"),
                            "status": "start"
                        })

                    elif chunk_type == "tool_result":
                        # 工具执行结果
                        await websocket.send_json({
                            "type": "tool_result",
                            "tool_name": chunk.get("tool_name"),
                            "result": chunk.get("result"),
                            "status": chunk.get("status", "success")
                        })

                    elif chunk_type == "content":
                        # 流式内容
                        content_chunk = chunk.get("content", "")
                        full_response += content_chunk
                        await websocket.send_json({
                            "type": "chunk",
                            "content": content_chunk,
                            "conversation_id": conversation_id
                        })

                    elif chunk_type == "error":
                        # 错误消息
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
                        "conversation_id": conversation_id,
                        "has_tool_calls": has_tool_calls
                    })

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
        logger.info(f"WebSocket 连接断开, conversation_id: {conversation_id}")
    except Exception as e:
        logger.error(f"WebSocket 连接异常: {str(e)}")
        traceback.print_exc()
