from fastapi import APIRouter
from web.routers.chat_router import router as chat_router
from web.routers.health_router import router as health_router
from web.routers.tool_router import router as tool_router
from web.routers.query_router import router as query_router
from web.routers.session_router import router as session_router

# 创建API主路由器
api_router = APIRouter()

# 注册所有子路由器
api_router.include_router(chat_router)
api_router.include_router(health_router)
api_router.include_router(tool_router)
api_router.include_router(query_router)
api_router.include_router(session_router)

# 导出统一的路由器
__all__ = ['api_router']
