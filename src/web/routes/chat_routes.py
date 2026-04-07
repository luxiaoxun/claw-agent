import json
import uuid
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from core.models.chat import ChatRequest, ChatResponse
from config.logging_config import get_logger
from web.dependencies import get_conversation_manager
import traceback

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/chat")
async def chat(
        request: Request,
        conversation_manager=Depends(get_conversation_manager)  # 关键修改1：使用Depends注入
):
    """处理聊天请求"""
    try:
        data = await request.json()  # 关键修改2：异步获取JSON
        if not data:
            return JSONResponse({"error": "请求体不能为空"}, status_code=400)

        # 会话ID
        conversation_id = data.get('conversation_id')
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())  # 关键修改3：转换为字符串

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
            # 关键修改4：直接await异步方法，不需要run_async
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

        return chat_response.to_dict()  # 关键修改5：FastAPI自动序列化字典

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


# 关键修改6：定义依赖注入函数（需要放在全局或单独模块）
async def get_conversation_manager(request: Request):
    """依赖注入：获取conversation_manager"""
    if request.app.state.conversation_manager is None:
        raise HTTPException(status_code=503, detail="Agent未初始化")
    return request.app.state.conversation_manager
