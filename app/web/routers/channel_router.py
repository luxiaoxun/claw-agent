# web/routers/channel_router.py
from fastapi import APIRouter, Body
from typing import Optional
from pydantic import BaseModel
from app.common.response import success_response, fail_response
from service.database_service import database_service
from config.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


class CreateChannelRequest(BaseModel):
    platform: str
    name: str
    config: dict
    description: Optional[str] = None
    enabled: int = 0


class UpdateChannelRequest(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    description: Optional[str] = None
    enabled: Optional[int] = None


def get_channel_service():
    return database_service.channel_service


# ==================== Channel CRUD ====================

@router.get("/channel/list")
async def list_channels(platform: Optional[str] = None, enabled: Optional[int] = None):
    """获取通道列表"""
    try:
        channels = get_channel_service().list_channels(platform=platform, enabled=enabled)
        logger.info(f"获取通道列表: platform={platform}, enabled={enabled}, count={len(channels)}")
        return success_response(data={"channels": channels, "total": len(channels)})
    except Exception as e:
        logger.error(f"获取通道列表失败: {e}")
        return fail_response(message=f"获取通道列表失败: {str(e)}")


@router.get("/channel/{channel_id}")
async def get_channel(channel_id: int):
    """获取单个通道配置"""
    try:
        channel = get_channel_service().get_channel_with_status(channel_id)
        if not channel:
            logger.warning(f"获取通道: 通道不存在, channel_id={channel_id}")
            return fail_response(message="通道不存在")
        logger.info(
            f"获取通道: channel_id={channel_id}, name={channel.get('name')}, platform={channel.get('platform')}")
        return success_response(data=channel)
    except Exception as e:
        logger.error(f"获取通道失败: channel_id={channel_id}, error={e}")
        return fail_response(message=f"获取通道失败: {str(e)}")


@router.post("/channel/create")
async def create_channel(body: CreateChannelRequest = Body(...)):
    """创建新的通道配置"""
    try:
        logger.info(f"创建通道: platform={body.platform}, name={body.name}, enabled={body.enabled}")
        channel_id = get_channel_service().create_channel(
            platform=body.platform,
            name=body.name,
            config=body.config,
            description=body.description,
            enabled=body.enabled
        )
        if channel_id:
            channel = get_channel_service().get_channel(channel_id)
            logger.info(f"通道创建成功: channel_id={channel_id}, name={body.name}")
            # If enabled, start the adapter immediately
            if channel and body.enabled:
                from app.main import app
                cm = getattr(app.state, 'channel_manager', None)
                if cm:
                    cm.start_channel(channel)
                    logger.info(f"通道已启用并启动适配器: channel_id={channel_id}")
            return success_response(data=channel, message="通道创建成功")
        logger.error(f"通道创建失败: name={body.name}")
        return fail_response(message="通道创建失败")
    except Exception as e:
        logger.error(f"创建通道失败: platform={body.platform}, name={body.name}, error={e}")
        return fail_response(message=f"创建通道失败: {str(e)}")


@router.post("/channel/{channel_id}/update")
async def update_channel(channel_id: int, body: UpdateChannelRequest = Body(...)):
    """更新通道配置"""
    try:
        logger.info(f"更新通道: channel_id={channel_id}, name={body.name}, enabled={body.enabled}")
        ok = get_channel_service().update_channel(
            channel_id=channel_id,
            name=body.name,
            config=body.config,
            description=body.description,
            enabled=body.enabled
        )
        if ok:
            channel = get_channel_service().get_channel_with_status(channel_id)
            logger.info(f"通道更新成功: channel_id={channel_id}")
            return success_response(data=channel, message="通道更新成功")
        logger.warning(f"通道更新失败: 通道不存在, channel_id={channel_id}")
        return fail_response(message="通道不存在或更新失败")
    except Exception as e:
        logger.error(f"更新通道失败: channel_id={channel_id}, error={e}")
        return fail_response(message=f"更新通道失败: {str(e)}")


@router.post("/channel/{channel_id}/delete")
async def delete_channel(channel_id: int):
    """删除通道配置"""
    try:
        logger.info(f"删除通道: channel_id={channel_id}")
        # Stop adapter first if running
        from app.main import app
        cm = getattr(app.state, 'channel_manager', None)
        if cm:
            cm.stop_channel(channel_id)
            logger.info(f"删除通道前已停止适配器: channel_id={channel_id}")

        ok = get_channel_service().delete_channel(channel_id)
        if ok:
            logger.info(f"通道删除成功: channel_id={channel_id}")
            return success_response(message="通道删除成功")
        logger.warning(f"通道删除失败: 通道不存在, channel_id={channel_id}")
        return fail_response(message="通道不存在或删除失败")
    except Exception as e:
        logger.error(f"删除通道失败: channel_id={channel_id}, error={e}")
        return fail_response(message=f"删除通道失败: {str(e)}")


@router.post("/channel/{channel_id}/enable")
async def enable_channel(channel_id: int):
    """启用通道"""
    try:
        logger.info(f"启用通道: channel_id={channel_id}")
        ok = get_channel_service().set_channel_enabled(channel_id, 1)
        if ok:
            channel = get_channel_service().get_channel(channel_id)
            if channel:
                from app.main import app
                cm = getattr(app.state, 'channel_manager', None)
                if cm:
                    cm.start_channel(channel)
                    logger.info(
                        f"通道已启用并通知ChannelManager启动: channel_id={channel_id}, name={channel.get('name')}")
            return success_response(data=channel, message="通道已启用")
        logger.warning(f"启用通道失败: 通道不存在, channel_id={channel_id}")
        return fail_response(message="通道不存在或启用失败")
    except Exception as e:
        logger.error(f"启用通道失败: channel_id={channel_id}, error={e}")
        return fail_response(message=f"启用通道失败: {str(e)}")


@router.post("/channel/{channel_id}/disable")
async def disable_channel(channel_id: int):
    """停用通道"""
    try:
        logger.info(f"停用通道: channel_id={channel_id}")
        ok = get_channel_service().set_channel_enabled(channel_id, 0)
        if ok:
            from app.main import app
            cm = getattr(app.state, 'channel_manager', None)
            if cm:
                cm.stop_channel(channel_id)
                logger.info(f"通道已停用并通知ChannelManager停止: channel_id={channel_id}")
            return success_response(message="通道已停用")
        logger.warning(f"停用通道失败: 通道不存在, channel_id={channel_id}")
        return fail_response(message="通道不存在或停用失败")
    except Exception as e:
        logger.error(f"停用通道失败: channel_id={channel_id}, error={e}")
        return fail_response(message=f"停用通道失败: {str(e)}")


@router.get("/channel/status/{channel_id}")
async def get_channel_status(channel_id: int):
    """获取通道状态"""
    try:
        status = get_channel_service().get_channel_status(channel_id)
        if status:
            logger.info(f"获取通道状态: channel_id={channel_id}, status={status.get('status')}")
            return success_response(data=status)
        logger.warning(f"获取通道状态: 状态不存在, channel_id={channel_id}")
        return fail_response(message="通道状态不存在")
    except Exception as e:
        logger.error(f"获取通道状态失败: channel_id={channel_id}, error={e}")
        return fail_response(message=f"获取通道状态失败: {str(e)}")
