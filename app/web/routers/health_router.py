# web/routers/health_router.py
from fastapi import APIRouter
from common.response import success_response, fail_response
from core.agent.agent_manager import agent_manager
from config.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/status")
async def health_status():
    """健康检查"""
    try:
        agent_initialized = agent_manager.is_initialized()

        tools_loaded = 0
        if agent_initialized:
            tools_loaded = len(agent_manager.get_tools_info())
            # 健康状态，返回成功响应
            health_data = {
                "status": "healthy",
                "agent_initialized": True,
                "tools_loaded": tools_loaded
            }

            return success_response(
                data=health_data,
                message="Service is healthy"
            )
        else:
            # 未就绪状态，使用自定义响应码或失败响应
            health_data = {
                "status": "unhealthy",
                "agent_initialized": False,
                "tools_loaded": tools_loaded
            }
            # 可以使用失败响应，或自定义响应码
            return success_response(
                data=health_data,
                message="Service is unhealthy"
            )

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return fail_response()
