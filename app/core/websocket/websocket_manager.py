# core/websocket/websocket_manager.py
from typing import Dict, Optional
from fastapi import WebSocket
from core.chat.conversation_manager import ConversationManager
from config.logging_config import get_logger
import uuid

logger = get_logger(__name__)


class WebSocketConnectionManager:
    """WebSocket 连接管理器 - 管理每个连接的会话状态"""

    def __init__(self):
        self.active_connections: Dict[str, Dict] = {}

    async def connect(self, websocket: WebSocket, client_id: str = None) -> str:
        """
        接受新连接并创建会话

        Args:
            websocket: WebSocket 连接对象
            client_id: 客户端ID（可选，不提供则自动生成）

        Returns:
            client_id: 客户端ID
        """
        await websocket.accept()

        if not client_id:
            client_id = str(uuid.uuid4())

        # 创建新的会话管理器（不立即初始化，等待 conversation_id）
        session_manager = ConversationManager()

        # 存储连接信息
        self.active_connections[client_id] = {
            "websocket": websocket,
            "conversation_manager": session_manager,
            "conversation_id": None,
            "initialized": False
        }

        logger.info(f"WebSocket 客户端 {client_id} 已连接")
        return client_id

    async def initialize_manager(self, client_id: str, conversation_id: str = None,
                                 user_id: str = None) -> ConversationManager:
        """
        初始化客户端的会话管理器（异步）

        Args:
            client_id: 客户端ID
            conversation_id: 会话ID（可选）
            user_id: 用户ID（可选）

        Returns:
            ConversationManager: 初始化后的会话管理器
        """
        conn = self.active_connections.get(client_id)
        if not conn:
            raise ValueError(f"客户端 {client_id} 不存在")

        session_manager = conn["conversation_manager"]

        # 如果已经初始化且 conversation_id 相同，直接返回
        if conn.get("initialized") and session_manager.conversation_id == conversation_id:
            logger.debug(f"客户端 {client_id} 的会话管理器已初始化，conversation_id: {conversation_id}")
            return session_manager

        # 初始化会话管理器
        try:
            await session_manager.initialize(
                conversation_id=conversation_id,
                user_id=user_id
            )

            # 更新连接信息
            conn["conversation_id"] = session_manager.conversation_id
            conn["initialized"] = True

            logger.info(f"客户端 {client_id} 的会话管理器已初始化，conversation_id: {session_manager.conversation_id}")
            return session_manager

        except Exception as e:
            logger.error(f"初始化客户端 {client_id} 的会话管理器失败: {str(e)}")
            raise

    async def update_conversation_id(self, client_id: str, conversation_id: str):
        """
        更新客户端的会话ID

        Args:
            client_id: 客户端ID
            conversation_id: 新的会话ID
        """
        conn = self.active_connections.get(client_id)
        if conn:
            conn["conversation_id"] = conversation_id
            manager = conn["conversation_manager"]
            if manager:
                manager.conversation_id = conversation_id
                # 如果已初始化且需要加载新会话的历史，重新加载
                if conn.get("initialized") and conversation_id:
                    await manager.load_history()
                    logger.info(
                        f"客户端 {client_id} 切换到会话 {conversation_id}，加载了 {len(manager.conversation_history)} 条历史消息")
            logger.debug(f"客户端 {client_id} 的会话ID已更新为 {conversation_id}")

    def disconnect(self, client_id: str):
        """断开连接（同步版本）"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket 客户端 {client_id} 已断开")

    async def disconnect_and_cleanup(self, client_id: str):
        """断开连接并清理资源（异步版本）"""
        if client_id in self.active_connections:
            manager = self.active_connections[client_id].get("conversation_manager")
            if manager:
                try:
                    await manager.close()
                    logger.info(f"客户端 {client_id} 的会话管理器已关闭")
                except Exception as e:
                    logger.error(f"关闭客户端 {client_id} 的会话管理器时出错: {str(e)}")
            del self.active_connections[client_id]
            logger.info(f"WebSocket 客户端 {client_id} 已断开并清理资源")

    def get_manager(self, client_id: str) -> Optional[ConversationManager]:
        """获取客户端的会话管理器"""
        conn = self.active_connections.get(client_id)
        return conn.get("conversation_manager") if conn else None

    def get_websocket(self, client_id: str) -> Optional[WebSocket]:
        """获取客户端的 WebSocket 连接"""
        conn = self.active_connections.get(client_id)
        return conn.get("websocket") if conn else None

    def get_conversation_id(self, client_id: str) -> Optional[str]:
        """获取客户端的当前会话ID"""
        conn = self.active_connections.get(client_id)
        return conn.get("conversation_id") if conn else None

    async def send_to_client(self, client_id: str, message: dict):
        """向指定客户端发送消息"""
        websocket = self.get_websocket(client_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"向客户端 {client_id} 发送消息失败: {str(e)}")

    async def broadcast(self, message: dict, exclude_client: str = None):
        """向所有客户端广播消息"""
        for client_id, conn in self.active_connections.items():
            if client_id != exclude_client:
                await self.send_to_client(client_id, message)

    def get_active_connections_count(self) -> int:
        """获取活跃连接数"""
        return len(self.active_connections)

    def is_client_connected(self, client_id: str) -> bool:
        """检查客户端是否已连接"""
        return client_id in self.active_connections


# 全局实例
ws_connection_manager = WebSocketConnectionManager()
