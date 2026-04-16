from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from pydantic import BaseModel
from core.chat.session_db import SessionDatabase
from config.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


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
    created_at: str
    updated_at: str
    user_id: Optional[str] = None
    message_count: int = 0
    metadata: Optional[dict] = None


class SessionListResponse(BaseModel):
    total: int
    sessions: List[SessionResponse]


# 初始化数据库
db = SessionDatabase()


@router.get("/", response_model=SessionListResponse)
async def list_sessions(
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
):
    """获取会话列表"""
    try:
        sessions = db.list_sessions(user_id=user_id, limit=limit, offset=offset)

        # 获取总数（简化实现，实际应该单独查询）
        total = len(sessions)

        return SessionListResponse(
            total=total,
            sessions=[SessionResponse(**session) for session in sessions]
        )
    except Exception as e:
        logger.error(f"获取会话列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}")
async def get_session(conversation_id: str):
    """获取单个会话详情"""
    try:
        session = db.get_session(conversation_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 获取消息数量
        messages = db.load_messages(conversation_id, limit=10000)

        return {
            "conversation_id": session['conversation_id'],
            "title": session.get('title', ''),
            "created_at": session.get('created_at'),
            "updated_at": session.get('updated_at'),
            "user_id": session.get('user_id'),
            "message_count": len(messages),
            "metadata": session.get('metadata', {})
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create")
async def create_session(session_data: SessionCreate):
    """创建新会话"""
    try:
        import uuid
        conversation_id = session_data.conversation_id or str(uuid.uuid4())

        success = db.create_session(
            conversation_id=conversation_id,
            title=session_data.title,
            user_id=session_data.user_id,
            metadata=session_data.metadata
        )

        if success:
            return {"conversation_id": conversation_id, "message": "会话创建成功"}
        else:
            raise HTTPException(status_code=500, detail="会话创建失败")
    except Exception as e:
        logger.error(f"创建会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{conversation_id}")
async def update_session(conversation_id: str, update_data: SessionUpdate):
    """更新会话信息（如标题）"""
    try:
        success = db.update_session_title(conversation_id, update_data.title)
        if success:
            return {"message": "会话更新成功"}
        else:
            raise HTTPException(status_code=404, detail="会话不存在")
    except Exception as e:
        logger.error(f"更新会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{conversation_id}")
async def delete_session(conversation_id: str):
    """删除会话"""
    try:
        success = db.delete_session(conversation_id)
        if success:
            return {"message": "会话删除成功"}
        else:
            raise HTTPException(status_code=404, detail="会话不存在")
    except Exception as e:
        logger.error(f"删除会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/messages")
async def get_session_messages(
        conversation_id: str,
        limit: int = 100,
        offset: int = 0
):
    """获取会话的消息历史"""
    try:
        # 检查会话是否存在
        session = db.get_session(conversation_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 获取消息（简化实现，暂不支持offset）
        messages = db.load_messages(conversation_id, limit=limit)

        return {
            "conversation_id": conversation_id,
            "total": len(messages),
            "messages": messages
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话消息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
