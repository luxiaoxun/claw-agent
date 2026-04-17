# web/routers/session_router.py
from fastapi import APIRouter
from typing import Optional, List
from pydantic import BaseModel
from service.database_service import database_service
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


# 辅助函数：确保数据库服务已初始化
def ensure_db_services():
    """确保数据库服务已初始化"""
    if not database_service.is_initialized():
        logger.warning("数据库服务未初始化，正在自动初始化...")
        database_service.initialize()


@router.get("/")
async def list_sessions(
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
):
    """获取会话列表"""
    try:
        ensure_db_services()
        logger.info(f"获取会话列表: user_id={user_id}, limit={limit}, offset={offset}")

        # 使用 session_service 获取会话列表
        sessions = database_service.session_service.list_sessions(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        # 转换为响应格式
        sessions_data = []
        for session in sessions:
            sessions_data.append({
                "conversation_id": session.get('conversation_id'),
                "title": session.get('title', ''),
                "create_time": session.get('create_time'),
                "update_time": session.get('update_time'),
                "user_id": session.get('user_id'),
                "message_count": session.get('message_count', 0),
                "metadata": session.get('metadata', {})
            })

        return success_response(
            data={
                "total": len(sessions),
                "sessions": sessions_data
            }
        )

    except Exception as e:
        logger.error(f"获取会话列表失败: {str(e)}")
        return fail_response(message=f"获取会话列表失败: {str(e)}")


@router.get("/{conversation_id}")
async def get_session(conversation_id: str):
    """获取单个会话详情"""
    try:
        ensure_db_services()
        logger.info(f"获取会话详情: conversation_id={conversation_id}")

        # 使用 session_service 获取会话
        session = database_service.session_service.get_session(conversation_id)
        if not session:
            logger.warning(f"会话不存在: {conversation_id}")
            return fail_response(message="会话不存在")

        # 使用 message_service 获取消息数量
        message_count = database_service.message_service.get_message_count(conversation_id)

        session_data = {
            "conversation_id": session.get('conversation_id'),
            "title": session.get('title', ''),
            "create_time": session.get('create_time'),
            "update_time": session.get('update_time'),
            "user_id": session.get('user_id'),
            "message_count": message_count,
            "metadata": session.get('metadata', {})
        }

        return success_response(
            data=session_data,
            message="获取会话详情成功"
        )

    except Exception as e:
        logger.error(f"获取会话详情失败: {str(e)}")
        return fail_response(message=f"获取会话详情失败: {str(e)}")


@router.post("/create")
async def create_session(session_data: SessionCreate):
    """创建新会话"""
    try:
        ensure_db_services()
        conversation_id = session_data.conversation_id or str(uuid.uuid4())
        logger.info(f"创建会话: conversation_id={conversation_id}, user_id={session_data.user_id}")

        # 使用 session_service 创建会话
        success = database_service.session_service.create_session(
            conversation_id=conversation_id,
            title=session_data.title,
            user_id=session_data.user_id,
            metadata=session_data.metadata
        )

        if success:
            return success_response(
                data={"conversation_id": conversation_id},
                message="会话创建成功"
            )
        else:
            logger.error(f"会话创建失败: {conversation_id}")
            return fail_response(message="会话创建失败")

    except Exception as e:
        logger.error(f"创建会话失败: {str(e)}")
        return fail_response(message=f"创建会话失败: {str(e)}")


@router.post("/create-or-get")
async def create_or_get_session(
        conversation_id: str,
        user_id: Optional[str] = None
):
    """获取或创建会话（如果不存在则创建）"""
    try:
        ensure_db_services()
        logger.info(f"获取或创建会话: conversation_id={conversation_id}, user_id={user_id}")

        # 使用 session_service 获取或创建会话
        session = database_service.session_service.get_or_create_session(
            conversation_id=conversation_id,
            user_id=user_id
        )

        if session:
            # 获取消息数量
            message_count = database_service.message_service.get_message_count(conversation_id)

            return success_response(
                data={
                    "conversation_id": session.get('conversation_id'),
                    "title": session.get('title', ''),
                    "create_time": session.get('create_time'),
                    "update_time": session.get('update_time'),
                    "user_id": session.get('user_id'),
                    "message_count": message_count,
                    "metadata": session.get('metadata', {})
                },
                message="获取会话成功"
            )
        else:
            logger.error(f"获取或创建会话失败: {conversation_id}")
            return fail_response(message="获取或创建会话失败")

    except Exception as e:
        logger.error(f"获取或创建会话失败: {str(e)}")
        return fail_response(message=f"获取或创建会话失败: {str(e)}")


@router.put("/{conversation_id}")
async def update_session(conversation_id: str, update_data: SessionUpdate):
    """更新会话信息（如标题）"""
    try:
        ensure_db_services()
        logger.info(f"更新会话: conversation_id={conversation_id}, title={update_data.title}")

        # 使用 session_service 更新会话标题
        success = database_service.session_service.update_session_title(
            conversation_id,
            update_data.title
        )

        if success:
            return success_response(message="会话更新成功")
        else:
            logger.warning(f"会话不存在，无法更新: {conversation_id}")
            return fail_response(message="会话不存在")

    except Exception as e:
        logger.error(f"更新会话失败: {str(e)}")
        return fail_response(message=f"更新会话失败: {str(e)}")


@router.delete("/{conversation_id}")
async def delete_session(conversation_id: str):
    """删除会话"""
    try:
        ensure_db_services()
        logger.info(f"删除会话: conversation_id={conversation_id}")

        # 使用 session_service 删除会话
        success = database_service.session_service.delete_session(conversation_id)

        if success:
            return success_response(message="会话删除成功")
        else:
            logger.warning(f"会话不存在，无法删除: {conversation_id}")
            return fail_response(message="会话不存在")

    except Exception as e:
        logger.error(f"删除会话失败: {str(e)}")
        return fail_response(message=f"删除会话失败: {str(e)}")


@router.get("/{conversation_id}/messages")
async def get_session_messages(
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
        message_type: Optional[str] = None
):
    """获取会话的消息历史"""
    try:
        ensure_db_services()
        logger.info(
            f"获取会话消息: conversation_id={conversation_id}, limit={limit}, offset={offset}, type={message_type}")

        # 检查会话是否存在
        session = database_service.session_service.get_session(conversation_id)
        if not session:
            logger.warning(f"会话不存在，无法获取消息: {conversation_id}")
            return fail_response(message="会话不存在")

        # 使用 message_service 获取消息
        messages = database_service.message_service.load_messages(
            conversation_id=conversation_id,
            limit=limit,
            offset=offset,
            message_type=message_type
        )

        # 获取消息总数
        total_messages = database_service.message_service.get_message_count(conversation_id)

        messages_data = {
            "conversation_id": conversation_id,
            "conversation_title": session.get('title', ''),
            "total": total_messages,
            "returned": len(messages),
            "offset": offset,
            "limit": limit,
            "messages": messages
        }

        return success_response(
            data=messages_data,
            message="获取会话消息成功"
        )

    except Exception as e:
        logger.error(f"获取会话消息失败: {str(e)}")
        return fail_response(message=f"获取会话消息失败: {str(e)}")


@router.delete("/{conversation_id}/messages")
async def delete_session_messages(
        conversation_id: str,
        before_time: Optional[str] = None,
        keep_session: bool = True
):
    """
    删除会话中的消息（不删除会话本身）

    Args:
        conversation_id: 会话ID
        before_time: 可选，删除指定时间之前的消息（ISO格式，如：2024-01-01T00:00:00）
        keep_session: 是否保留会话（默认True，删除消息但保留会话记录）

    注意：
        - 如果 keep_session=True，会删除消息但保留会话
        - 如果 keep_session=False，会删除整个会话（包括所有消息）
        - 删除整个会话时，建议直接使用 DELETE /{conversation_id} API
    """
    try:
        ensure_db_services()

        # 检查会话是否存在
        session = database_service.session_service.get_session(conversation_id)
        if not session:
            logger.warning(f"会话不存在: {conversation_id}")
            return fail_response(message="会话不存在")

        if not keep_session:
            # 删除整个会话（会级联删除消息）
            success = database_service.session_service.delete_session(conversation_id)
            if success:
                logger.info(f"会话 {conversation_id} 及其所有消息已删除")
                return success_response(message="会话及其消息已删除")
            else:
                return fail_response(message="删除会话失败")

        # 只删除消息，保留会话
        from datetime import datetime
        before_datetime = None
        if before_time:
            try:
                before_datetime = datetime.fromisoformat(before_time)
            except ValueError:
                return fail_response(message="时间格式错误，请使用 ISO 格式（如：2024-01-01T00:00:00）")

        # 使用 message_service 删除消息
        success = database_service.message_service.delete_messages(
            conversation_id=conversation_id,
            before_time=before_datetime
        )

        if success:
            message = f"已删除会话 {conversation_id} 中的消息"
            if before_datetime:
                message += f"（{before_datetime} 之前）"
            logger.info(message)
            return success_response(message=message)
        else:
            return fail_response(message="删除消息失败")

    except Exception as e:
        logger.error(f"删除会话消息失败: {str(e)}")
        return fail_response(message=f"删除会话消息失败: {str(e)}")


@router.get("/statistics")
async def get_statistics(user_id: Optional[str] = None):
    """获取会话统计信息"""
    try:
        ensure_db_services()
        logger.info(f"获取统计信息: user_id={user_id}")

        # 获取所有会话
        sessions = database_service.session_service.list_sessions(
            user_id=user_id,
            limit=10000,  # 获取所有会话用于统计
            offset=0
        )

        total_sessions = len(sessions)
        total_messages = 0
        sessions_with_messages = 0

        # 统计消息总数
        for session in sessions:
            conversation_id = session.get('conversation_id')
            if conversation_id:
                msg_count = database_service.message_service.get_message_count(conversation_id)
                total_messages += msg_count
                if msg_count > 0:
                    sessions_with_messages += 1

        stats = {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "sessions_with_messages": sessions_with_messages,
            "avg_messages_per_session": total_messages / total_sessions if total_sessions > 0 else 0,
            "user_id": user_id or "all"
        }

        return success_response(
            data=stats,
            message="获取统计信息成功"
        )

    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        return fail_response(message=f"获取统计信息失败: {str(e)}")
