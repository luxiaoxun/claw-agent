# app/web/routers/im_router.py
from fastapi import APIRouter, Request
from app.common.response import success_response, fail_response
from app.channel.feishu.feishu_config import feishu_settings
from config.settings import settings
from config.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/im/status")
async def get_im_status():
    """Get IM channel status (enabled platforms, connection status, etc.)."""
    feishu_configured = bool(feishu_settings.app_id and feishu_settings.app_secret)

    return success_response({
        "im_enabled": settings.IM_ENABLED,
        "platforms": {
            "feishu": {
                "configured": feishu_configured,
                "enabled": settings.IM_ENABLED and feishu_configured,
            }
        }
    })


@router.get("/im/feishu/config")
async def get_feishu_config():
    """Get Feishu configuration status (without exposing secrets)."""
    return success_response({
        "app_id": feishu_settings.app_id[:8] + "***" if feishu_settings.app_id else None,
        "app_secret_set": bool(feishu_settings.app_secret),
        "verification_token_set": bool(feishu_settings.verification_token),
        "encrypt_key_set": bool(feishu_settings.encrypt_key),
    })


@router.post("/im/feishu/test")
async def test_feishu_connection():
    """Test Feishu connection by sending a test message."""
    # TODO: Implement test message sending
    return success_response({"message": "Test endpoint - not yet implemented"})