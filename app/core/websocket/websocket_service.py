# core/websocket/websocket_service.py
from fastapi import WebSocket, WebSocketDisconnect
from config.logging_config import get_logger
from core.websocket.websocket_manager import WebSocketConnectionManager
from core.websocket.ws_message_handler import TextMessageHandler
from core.websocket.ws_file_handler import FileMessageHandler

logger = get_logger(__name__)


class WebSocketService:
    """WebSocket服务 - 统一处理WebSocket连接和消息分发"""

    def __init__(self):
        self.connection_manager = WebSocketConnectionManager()
        self.text_handler = TextMessageHandler(self.connection_manager)
        self.file_handler = FileMessageHandler(self.connection_manager, max_file_size_mb=100)

    async def handle_connection(self, websocket: WebSocket):
        """
        处理WebSocket连接

        Args:
            websocket: WebSocket连接对象
        """
        client_id = None
        try:
            # 1. 接受连接
            client_id = await self.connection_manager.connect(websocket)

            # 2. 发送连接成功消息
            await websocket.send_json({
                "type": "connection",
                "status": "connected",
                "client_id": client_id,
                "message": "WebSocket 连接成功（支持文件传输）"
            })

            logger.info(f"WebSocket 客户端 {client_id} 连接已建立")

            # 3. 循环接收消息
            while True:
                try:
                    message = await websocket.receive()
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"接收消息失败: {str(e)}")
                    break

                # 4. 消息分发
                if message["type"] == "websocket.receive":
                    if "text" in message:
                        # 处理文本消息
                        await self._handle_text_message(websocket, client_id, message["text"])
                    elif "bytes" in message:
                        # 处理二进制消息（文件）
                        await self.file_handler.handle(websocket, client_id, message["bytes"])

        except WebSocketDisconnect:
            logger.info(f"WebSocket 客户端断开连接: {client_id}")
        except Exception as e:
            logger.error(f"WebSocket 连接异常: {str(e)}", exc_info=True)
        finally:
            # 5. 清理资源
            if client_id:
                await self.connection_manager.disconnect_and_cleanup(client_id)

    async def _handle_text_message(self, websocket: WebSocket, client_id: str, text_data: str):
        """
        处理文本消息（内部方法）

        Args:
            websocket: WebSocket连接
            client_id: 客户端ID
            text_data: 文本数据
        """
        import json

        try:
            message_data = json.loads(text_data)
            await self.text_handler.handle(websocket, client_id, message_data)
        except json.JSONDecodeError:
            await websocket.send_json({
                "type": "error",
                "error": "Invalid JSON data"
            })
        except Exception as e:
            logger.error(f"处理文本消息时出错: {str(e)}", exc_info=True)
            await websocket.send_json({
                "type": "error",
                "error": f"Process message error: {str(e)}"
            })

    async def close(self):
        await self.connection_manager.close_all_connections()


# 全局单例
websocket_service = WebSocketService()
