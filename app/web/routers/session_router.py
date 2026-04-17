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
    meta_data: Optional[dict] = None


class SessionUpdate(BaseModel):
    title: str


class MessageRoundResponse(BaseModel):
    """消息轮次响应模型"""
    id: int
    conversation_id: str
    user_message: str
    ai_response: str
    message_chain: Optional[dict] = None
    round_number: int
    meta_data: Optional[dict] = None
    create_time: str


class SessionResponse(BaseModel):
    conversation_id: str
    title: str
    create_time: str
    update_time: str
    user_id: Optional[str] = None
    round_count: int = 0
    meta_data: Optional[dict] = None


class SessionListResponse(BaseModel):
    total: int
    sessions: List[SessionResponse]


@router.get("/")
async def list_sessions(
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
):
    """获取会话列表"""
    try:
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
            # 获取会话的轮次数
            round_count = database_service.message_service.get_message_rounds_count(
                session.get('conversation_id')
            )

            sessions_data.append({
                "conversation_id": session.get('conversation_id'),
                "title": session.get('title', ''),
                "create_time": session.get('create_time'),
                "update_time": session.get('update_time'),
                "user_id": session.get('user_id'),
                "round_count": round_count,
                "meta_data": session.get('meta_data', {})
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
        logger.info(f"获取会话详情: conversation_id={conversation_id}")

        # 使用 session_service 获取会话
        session = database_service.session_service.get_session(conversation_id)
        if not session:
            logger.warning(f"会话不存在: {conversation_id}")
            return fail_response(message="会话不存在")

        # 使用 message_service 获取轮次数
        round_count = database_service.message_service.get_message_rounds_count(conversation_id)

        session_data = {
            "conversation_id": session.get('conversation_id'),
            "title": session.get('title', ''),
            "create_time": session.get('create_time'),
            "update_time": session.get('update_time'),
            "user_id": session.get('user_id'),
            "round_count": round_count,
            "meta_data": session.get('meta_data', {})
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
        conversation_id = session_data.conversation_id or str(uuid.uuid4())
        logger.info(f"创建会话: conversation_id={conversation_id}, user_id={session_data.user_id}")

        # 使用 session_service 创建会话
        success = database_service.session_service.create_session(
            conversation_id=conversation_id,
            title=session_data.title,
            user_id=session_data.user_id,
            meta_data=session_data.meta_data
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


@router.put("/{conversation_id}")
async def update_session(conversation_id: str, update_data: SessionUpdate):
    """更新会话信息（如标题）"""
    try:
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
async def get_conversation_messages(
        conversation_id: str,
        limit: int = 50,
        offset: int = 0,
        order_desc: bool = False
):
    """
    获取会话的对话轮次列表（新接口）
    每条记录代表一次完整的问答轮次
    """
    try:
        logger.info(
            f"获取会话轮次: conversation_id={conversation_id}, limit={limit}, offset={offset}, order_desc={order_desc}")

        # 检查会话是否存在
        session = database_service.session_service.get_session(conversation_id)
        if not session:
            logger.warning(f"会话不存在，无法获取轮次: {conversation_id}")
            return fail_response(message="会话不存在")

        # 使用 message_service 获取对话轮次
        rounds = database_service.message_service.load_messages(
            conversation_id=conversation_id,
            limit=limit,
            offset=offset,
            order_desc=order_desc
        )

        # 获取轮次总数
        total_rounds = database_service.message_service.get_message_rounds_count(conversation_id)

        rounds_data = {
            "conversation_id": conversation_id,
            "conversation_title": session.get('title', ''),
            "total": total_rounds,
            "returned": len(rounds),
            "offset": offset,
            "limit": limit,
            "rounds": rounds  # 修改：messages -> rounds
        }

        return success_response(
            data=rounds_data,
            message="获取会话轮次成功"
        )

    except Exception as e:
        logger.error(f"获取会话轮次失败: {str(e)}")
        return fail_response(message=f"获取会话轮次失败: {str(e)}")


@router.get("/statistics")
async def get_statistics(user_id: Optional[str] = None):
    """获取会话统计信息"""
    try:
        logger.info(f"获取统计信息: user_id={user_id}")

        # 获取所有会话
        sessions = database_service.session_service.list_sessions(
            user_id=user_id,
            limit=10000,  # 获取所有会话用于统计
            offset=0
        )

        total_sessions = len(sessions)
        total_rounds = 0
        sessions_with_rounds = 0

        # 统计轮次总数
        for session in sessions:
            conversation_id = session.get('conversation_id')
            if conversation_id:
                round_count = database_service.message_service.get_message_rounds_count(conversation_id)
                total_rounds += round_count
                if round_count > 0:
                    sessions_with_rounds += 1

        stats = {
            "total_sessions": total_sessions,
            "total_rounds": total_rounds,  # 修改：total_messages -> total_rounds
            "sessions_with_rounds": sessions_with_rounds,  # 修改：sessions_with_messages -> sessions_with_rounds
            "avg_rounds_per_session": total_rounds / total_sessions if total_sessions > 0 else 0,
            "user_id": user_id or "all"
        }

        return success_response(
            data=stats,
            message="获取统计信息成功"
        )

    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        return fail_response(message=f"获取统计信息失败: {str(e)}")
