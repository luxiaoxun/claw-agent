from contextlib import asynccontextmanager
from fastapi import FastAPI
from config.settings import settings
from config.logging_config import setup_logging, get_logger
from web.routers import api_router
from web.middlewares.error_handler import register_error_handlers

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理应用生命周期，在启动时初始化Agent"""

    # 启动时初始化
    logger.info("系统启动，开始初始化Agent...")
    try:
        from core.agent.conversation_manager import ConversationManager
        from core.websocket_manager import ws_connection_manager

        # 初始化并直接赋值给app.state
        conversation_manager = await ConversationManager().initialize()
        app.state.conversation_manager = conversation_manager

        # 初始化 WebSocket 管理器
        ws_connection_manager.set_base_manager(conversation_manager)
        app.state.ws_connection_manager = ws_connection_manager

        logger.info("Agent初始化成功")
    except Exception as e:
        logger.error(f"Agent初始化失败: {e}")
        import traceback
        traceback.print_exc()
        raise

    yield

    # 关闭时清理
    logger.info("系统关闭，清理资源...")


def create_app() -> FastAPI:
    """创建FastAPI应用工厂函数"""

    # 设置日志
    setup_logging()

    # 创建FastAPI应用
    app = FastAPI(
        title="Claw Agent API",
        description="A simple AI agent",
        version="0.1.0",
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
    logger.info(f"注册的路由: {[route.path for route in app.routes]}")

    return app


# 创建全局app实例
app = create_app()

if __name__ == '__main__':
    import uvicorn

    logger.info(f"使用Uvicorn服务器启动...")
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
