# core/chat/session_service.py
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from sqlalchemy import (
    create_engine, func, delete
)
from sqlalchemy.orm import sessionmaker, Session
from config.logging_config import get_logger
from config.settings import WORKSPACE_DIR
from core.model.db_model import Base, SessionModel, MessageModel

logger = get_logger(__name__)


class SessionDatabase:
    """SQLAlchemy 版本的会话数据库管理类"""

    def __init__(self, db_path: str = None):
        # 使用 WORKSPACE_DIR 构建数据库路径
        if db_path is None:
            db_path = os.path.join(WORKSPACE_DIR, "chat_sessions.db")

        self.db_path = db_path

        # 延迟初始化，不在这里创建数据库连接
        self.engine = None
        self.SessionLocal = None
        self._initialized = False

    def _ensure_initialized(self):
        """确保数据库已初始化（延迟初始化）"""
        if not self._initialized:
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

            # 创建表
            Base.metadata.create_all(bind=self.engine)

            self._initialized = True
            logger.info(f"SQLAlchemy 数据库初始化完成: {self.db_path}")

    def _get_session(self) -> Session:
        """获取数据库会话"""
        self._ensure_initialized()
        return self.SessionLocal()

    def create_session(self, conversation_id: str, title: str = None,
                       user_id: str = None, metadata: Dict = None) -> bool:
        """创建新会话"""
        session = self._get_session()
        try:
            db_session = SessionModel(
                conversation_id=conversation_id,
                title=title or f"会话_{conversation_id[:8]}",
                user_id=user_id,
                meta_data=json.dumps(metadata) if metadata else None  # 使用 meta_data
            )
            session.add(db_session)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"创建会话失败: {str(e)}")
            return False
        finally:
            session.close()

    def get_session(self, conversation_id: str) -> Optional[Dict]:
        """获取会话信息"""
        session = self._get_session()
        try:
            db_session = session.query(SessionModel).filter(
                SessionModel.conversation_id == conversation_id
            ).first()
            return db_session.to_dict() if db_session else None
        except Exception as e:
            logger.error(f"获取会话失败: {str(e)}")
            return None
        finally:
            session.close()

    def get_or_create_session(self, conversation_id: str, user_id: str = None) -> Dict:
        """获取或创建会话"""
        session = self._get_session()
        try:
            db_session = session.query(SessionModel).filter(
                SessionModel.conversation_id == conversation_id
            ).first()

            if not db_session:
                db_session = SessionModel(
                    conversation_id=conversation_id,
                    title=f"会话_{conversation_id[:8]}",
                    user_id=user_id
                )
                session.add(db_session)
                session.commit()

            return db_session.to_dict()
        except Exception as e:
            session.rollback()
            logger.error(f"获取或创建会话失败: {str(e)}")
            return {}
        finally:
            session.close()

    def save_messages(self, conversation_id: str, messages: List[Dict]):
        """保存消息到数据库"""
        session = self._get_session()
        try:
            # 先确保会话存在
            db_session = session.query(SessionModel).filter(
                SessionModel.conversation_id == conversation_id
            ).first()

            if not db_session:
                # 自动创建会话
                db_session = SessionModel(
                    conversation_id=conversation_id,
                    title=f"会话_{conversation_id[:8]}"
                )
                session.add(db_session)
                session.flush()

            for msg in messages:
                # 检查消息是否已存在（简单去重）
                existing = session.query(MessageModel).filter(
                    MessageModel.conversation_id == conversation_id,
                    MessageModel.content == msg.get('content', ''),
                    func.abs(func.strftime('%s', MessageModel.create_time) -
                             func.strftime('%s', datetime.now())) < 5
                ).first()

                if not existing:
                    db_message = MessageModel(
                        conversation_id=conversation_id,
                        message_type=msg.get('type', 'unknown'),
                        content=msg.get('content', ''),
                        tool_calls=json.dumps(msg.get('tool_calls', [])) if msg.get('tool_calls') else None,
                        create_time=msg.get('create_time', datetime.now())
                    )
                    session.add(db_message)

            # 更新会话的更新时间
            db_session.update_time = datetime.now()
            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"保存消息失败: {str(e)}")
        finally:
            session.close()

    def load_messages(self, conversation_id: str, limit: int = 100) -> List[Dict]:
        """加载会话的历史消息"""
        session = self._get_session()
        try:
            messages = session.query(MessageModel).filter(
                MessageModel.conversation_id == conversation_id
            ).order_by(MessageModel.create_time.asc()).limit(limit).all()

            return [msg.to_dict() for msg in messages]
        except Exception as e:
            logger.error(f"加载消息失败: {str(e)}")
            return []
        finally:
            session.close()

    def list_sessions(self, user_id: str = None, limit: int = 50, offset: int = 0) -> List[Dict]:
        """获取会话列表"""
        session = self._get_session()
        try:
            query = session.query(
                SessionModel,
                func.count(MessageModel.id).label('message_count')
            ).outerjoin(
                MessageModel, SessionModel.conversation_id == MessageModel.conversation_id
            )

            if user_id:
                query = query.filter(SessionModel.user_id == user_id)

            results = query.group_by(SessionModel.conversation_id) \
                .order_by(SessionModel.update_time.desc()) \
                .limit(limit).offset(offset).all()

            sessions = []
            for db_session, msg_count in results:
                session_dict = db_session.to_dict()
                session_dict['message_count'] = msg_count
                sessions.append(session_dict)

            return sessions
        except Exception as e:
            logger.error(f"获取会话列表失败: {str(e)}")
            return []
        finally:
            session.close()

    def delete_session(self, conversation_id: str) -> bool:
        """删除会话（级联删除消息）"""
        session = self._get_session()
        try:
            # 使用 delete 语句实现级联删除
            stmt = delete(SessionModel).where(SessionModel.conversation_id == conversation_id)
            result = session.execute(stmt)
            session.commit()
            return result.rowcount > 0
        except Exception as e:
            session.rollback()
            logger.error(f"删除会话失败: {str(e)}")
            return False
        finally:
            session.close()

    def update_session_title(self, conversation_id: str, title: str) -> bool:
        """更新会话标题"""
        session = self._get_session()
        try:
            db_session = session.query(SessionModel).filter(
                SessionModel.conversation_id == conversation_id
            ).first()

            if db_session:
                db_session.title = title
                db_session.update_time = datetime.now()
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"更新会话标题失败: {str(e)}")
            return False
        finally:
            session.close()
