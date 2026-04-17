# service/database_service.py
from typing import Optional
from config.logging_config import get_logger
from service.database_manager import DatabaseManager
from service.session_service import SessionService
from service.message_service import MessageService

logger = get_logger(__name__)


class DatabaseService:
    """数据库服务容器 - 单例模式，管理所有数据库相关服务"""

    _instance: Optional['DatabaseService'] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 避免重复初始化
        if self._initialized:
            return

        self.db_manager: Optional[DatabaseManager] = None
        self.session_service: Optional[SessionService] = None
        self.message_service: Optional[MessageService] = None
        self._initialized = True

    def initialize(self, db_path: str = None) -> None:
        """初始化所有数据库服务"""
        if self.db_manager is not None:
            logger.info("数据库服务已经初始化")
            return

        # 初始化数据库管理器
        self.db_manager = DatabaseManager(db_path)
        self.db_manager.initialize()

        # 初始化服务类
        self.session_service = SessionService(self.db_manager)
        self.message_service = MessageService(self.db_manager)

        logger.info("数据库服务容器初始化完成")

    def close(self) -> None:
        """关闭所有数据库服务"""
        if self.db_manager:
            self.db_manager.close()
            self.db_manager = None
            self.session_service = None
            self.message_service = None
            logger.info("数据库服务容器已关闭")

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self.db_manager is not None and self.db_manager._initialized


# 全局单例实例
database_service = DatabaseService()
