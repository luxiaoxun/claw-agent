from fastapi import APIRouter
from web.routes.chat_routes import router as chat_router
from web.routes.health_routes import router as health_router
from web.routes.tool_routes import router as tool_router
from web.routes.query_routes import router as query_router

# 创建API主路由器
api_router = APIRouter()

# 注册所有子路由器
api_router.include_router(chat_router)
api_router.include_router(health_router)
api_router.include_router(tool_router)
api_router.include_router(query_router)

# 导出统一的路由器
__all__ = ['api_router']