# model/channel_model.py
import json
from datetime import datetime
from typing import Dict
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from soma.model.db_model import Base


class ChannelConfigModel(Base):
    """IM通道配置表 - 支持飞书、企业微信等多个平台的多机器人配置"""
    __tablename__ = 'tb_channel_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False)  # feishu / wecom
    name = Column(String(255), nullable=False)  # 用户自定义名称
    enabled = Column(Integer, default=0)  # 0=停用, 1=启用
    config = Column(JSON, nullable=False)  # 平台凭证JSON
    description = Column(Text, nullable=True)  # 描述
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
