# core/websocket/websocket_manager.py
from typing import Dict, Optional
from fastapi import WebSocket
from core.chat.session_manager import SessionManager
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

        # 创建新的会话管理器
        session_manager = SessionManager()

        # 存储连接信息
        self.active_connections[client_id] = {
            "websocket": websocket,
            "session_manager": session_manager,
            "session_id": None,
            "user_id": None,
            "initialized": False
        }

        logger.info(f"WebSocket 客户端 {client_id} 已连接")
        return client_id

    async def get_or_create_session_manager(self, client_id: str, session_id: str = None,
                                            user_id: str = None) -> SessionManager:
        """
        获取或创建会话管理器

        当 session_id 为 None 时，创建新的会话管理器
        当 session_id 有值时，查找已存在的会话管理器，如果不存在则创建新的

        Args:
            client_id: 客户端ID
            session_id: 会话ID（可以为 None）
            user_id: 用户ID（可选）

        Returns:
            SessionManager: 会话管理器实例
        """
        conn = self.active_connections.get(client_id)
        if not conn:
            raise ValueError(f"客户端 {client_id} 不存在")

        session_manager = conn["session_manager"]

        # 情况1: session_id 为 None，创建新的会话管理器
        if session_id is None:
            # 检查当前是否已经有初始化的会话管理器
            if conn.get("initialized"):
                # 如果已经初始化，关闭旧的会话管理器
                try:
                    await session_manager.close()
                    logger.info(f"关闭旧的会话管理器，session_id: {conn['session_id']}")
                except Exception as e:
                    logger.error(f"关闭旧会话管理器失败: {str(e)}")

            # 创建新的会话管理器
            new_session_id = str(uuid.uuid4())
            new_session_manager = SessionManager()
            try:
                await new_session_manager.initialize(
                    session_id=new_session_id,
                    user_id=user_id
                )

                # 更新连接信息
                conn["session_manager"] = new_session_manager
                conn["session_id"] = new_session_manager.session_id
                conn["user_id"] = user_id
                conn["initialized"] = True

                logger.info(f"为客户端 {client_id} 创建新会话，session_id: {new_session_manager.session_id}")
                return new_session_manager

            except Exception as e:
                logger.error(f"创建新会话管理器失败: {str(e)}")
                raise

        # 情况2: session_id 有值，查找已存在的会话管理器
        else:
            # 检查当前会话管理器是否已经初始化且 session_id 匹配
            if conn.get("initialized") and conn["session_id"] == session_id:
                logger.debug(f"找到已存在的会话管理器，session_id: {session_id}")
                return session_manager

            # 未初始化或 session_id 不匹配，创建新的会话管理器
            # 先关闭旧的（如果存在）
            if conn.get("initialized"):
                try:
                    await session_manager.close()
                    logger.info(f"关闭旧的会话管理器，session_id: {conn['session_id']}")
                except Exception as e:
                    logger.error(f"关闭旧会话管理器失败: {str(e)}")

            # 创建新的会话管理器
            new_session_manager = SessionManager()
            try:
                await new_session_manager.initialize(
                    session_id=session_id,
                    user_id=user_id
                )

                # 更新连接信息
                conn["session_manager"] = new_session_manager
                conn["session_id"] = new_session_manager.session_id
                conn["user_id"] = user_id
                conn["initialized"] = True

                logger.info(f"为客户端 {client_id} 创建指定会话，session_id: {new_session_manager.session_id}")
                return new_session_manager

            except Exception as e:
                logger.error(f"创建指定会话管理器失败: {str(e)}")
                raise

    def disconnect(self, client_id: str):
        """断开连接（同步版本，仅移除连接，不清理资源）"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket 客户端 {client_id} 已断开")

    async def disconnect_and_cleanup(self, client_id: str):
        """断开连接并清理资源（异步版本）"""
        if client_id in self.active_connections:
            conn = self.active_connections[client_id]
            manager = conn.get("session_manager")
            if manager:
                try:
                    await manager.close()
                    logger.info(f"客户端 {client_id} 的会话管理器已关闭")
                except Exception as e:
                    logger.error(f"关闭客户端 {client_id} 的会话管理器时出错: {str(e)}")

            # 关闭 WebSocket 连接（如果仍然打开）
            websocket = conn.get("websocket")
            if websocket:
                try:
                    await websocket.close()
                except Exception as e:
                    logger.debug(f"关闭 WebSocket 连接时出错: {str(e)}")

            del self.active_connections[client_id]
            logger.info(f"WebSocket 客户端 {client_id} 已断开并清理资源")

    def get_websocket(self, client_id: str) -> Optional[WebSocket]:
        """获取客户端的 WebSocket 连接"""
        conn = self.active_connections.get(client_id)
        return conn.get("websocket") if conn else None

    def get_session_id(self, client_id: str) -> Optional[str]:
        """获取客户端的当前会话ID"""
        conn = self.active_connections.get(client_id)
        return conn.get("session_id") if conn else None

    def get_user_id(self, client_id: str) -> Optional[str]:
        """获取客户端的用户ID"""
        conn = self.active_connections.get(client_id)
        return conn.get("user_id") if conn else None

    def is_manager_initialized(self, client_id: str) -> bool:
        """检查客户端的会话管理器是否已初始化"""
        conn = self.active_connections.get(client_id)
        return conn.get("initialized", False) if conn else False

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

    async def close_all_connections(self):
        """关闭所有连接（用于系统关闭时）"""
        logger.info(f"正在关闭所有 WebSocket 连接")
        for client_id in list(self.active_connections.keys()):
            await self.disconnect_and_cleanup(client_id)
        logger.info("所有 WebSocket 连接已关闭")


# 全局实例
ws_connection_manager = WebSocketConnectionManager()
