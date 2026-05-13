# core/websocket/ws_file_handler.py
import struct
import json
from pathlib import Path
from fastapi import WebSocket
from config.logging_config import get_logger
from core.websocket.websocket_manager import WebSocketConnectionManager
from utils.file_handler import FileHandler as FileStorageHandler

logger = get_logger(__name__)


class FileMessageHandler:
    """文件消息处理器 - 处理二进制文件上传"""

    def __init__(self, connection_manager: WebSocketConnectionManager,
                 max_file_size_mb: int = 100,
                 allowed_extensions: list = None):
        """
        初始化文件消息处理器

        Args:
            connection_manager: WebSocket连接管理器
            max_file_size_mb: 最大文件大小（MB）
            allowed_extensions: 允许的文件扩展名列表
        """
        self.connection_manager = connection_manager
        self.max_file_size_mb = max_file_size_mb
        self.allowed_extensions = allowed_extensions or [
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',  # 图片
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',  # 文档
            '.txt', '.md', '.json', '.xml', '.csv',  # 文本
            '.mp3', '.mp4', '.avi', '.mov', '.wav',  # 音视频
            '.zip', '.rar', '.7z', '.tar', '.gz'  # 压缩包
        ]
        self.file_storage = FileStorageHandler()

    async def handle(self, websocket: WebSocket, client_id: str, binary_data: bytes):
        """
        处理二进制消息（文件上传）

        协议格式：
        1. 前4字节：元数据长度（int，大端序）
        2. 元数据：JSON格式的字符串（包含文件名、文件类型等）
        3. 后面的数据：文件二进制内容

        Args:
            websocket: WebSocket连接
            client_id: 客户端ID
            binary_data: 二进制数据
        """
        try:
            # 1. 验证数据长度
            if len(binary_data) < 4:
                logger.error(f"二进制数据太短: {len(binary_data)} bytes")
                await self._send_error(websocket, "Invalid file data: data too short")
                return

            # 2. 解析元数据长度
            metadata_length = struct.unpack('>I', binary_data[:4])[0]

            # 3. 提取并解析元数据
            if len(binary_data) < 4 + metadata_length:
                logger.error(f"数据不完整: expected {4 + metadata_length} bytes, got {len(binary_data)}")
                await self._send_error(websocket, "Invalid file data: incomplete metadata")
                return

            metadata_json = binary_data[4:4 + metadata_length].decode('utf-8')
            metadata = json.loads(metadata_json)

            # 4. 提取文件数据
            file_data = binary_data[4 + metadata_length:]

            if len(file_data) == 0:
                logger.error("文件数据为空")
                await self._send_error(websocket, "File data is empty")
                return

            # 5. 确保会话管理器存在（如果没有则创建）
            session_info = self.connection_manager.get_session_info(client_id)
            new_session_created = False

            if not session_info or not session_info.get("initialized"):
                # 需要获取或创建会话管理器
                session_id = session_info.get("session_id") if session_info else None
                user_id = session_info.get("user_id") if session_info else None
                try:
                    session_manager = await self.connection_manager.get_or_create_session_manager(
                        client_id=client_id,
                        session_id=session_id,
                        user_id=user_id
                    )
                    session_info = {
                        "session_id": session_manager.session_id,
                        "user_id": user_id,
                        "initialized": True
                    }
                    new_session_created = True
                    logger.info(f"文件上传前创建会话管理器: {session_manager.session_id}")
                except Exception as e:
                    logger.error(f"创建会话管理器失败: {e}")
                    await self._send_error(websocket, "Failed to create session")
                    return

            # 如果创建了新会话，发送 session 消息告知前端
            if new_session_created:
                await websocket.send_json({
                    "type": "session",
                    "session_id": session_info.get("session_id")
                })

            # 6. 验证文件
            filename = metadata.get('filename', 'unknown')
            validation_result = await self._validate_file(filename, len(file_data))

            if not validation_result["valid"]:
                await self._send_error(websocket, validation_result["error"])
                return

            # 7. 保存文件
            file_info = await self.file_storage.save_file(
                file_data=file_data,
                filename=filename,
                user_id=session_info.get("user_id"),
                session_id=session_info.get("session_id")
            )

            # 8. 获取文件访问URL
            file_url = await self.file_storage.get_file_url(file_info["path"])
            file_info["url"] = file_url

            # 9. 发送成功响应
            await websocket.send_json({
                "type": "file_received",
                "file_info": {
                    "name": file_info["original_name"],
                    "saved_name": file_info["saved_name"],
                    "size": file_info["size"],
                    "url": file_info["url"],
                    "path": file_info["relative_path"],
                    "timestamp": file_info["timestamp"]
                }
            })

            logger.info(f"文件上传成功: {filename} ({file_info['size']}B) from client {client_id}")

            # 10. 可选：通知AI有文件上传
            await self._notify_ai_about_file(client_id, file_info)

        except json.JSONDecodeError as e:
            logger.error(f"解析元数据JSON失败: {str(e)}")
            await self._send_error(websocket, f"Invalid metadata JSON: {str(e)}")
        except struct.error as e:
            logger.error(f"解析二进制数据失败: {str(e)}")
            await self._send_error(websocket, f"Invalid binary data format: {str(e)}")
        except Exception as e:
            logger.error(f"处理二进制消息失败: {str(e)}", exc_info=True)
            await self._send_error(websocket, f"File upload failed: {str(e)}")

    async def _validate_file(self, filename: str, file_size: int) -> dict:
        """
        验证文件是否合法

        Args:
            filename: 文件名
            file_size: 文件大小（字节）

        Returns:
            验证结果字典
        """
        # 检查文件大小
        file_size_mb = file_size / (1024 * 1024)
        if file_size_mb > self.max_file_size_mb:
            return {
                "valid": False,
                "error": f"File too large: {file_size_mb:.2f}MB (max {self.max_file_size_mb}MB)"
            }

        # 检查文件扩展名
        file_ext = Path(filename).suffix.lower()
        if self.allowed_extensions and file_ext not in self.allowed_extensions:
            return {
                "valid": False,
                "error": f"File type not allowed: {file_ext}. Allowed: {', '.join(self.allowed_extensions)}"
            }

        return {"valid": True}

    async def _send_error(self, websocket: WebSocket, error_message: str):
        """发送错误消息"""
        await websocket.send_json({
            "type": "error",
            "error": error_message
        })

    async def _notify_ai_about_file(self, client_id: str, file_info: dict):
        """
        通知 AI 有文件上传，将文件信息添加到会话上下文中

        Args:
            client_id: 客户端ID
            file_info: 文件信息
        """
        try:
            # 获取连接信息和会话管理器
            conn = self.connection_manager.active_connections.get(client_id)
            if not conn:
                logger.warning(f"客户端 {client_id} 不存在，无法添加文件上下文")
                return

            session_manager = conn.get("session_manager")
            if not session_manager:
                logger.warning(f"客户端 {client_id} 没有会话管理器，无法添加文件上下文")
                return

            # 调用 SessionManager 的方法添加文件上下文
            success = await session_manager.add_file_context(file_info)
            if success:
                logger.info(
                    f"文件上下文已添加到会话: {file_info['original_name']}, session_id: {session_manager.session_id}")
            else:
                logger.warning(f"文件上下文添加失败: {file_info['original_name']}")

        except Exception as e:
            logger.error(f"通知AI文件上传失败: {str(e)}", exc_info=True)

    async def _send_file_notification(self, websocket: WebSocket, file_info: dict):
        """
        可选：发送文件上传成功的通知消息（展示在聊天界面）

        Args:
            websocket: WebSocket连接
            file_info: 文件信息
        """
        try:
            # 可以选择是否在聊天界面显示文件上传的系统消息
            if hasattr(self, 'show_file_upload_message') and self.show_file_upload_message:
                await websocket.send_json({
                    "type": "system",
                    "content": f"📎 文件已上传: {file_info['original_name']} ({file_info['size']} B)\n"
                               f"你可以继续提问，AI 将能够访问这个文件。",
                    "file_info": {
                        "name": file_info['original_name'],
                        "url": file_info['url'],
                        "size_mb": file_info['size_mb']
                    }
                })
        except Exception as e:
            logger.debug(f"发送文件通知失败: {str(e)}")
