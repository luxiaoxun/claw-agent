# service/message_service.py
import json
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy import func
from config.logging_config import get_logger
from core.model.db_model import SessionModel, MessageModel
from service.database_manager import DatabaseManager

logger = get_logger(__name__)


class MessageService:
    """消息服务 - 负责MessageModel的操作"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def save_messages(self, conversation_id: str, messages: List[Dict]) -> bool:
        """保存消息到数据库"""
        session = self.db_manager.get_session()
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

            saved_count = 0
            for msg in messages:
                # 使用更精确的去重条件：相同会话、相同类型、相同内容、时间相近
                existing = session.query(MessageModel).filter(
                    MessageModel.conversation_id == conversation_id,
                    MessageModel.message_type == msg.get('type', 'unknown'),
                    MessageModel.content == msg.get('content', ''),
                    MessageModel.create_time >= datetime.now()  # 只检查最近的消息
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
                    saved_count += 1

            # 更新会话的更新时间
            if saved_count > 0:
                db_session.update_time = datetime.now()

            session.commit()
            logger.info(f"成功保存 {saved_count} 条新消息到会话 {conversation_id}")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"保存消息失败: {str(e)}")
            return False
        finally:
            session.close()

    def load_messages(self, conversation_id: str, limit: int = 100,
                      offset: int = 0, message_type: Optional[str] = None,
                      order_desc: bool = False) -> List[Dict]:
        """
        加载会话的历史消息

        Args:
            conversation_id: 会话ID
            limit: 返回消息数量限制
            offset: 偏移量，用于分页
            message_type: 可选，过滤特定类型的消息
            order_desc: 是否按时间倒序排列（True: 最新的在前，False: 最早的在前）
        """
        session = self.db_manager.get_session()
        try:
            query = session.query(MessageModel).filter(
                MessageModel.conversation_id == conversation_id
            )

            if message_type:
                query = query.filter(MessageModel.message_type == message_type)

            # 根据 order_desc 参数决定排序方式
            if order_desc:
                # 按时间倒序（最新的在前）
                query = query.order_by(MessageModel.create_time.desc())
            else:
                # 按时间正序（最早的在前）
                query = query.order_by(MessageModel.create_time.asc())

            messages = query.limit(limit).offset(offset).all()

            return [msg.to_dict() for msg in messages]
        except Exception as e:
            logger.error(f"加载消息失败: {str(e)}")
            return []
        finally:
            session.close()

    def delete_messages(self, conversation_id: str, before_time: datetime = None) -> bool:
        """
        删除会话中的消息（保留会话本身）

        Args:
            conversation_id: 会话ID
            before_time: 可选，删除指定时间之前的消息

        Returns:
            bool: 是否删除成功
        """
        session = self.db_manager.get_session()
        try:
            query = session.query(MessageModel).filter(
                MessageModel.conversation_id == conversation_id
            )

            if before_time:
                query = query.filter(MessageModel.create_time <= before_time)

            # 获取要删除的消息数量
            count = query.count()

            if count > 0:
                deleted_count = query.delete(synchronize_session=False)
                # 更新会话的更新时间
                session.query(SessionModel).filter(
                    SessionModel.conversation_id == conversation_id
                ).update({SessionModel.update_time: datetime.now()})

                session.commit()
                logger.info(f"从会话 {conversation_id} 删除了 {deleted_count} 条消息")
            else:
                logger.info(f"会话 {conversation_id} 中没有需要删除的消息")

            return True

        except Exception as e:
            session.rollback()
            logger.error(f"删除消息失败: {str(e)}")
            return False
        finally:
            session.close()

    def get_message_count(self, conversation_id: str) -> int:
        """获取会话的消息总数"""
        session = self.db_manager.get_session()
        try:
            count = session.query(MessageModel).filter(
                MessageModel.conversation_id == conversation_id
            ).count()
            return count
        except Exception as e:
            logger.error(f"获取消息数量失败: {str(e)}")
            return 0
        finally:
            session.close()
