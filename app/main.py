# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from config.settings import settings
from config.logging_config import setup_logging, get_logger
from web.routers import api_router
from web.middlewares.error_handler import register_error_handlers
from core.agent.agent_manager import agent_manager
from core.websocket.websocket_manager import ws_connection_manager
from service.database_service import database_service

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理应用生命周期，在启动时初始化 Agent 和数据库服务"""

    # 启动时初始化
    logger.info("系统启动，开始初始化...")
    try:
        # 初始化数据库服务容器
        database_service.initialize()
        logger.info("数据库服务容器初始化成功")

        # 初始化 AgentManager（单例，全局共享）
        await agent_manager.initialize()
        logger.info("AgentManager 初始化成功")

        app.state.agent_manager = agent_manager
        app.state.ws_connection_manager = ws_connection_manager
        app.state.database_service = database_service

        logger.info("系统初始化成功")
    except Exception as e:
        logger.error(f"系统初始化失败: {e}")
        import traceback
        traceback.print_exc()
        raise

    yield

    # 关闭时清理
    logger.info("系统关闭，清理资源...")
    try:
        # 关闭数据库服务容器
        database_service.close()
        logger.info("数据库服务容器已关闭")

        # 关闭 AgentManager
        await agent_manager.close()
        logger.info("AgentManager 已关闭")

        # 关闭所有活跃的 WebSocket 连接
        await ws_connection_manager.close_all_connections()

        logger.info("资源清理完成")
    except Exception as e:
        logger.error(f"资源清理失败: {e}")


def create_app() -> FastAPI:
    """创建FastAPI应用工厂函数"""

    # 设置日志
    setup_logging()

    # 创建FastAPI应用
    app = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan
    )

    # 配置CORS
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(api_router, prefix="/api")

    # 注册错误处理
    register_error_handlers(app)

    logger.info(f"FastAPI应用创建成功，运行模式: {'debug' if settings.DEBUG else 'production'}")

    return app


# 创建全局app实例
app = create_app()

if __name__ == '__main__':
    import uvicorn

    logger.info(f"使用Uvicorn服务器启动...")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
