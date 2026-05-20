# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from config.settings import settings, SKILLS_DIR
from config.logging_config import setup_logging, get_logger
from web.routers import api_router
from web.middlewares.error_handler import register_error_handlers
from core.agent.agent_manager import agent_manager
from core.skill.skill_manager import SkillManager
from service.database_service import database_service
from core.websocket.websocket_service import websocket_service

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

        # 初始化 SkillManager
        skill_manager = SkillManager.initialize(SKILLS_DIR)
        skill_manager.load_all_skills()
        logger.info("SkillManager 初始化成功")

        # 初始化 AgentManager
        await agent_manager.initialize()
        logger.info("AgentManager 初始化成功")

        app.state.database_service = database_service
        app.state.skill_manager = skill_manager
        app.state.agent_manager = agent_manager
        app.state.websocket_service = websocket_service

        # 初始化 IM Channel 适配器 (飞书)
        if settings.IM_ENABLED:
            from app.channel.feishu import FeishuAdapter
            feishu_adapter = FeishuAdapter()
            await feishu_adapter.start()
            app.state.feishu_adapter = feishu_adapter
            logger.info("Feishu channel adapter 已启动")

            # 同时启动企业微信适配器
            from app.channel.wecom import wecom_adapter
            await wecom_adapter.start()
            app.state.wecom_adapter = wecom_adapter
            logger.info("WeCom channel adapter 已启动")
        else:
            logger.info("IM channel 未启用 (IM_ENABLED=false)")

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
        # 关闭 IM Channel 适配器
        if hasattr(app.state, 'feishu_adapter') and app.state.feishu_adapter:
            await app.state.feishu_adapter.stop()
            logger.info("Feishu channel adapter 已关闭")

        if hasattr(app.state, 'wecom_adapter') and app.state.wecom_adapter:
            await app.state.wecom_adapter.stop()
            logger.info("WeCom channel adapter 已关闭")

        # 关闭数据库服务容器
        database_service.close()
        logger.info("数据库服务容器已关闭")

        # 关闭 AgentManager
        await agent_manager.close()
        logger.info("AgentManager 已关闭")

        # 关闭 SkillManager
        if hasattr(app.state, 'skill_manager'):
            app.state.skill_manager.close()
            logger.info("SkillManager 已关闭")

        # 关闭所有活跃的 WebSocket 连接
        websocket_service.close()

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
