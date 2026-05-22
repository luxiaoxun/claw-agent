# soma/channel/channel_manager.py
"""
ChannelManager - 从数据库加载通道配置，动态管理多个IM通道适配器
"""
from typing import Dict, Optional
import json
from soma.config.logging_config import get_logger
from soma.service.database_service import database_service

logger = get_logger(__name__)


class ChannelManager:
    """
    管理所有IM通道适配器
    从数据库加载配置，动态启动/停止各平台适配器
    """

    def __init__(self):
        self._adapters: Dict[int, object] = {}  # channel_id -> adapter instance

    def _create_feishu_adapter(self, channel_id: int, config: Dict):
        """创建飞书适配器"""
        from soma.channel.feishu.feishu_adapter import FeishuAdapter
        adapter = FeishuAdapter()
        adapter._channel_id = channel_id
        adapter._config = config
        return adapter

    def _create_wecom_adapter(self, channel_id: int, config: Dict):
        """创建企业微信适配器"""
        from soma.channel.wecom.wecom_adapter import WeComAdapter
        adapter = WeComAdapter()
        adapter._channel_id = channel_id
        adapter._config = config
        return adapter

    async def start_all(self):
        """从数据库加载所有已启用的通道并启动"""
        try:
            enabled_channels = database_service.channel_service.list_enabled_channels()
            logger.info(f"从数据库加载到 {len(enabled_channels)} 个已启用的IM通道")

            for channel in enabled_channels:
                self.start_channel(channel)

        except Exception as e:
            logger.error(f"启动所有通道失败: {e}", exc_info=True)

    def start_channel(self, channel: Dict):
        """启动单个通道"""
        try:
            channel_id = channel['id']
            platform = channel['platform']
            config = channel['config']

            # 解析config JSON
            if isinstance(config, str):
                config = json.loads(config)

            # 根据平台创建适配器
            if platform == 'feishu':
                adapter = self._create_feishu_adapter(channel_id, config)
                adapter.start_with_config(config)
                self._adapters[channel_id] = adapter
                database_service.channel_service.update_channel_status(channel_id, 'connected')
                logger.info(f"飞书通道 {channel_id} 已启动: {channel['name']}")

            elif platform == 'wecom':
                adapter = self._create_wecom_adapter(channel_id, config)
                adapter.start_with_config(config)
                self._adapters[channel_id] = adapter
                database_service.channel_service.update_channel_status(channel_id, 'connected')
                logger.info(f"企业微信通道 {channel_id} 已启动: {channel['name']}")

            else:
                logger.warning(f"不支持的平台类型: {platform}")

        except Exception as e:
            logger.error(f"启动通道 {channel.get('id')} 失败: {e}", exc_info=True)
            database_service.channel_service.update_channel_status(
                channel.get('id'), 'error', str(e)
            )

    def stop_channel(self, channel_id: int):
        """停止单个通道"""
        try:
            if channel_id in self._adapters:
                adapter = self._adapters[channel_id]
                adapter.stop()
                del self._adapters[channel_id]
                database_service.channel_service.update_channel_status(channel_id, 'disconnected')
                logger.info(f"通道 {channel_id} 已停止")
        except Exception as e:
            logger.error(f"停止通道 {channel_id} 失败: {e}")

    def restart_channel(self, channel_id: int):
        """重启单个通道"""
        self.stop_channel(channel_id)
        channel = database_service.channel_service.get_channel(channel_id)
        if channel and channel.get('enabled'):
            self.start_channel(channel)

    async def stop_all(self):
        """停止所有通道"""
        try:
            for channel_id in list(self._adapters.keys()):
                self.stop_channel(channel_id)
            logger.info("所有通道已停止")
        except Exception as e:
            logger.error(f"停止所有通道失败: {e}")

    def get_adapter(self, channel_id: int) -> Optional[object]:
        """获取指定通道的适配器"""
        return self._adapters.get(channel_id)

    def get_all_adapters(self) -> Dict[int, object]:
        """获取所有已启动的适配器"""
        return self._adapters.copy()


# Global singleton
channel_manager = ChannelManager()
