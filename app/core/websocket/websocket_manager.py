from typing import Dict, Optional
from fastapi import WebSocket
from core.agent.conversation_manager import ConversationManager
from config.logging_config import get_logger

logger = get_logger(__name__)


class WebSocketConnectionManager:
    """WebSocket 连接管理器 - 管理每个连接的会话状态"""

    def __init__(self):
        self.active_connections: Dict[str, Dict] = {}
        self.base_conversation_manager: Optional[ConversationManager] = None

    def set_base_manager(self, manager: ConversationManager):
        """设置基础的 conversation manager"""
        self.base_conversation_manager = manager

    async def connect(self, websocket: WebSocket, client_id: str = None):
        """接受新连接并创建会话"""
        await websocket.accept()

        if not client_id:
            import uuid
            client_id = str(uuid.uuid4())

        # 为每个连接创建独立的会话管理器（共享 Agent 但独立历史）
        session_manager = ConversationManager()
        session_manager.deep_agent = self.base_conversation_manager.deep_agent
        session_manager.conversation_history = []  # 独立的历史记录

        self.active_connections[client_id] = {
            "websocket": websocket,
            "conversation_manager": session_manager,
            "conversation_id": None
        }

        logger.info(f"WebSocket 客户端 {client_id} 已连接")
        return client_id

    def disconnect(self, client_id: str):
        """断开连接"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket 客户端 {client_id} 已断开")

    def get_manager(self, client_id: str) -> Optional[ConversationManager]:
        """获取客户端的会话管理器"""
        conn = self.active_connections.get(client_id)
        return conn.get("conversation_manager") if conn else None

    def get_websocket(self, client_id: str) -> Optional[WebSocket]:
        """获取客户端的 WebSocket 连接"""
        conn = self.active_connections.get(client_id)
        return conn.get("websocket") if conn else None

    async def send_to_client(self, client_id: str, message: dict):
        """向指定客户端发送消息"""
        websocket = self.get_websocket(client_id)
        if websocket:
            await websocket.send_json(message)


# 全局实例
ws_connection_manager = WebSocketConnectionManager()
