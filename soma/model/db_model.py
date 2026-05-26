# model/db_model.py
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy import (
    Column, String, Text, Integer,
    DateTime, ForeignKey, Index, JSON
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class SessionModel(Base):
    """会话表模型"""
    __tablename__ = 'tb_session'

    session_id = Column(String(255), primary_key=True)
    title = Column(String(500))
    user_id = Column(String(255), nullable=True)
    meta_data = Column(Text, nullable=True)  # JSON string
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系：一个会话有多条消息记录
    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan")

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "user_id": self.user_id,
            "meta_data": json.loads(self.meta_data) if self.meta_data else None,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }


class MessageModel(Base):
    """
    消息表模型 - 重新设计
    每条记录代表一次完整的对话轮次（一问一答）
    """
    __tablename__ = 'tb_message'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), ForeignKey('tb_session.session_id', ondelete='CASCADE'))
    user_message = Column(Text, nullable=False)  # 用户输入的消息
    ai_message = Column(Text, nullable=False)  # AI 的最终响应
    # 完整的消息链（JSON 格式，存储完整的交互过程）
    # 包含：AIMessage (可能带 tool_calls), ToolMessage 等
    message_chain = Column(JSON, nullable=True)  # 存储完整的消息链
    round_number = Column(Integer, nullable=False)  # 对话轮次序号（从1开始递增）
    meta_data = Column(JSON, nullable=True)  # 额外的元数据，如 token 使用量、处理时间等
    create_time = Column(DateTime, default=datetime.now)

    # 关系
    session = relationship("SessionModel", back_populates="messages")

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_message": self.user_message,
            "ai_message": self.ai_message,
            "message_chain": self.message_chain,
            "round_number": self.round_number,
            "meta_data": self.meta_data,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }

    def to_langchain_messages(self) -> List[Any]:
        """
        将存储的消息转换为 LangChain 消息对象列表
        返回完整的对话历史（包含用户消息、AI消息、工具消息等）
        """
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

        messages = []

        # 添加用户消息
        messages.append(HumanMessage(content=self.user_message))

        # 重建消息链
        if self.message_chain:
            for msg_data in self.message_chain:
                msg_type = msg_data.get('type')
                content = msg_data.get('content', '')

                if msg_type == 'ai':
                    ai_msg = AIMessage(content=content)
                    tool_calls = msg_data.get('tool_calls', [])
                    if tool_calls:
                        ai_msg.tool_calls = tool_calls
                    messages.append(ai_msg)
                elif msg_type == 'tool':
                    tool_call_id = msg_data.get('tool_call_id', '')
                    tool_msg = ToolMessage(content=content, tool_call_id=tool_call_id)
                    messages.append(tool_msg)

        # 添加 AI 最终响应（如果不在消息链中）
        if not any(isinstance(msg, AIMessage) and msg.content == self.ai_message for msg in messages):
            messages.append(AIMessage(content=self.ai_message))

        return messages


# 创建索引
Index('idx_messages_session_id', MessageModel.session_id)
Index('idx_messages_create_time', MessageModel.session_id, MessageModel.create_time)
Index('idx_sessions_user_id', SessionModel.user_id)
Index('idx_sessions_update_time', SessionModel.update_time)


class ChannelConfigModel(Base):
    """IM通道配置表 - 支持飞书、企业微信等多个平台的多机器人配置"""
    __tablename__ = 'tb_channel_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False)  # feishu / wecom
    name = Column(String(255), nullable=False)     # 用户自定义名称
    enabled = Column(Integer, default=0)           # 0=停用, 1=启用
    config = Column(JSON, nullable=False)            # 平台凭证JSON
    description = Column(Text, nullable=True)       # 描述
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    status = relationship("ChannelStatusModel", back_populates="channel", uselist=False, cascade="all, delete-orphan")

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "platform": self.platform,
            "name": self.name,
            "enabled": self.enabled,
            "config": self.config,
            "description": self.description,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }


class ChannelStatusModel(Base):
    """IM通道运行时状态表"""
    __tablename__ = 'tb_channel_status'

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(Integer, ForeignKey('tb_channel_config.id', ondelete='CASCADE'), unique=True)
    status = Column(String(50), default='disconnected')  # connected / disconnected / error
    last_heartbeat = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    channel = relationship("ChannelConfigModel", back_populates="status")

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "status": self.status,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "error_message": self.error_message,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
