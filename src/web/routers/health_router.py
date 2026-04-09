from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from core.models.responses import HealthResponse
from web.dependencies import get_conversation_manager
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/status")
async def health_status(conversation_manager=Depends(get_conversation_manager)):
    """健康检查"""
    try:
        agent_initialized = conversation_manager is not None

        tools_loaded = 0
        if agent_initialized and conversation_manager.agent_executor:
            tools_loaded = len(conversation_manager.agent_executor.tools)

        if agent_initialized:
            response = HealthResponse.healthy(
                tools_loaded=tools_loaded,
                version=settings.APP_VERSION
            )
            return response.to_dict()
        else:
            response = HealthResponse.initializing(version=settings.APP_VERSION)
            return JSONResponse(
                status_code=503,
                content=response.to_dict()
            )

    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )
