# service/channel_service.py
import json
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy import func
from soma.config.logging_config import get_logger
from soma.model.db_model import ChannelConfigModel, ChannelStatusModel
from soma.service.database_manager import DatabaseManager

logger = get_logger(__name__)


class ChannelService:
    """通道服务 - 负责ChannelConfigModel和ChannelStatusModel的操作"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    # ==================== ChannelConfig CRUD ====================

    def create_channel(self, platform: str, name: str, config: Dict,
                      description: str = None, enabled: int = 0) -> Optional[int]:
        """创建新的通道配置"""
        session = self.db_manager.get_session()
        try:
            db_channel = ChannelConfigModel(
                platform=platform,
                name=name,
                config=json.dumps(config),
                description=description,
                enabled=enabled
            )
            session.add(db_channel)
            session.commit()
            channel_id = db_channel.id

            # 同时创建状态记录
            db_status = ChannelStatusModel(
                channel_id=channel_id,
                status='disconnected'
            )
            session.add(db_status)
            session.commit()

            return channel_id
        except Exception as e:
            session.rollback()
            logger.error(f"创建通道配置失败: {str(e)}")
            return None
        finally:
            session.close()

    def get_channel(self, channel_id: int) -> Optional[Dict]:
        """获取单个通道配置"""
        session = self.db_manager.get_session()
        try:
            db_channel = session.query(ChannelConfigModel).filter(
                ChannelConfigModel.id == channel_id
            ).first()
            return db_channel.to_dict() if db_channel else None
        except Exception as e:
            logger.error(f"获取通道配置失败: {str(e)}")
            return None
        finally:
            session.close()

    def get_channel_with_status(self, channel_id: int) -> Optional[Dict]:
        """获取通道配置及状态"""
        session = self.db_manager.get_session()
        try:
            db_channel = session.query(ChannelConfigModel).filter(
                ChannelConfigModel.id == channel_id
            ).first()
            if not db_channel:
                return None

            result = db_channel.to_dict()
            if db_channel.status:
                result['status_info'] = db_channel.status.to_dict()
            return result
        except Exception as e:
            logger.error(f"获取通道配置失败: {str(e)}")
            return None
        finally:
            session.close()

    def list_channels(self, platform: str = None, enabled: int = None,
                     limit: int = 100, offset: int = 0) -> List[Dict]:
        """获取通道列表"""
        session = self.db_manager.get_session()
        try:
            query = session.query(ChannelConfigModel)

            if platform:
                query = query.filter(ChannelConfigModel.platform == platform)
            if enabled is not None:
                query = query.filter(ChannelConfigModel.enabled == enabled)

            results = query.order_by(ChannelConfigModel.create_time.desc()) \
                .limit(limit).offset(offset).all()

            channels = []
            for db_channel in results:
                ch = db_channel.to_dict()
                if db_channel.status:
                    ch['status_info'] = db_channel.status.to_dict()
                channels.append(ch)

            return channels
        except Exception as e:
            logger.error(f"获取通道列表失败: {str(e)}")
            return []
        finally:
            session.close()

    def list_enabled_channels(self, platform: str = None) -> List[Dict]:
        """获取所有已启用的通道"""
        session = self.db_manager.get_session()
        try:
            query = session.query(ChannelConfigModel).filter(ChannelConfigModel.enabled == 1)
            if platform:
                query = query.filter(ChannelConfigModel.platform == platform)
            results = query.all()

            channels = []
            for db_channel in results:
                ch = db_channel.to_dict()
                ch['config'] = json.loads(db_channel.config) if isinstance(db_channel.config, str) else db_channel.config
                channels.append(ch)

            return channels
        except Exception as e:
            logger.error(f"获取启用通道列表失败: {str(e)}")
            return []
        finally:
            session.close()

    def update_channel(self, channel_id: int, name: str = None,
                       config: Dict = None, description: str = None,
                       enabled: int = None) -> bool:
        """更新通道配置"""
        session = self.db_manager.get_session()
        try:
            db_channel = session.query(ChannelConfigModel).filter(
                ChannelConfigModel.id == channel_id
            ).first()

            if not db_channel:
                return False

            if name is not None:
                db_channel.name = name
            if config is not None:
                db_channel.config = json.dumps(config)
            if description is not None:
                db_channel.description = description
            if enabled is not None:
                db_channel.enabled = enabled

            db_channel.update_time = datetime.now()
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新通道配置失败: {str(e)}")
            return False
        finally:
            session.close()

    def delete_channel(self, channel_id: int) -> bool:
        """删除通道配置"""
        session = self.db_manager.get_session()
        try:
            db_channel = session.query(ChannelConfigModel).filter(
                ChannelConfigModel.id == channel_id
            ).first()
            if not db_channel:
                return False

            session.delete(db_channel)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"删除通道配置失败: {str(e)}")
            return False
        finally:
            session.close()

    def set_channel_enabled(self, channel_id: int, enabled: int) -> bool:
        """启用或停用通道"""
        return self.update_channel(channel_id, enabled=enabled)

    # ==================== ChannelStatus CRUD ====================

    def update_channel_status(self, channel_id: int, status: str,
                              error_message: str = None) -> bool:
        """更新通道状态"""
        session = self.db_manager.get_session()
        try:
            db_status = session.query(ChannelStatusModel).filter(
                ChannelStatusModel.channel_id == channel_id
            ).first()

            if not db_status:
                # 创建状态记录
                db_status = ChannelStatusModel(
                    channel_id=channel_id,
                    status=status,
                    error_message=error_message,
                    last_heartbeat=datetime.now()
                )
                session.add(db_status)
            else:
                db_status.status = status
                db_status.error_message = error_message
                db_status.last_heartbeat = datetime.now()
                db_status.update_time = datetime.now()

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新通道状态失败: {str(e)}")
            return False
        finally:
            session.close()

    def get_channel_status(self, channel_id: int) -> Optional[Dict]:
        """获取通道状态"""
        session = self.db_manager.get_session()
        try:
            db_status = session.query(ChannelStatusModel).filter(
                ChannelStatusModel.channel_id == channel_id
            ).first()
            return db_status.to_dict() if db_status else None
        except Exception as e:
            logger.error(f"获取通道状态失败: {str(e)}")
            return None
        finally:
            session.close()