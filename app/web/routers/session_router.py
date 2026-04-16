# web/routers/session_router.py
from fastapi import APIRouter
from typing import Optional, List
from pydantic import BaseModel
from core.chat.session_service import SessionDatabase
from config.logging_config import get_logger
from common.response import success_response, fail_response
import uuid

logger = get_logger(__name__)
router = APIRouter(prefix="/session", tags=["session"])


# 请求/响应模型
class SessionCreate(BaseModel):
    conversation_id: Optional[str] = None
    title: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[dict] = None


class SessionUpdate(BaseModel):
    title: str


class SessionResponse(BaseModel):
    conversation_id: str
    title: str
    create_time: str
    update_time: str
    user_id: Optional[str] = None
    message_count: int = 0
    metadata: Optional[dict] = None


class SessionListResponse(BaseModel):
    total: int
    sessions: List[SessionResponse]


# 初始化数据库
db = SessionDatabase()


@router.get("/")
async def list_sessions(
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
):
    """获取会话列表"""
    try:
        logger.info(f"获取会话列表: user_id={user_id}, limit={limit}, offset={offset}")

        sessions = db.list_sessions(user_id=user_id, limit=limit, offset=offset)

        # 获取总数（简化实现，实际应该单独查询）
        total = len(sessions)

        sessions_data = [SessionResponse(**session).dict() for session in sessions]

        return success_response(
            data={
                "total": total,
                "sessions": sessions_data
            }
        )

    except Exception as e:
        logger.error(f"获取会话列表失败: {str(e)}")
        return fail_response()


@router.get("/{conversation_id}")
async def get_session(conversation_id: str):
    """获取单个会话详情"""
    try:
        logger.info(f"获取会话详情: conversation_id={conversation_id}")

        session = db.get_session(conversation_id)
        if not session:
            logger.warning(f"会话不存在: {conversation_id}")
            return fail_response(message="会话不存在")

        # 获取消息数量
        messages = db.load_messages(conversation_id, limit=10000)

        session_data = {
            "conversation_id": session['conversation_id'],
            "title": session.get('title', ''),
            "create_time": session.get('create_time'),
            "update_time": session.get('update_time'),
            "user_id": session.get('user_id'),
            "message_count": len(messages),
            "metadata": session.get('metadata', {})
        }

        return success_response(
            data=session_data,
            message="获取会话详情成功"
        )

    except Exception as e:
        logger.error(f"获取会话详情失败: {str(e)}")
        return fail_response()


@router.post("/create")
async def create_session(session_data: SessionCreate):
    """创建新会话"""
    try:
        conversation_id = session_data.conversation_id or str(uuid.uuid4())
        logger.info(f"创建会话: conversation_id={conversation_id}, user_id={session_data.user_id}")

        success = db.create_session(
            conversation_id=conversation_id,
            title=session_data.title,
            user_id=session_data.user_id,
            metadata=session_data.metadata
        )

        if success:
            return success_response(
                data={"conversation_id": conversation_id}
            )
        else:
            logger.error(f"会话创建失败: {conversation_id}")
            return fail_response(message="会话创建失败")

    except Exception as e:
        logger.error(f"创建会话失败: {str(e)}")
        return fail_response()


@router.put("/{conversation_id}")
async def update_session(conversation_id: str, update_data: SessionUpdate):
    """更新会话信息（如标题）"""
    try:
        logger.info(f"更新会话: conversation_id={conversation_id}, title={update_data.title}")

        success = db.update_session_title(conversation_id, update_data.title)

        if success:
            return success_response(message="会话更新成功")
        else:
            logger.warning(f"会话不存在，无法更新: {conversation_id}")
            return fail_response(message="会话不存在")

    except Exception as e:
        logger.error(f"更新会话失败: {str(e)}")
        return fail_response()


@router.delete("/{conversation_id}")
async def delete_session(conversation_id: str):
    """删除会话"""
    try:
        logger.info(f"删除会话: conversation_id={conversation_id}")

        success = db.delete_session(conversation_id)

        if success:
            return success_response(message="会话删除成功")
        else:
            logger.warning(f"会话不存在，无法删除: {conversation_id}")
            return fail_response(message="会话不存在")

    except Exception as e:
        logger.error(f"删除会话失败: {str(e)}")
        return fail_response()


@router.get("/{conversation_id}/messages")
async def get_session_messages(
        conversation_id: str,
        limit: int = 100,
        offset: int = 0
):
    """获取会话的消息历史"""
    try:
        logger.info(f"获取会话消息: conversation_id={conversation_id}, limit={limit}, offset={offset}")

        # 检查会话是否存在
        session = db.get_session(conversation_id)
        if not session:
            logger.warning(f"会话不存在，无法获取消息: {conversation_id}")
            return fail_response(message="会话不存在")

        # 获取消息（简化实现，暂不支持offset）
        messages = db.load_messages(conversation_id, limit=limit)

        messages_data = {
            "conversation_id": conversation_id,
            "total": len(messages),
            "messages": messages
        }

        return success_response(
            data=messages_data,
            message="获取会话消息成功"
        )

    except Exception as e:
        logger.error(f"获取会话消息失败: {str(e)}")
        return fail_response()
