# service/database_manager.py
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.logging_config import get_logger
from config.settings import WORKSPACE_DIR
from core.model.db_model import Base

logger = get_logger(__name__)


class DatabaseManager:
    """数据库管理器 - 负责数据库初始化和连接管理"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(WORKSPACE_DIR, "chat_sessions.db")

        self.db_path = db_path
        self.engine = None
        self.SessionLocal = None
        self._initialized = False

    def initialize(self) -> None:
        """初始化数据库连接和表结构"""
        if self._initialized:
            return

        # 确保数据目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # 创建数据库引擎
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
            echo=False
        )

        # 创建会话工厂
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        # 创建所有表
        Base.metadata.create_all(bind=self.engine)

        self._initialized = True
        logger.info(f"数据库初始化完成: {self.db_path}")

    def get_session(self) -> Session:
        """获取数据库会话"""
        if not self._initialized:
            self.initialize()
        return self.SessionLocal()

    def close(self) -> None:
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
            self._initialized = False
            logger.info("数据库连接已关闭")