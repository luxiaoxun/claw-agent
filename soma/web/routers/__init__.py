from fastapi import APIRouter
from soma.web.routers.chat_router import router as chat_router
from soma.web.routers.health_router import router as health_router
from soma.web.routers.tool_router import router as tool_router
from soma.web.routers.query_router import router as query_router
from soma.web.routers.session_router import router as session_router
from soma.web.routers.skill_router import router as skill_router
from soma.web.routers.workspace_router import router as workspace_router
from soma.web.routers.channel_router import router as channel_router
from soma.web.routers.rag_router import router as rag_router
from soma.web.routers.agent_router import router as agent_router

# 创建API主路由器
api_router = APIRouter()

# 注册所有子路由器
api_router.include_router(chat_router)
api_router.include_router(health_router)
api_router.include_router(tool_router)
api_router.include_router(query_router)
api_router.include_router(session_router)
api_router.include_router(skill_router)
api_router.include_router(workspace_router)
api_router.include_router(channel_router)
api_router.include_router(rag_router)
api_router.include_router(agent_router)

# 导出统一的路由器
__all__ = ['api_router']
