# core/model/db_model.py
import json
from datetime import datetime
from typing import Dict
from sqlalchemy import (
    Column, String, Text, Integer,
    DateTime, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class SessionModel(Base):
    """会话表模型"""
    __tablename__ = 'tb_session'

    conversation_id = Column(String(255), primary_key=True)
    title = Column(String(500))
    user_id = Column(String(255), nullable=True)
    # 修改：将 metadata 改为 meta_data，避免与 SQLAlchemy 保留字段冲突
    meta_data = Column(Text, nullable=True)  # JSON string - 重命名为 meta_data
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系：一个会话有多条消息
    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan")

    def to_dict(self) -> Dict:
        return {
            "conversation_id": self.conversation_id,
            "title": self.title,
            "user_id": self.user_id,
            "metadata": json.loads(self.meta_data) if self.meta_data else None,  # 返回时仍用 metadata 键名
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }


class MessageModel(Base):
    """消息表模型"""
    __tablename__ = 'tb_message'

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(255), ForeignKey('tb_session.conversation_id', ondelete='CASCADE'))
    message_type = Column(String(50))  # human, ai, tool
    content = Column(Text)
    tool_calls = Column(Text, nullable=True)  # JSON string
    create_time = Column(DateTime, default=datetime.now)

    # 关系
    session = relationship("SessionModel", back_populates="messages")

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "message_type": self.message_type,
            "content": self.content,
            "tool_calls": json.loads(self.tool_calls) if self.tool_calls else None,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }


# 创建索引
Index('idx_messages_conversation_id', MessageModel.conversation_id)
Index('idx_messages_create_time', MessageModel.conversation_id, MessageModel.create_time)
Index('idx_sessions_user_id', SessionModel.user_id)
Index('idx_sessions_update_time', SessionModel.update_time)
