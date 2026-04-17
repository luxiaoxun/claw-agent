# service/session_service.py
import json
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy import func, delete
from config.logging_config import get_logger
from core.model.db_model import SessionModel, MessageModel
from service.database_manager import DatabaseManager

logger = get_logger(__name__)


class SessionService:
    """会话服务 - 负责SessionModel的操作"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def create_session(self, conversation_id: str, title: str = None,
                       user_id: str = None, meta_data: Dict = None) -> bool:
        """创建新会话"""
        session = self.db_manager.get_session()
        try:
            db_session = SessionModel(
                conversation_id=conversation_id,
                title=title or f"会话_{conversation_id[:8]}",
                user_id=user_id,
                meta_data=json.dumps(meta_data) if meta_data else None
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
        session = self.db_manager.get_session()
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
        session = self.db_manager.get_session()
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

    def list_sessions(self, user_id: str = None, limit: int = 50, offset: int = 0) -> List[Dict]:
        """获取会话列表"""
        session = self.db_manager.get_session()
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
        session = self.db_manager.get_session()
        try:
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
        session = self.db_manager.get_session()
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
