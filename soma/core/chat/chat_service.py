# core/chat/chat_service.py
import json
import uuid
from typing import Dict, Any, Optional, Tuple
from soma.core.chat.session_manager import SessionManager
from soma.config.logging_config import get_logger

logger = get_logger(__name__)


class ChatService:
    """聊天服务 - 处理 HTTP 聊天请求"""

    def __init__(self):
        """初始化聊天服务"""
        self.session_managers: Dict[str, SessionManager] = {}

    async def process_chat_request(self, message: str, session_id: Optional[str] = None,
                                   user_id: Optional[str] = None) -> Tuple[
        Optional[Dict[str, Any]], Optional[str]]:
        """
        处理聊天请求

        Args:
            message: 用户消息内容
            session_id: 会话ID
            user_id: 用户ID

        Returns:
            Tuple[响应数据, 错误信息]
            - 成功时: (响应数据, None)
            - 失败时: (None, 错误信息)
        """
        session_manager = None

        try:
            # 1. 验证消息
            if not message or not isinstance(message, str):
                return None, "消息内容不能为空"

            # 2. 确定会话ID
            if session_id is None:
                session_id = str(uuid.uuid4())

            # 3. 创建并初始化会话管理器
            session_manager = SessionManager(session_id=session_id, user_id=user_id)
            await session_manager.initialize()

            # 4. 处理消息
            logger.info(f"处理聊天请求: {message[:100]}..., session_id: {session_id}")

            try:
                response = await session_manager.process_message(message)
            except Exception as e:
                logger.error(f"处理消息时异步执行错误: {str(e)}")
                return None, f"处理消息失败: {str(e)}"

            # 5. 解析响应
            try:
                parsed_response = json.loads(response)
            except json.JSONDecodeError:
                parsed_response = response

            # 6. 构建响应数据
            response_data = {
                "response": parsed_response,
                "session_id": session_id
            }

            logger.info(f"聊天请求处理完成，session_id: {session_id}")
            return response_data, None

        except Exception as e:
            logger.error(f"处理聊天请求时出错: {str(e)}", exc_info=True)
            return None, f"处理请求失败: {str(e)}"

        finally:
            # 7. 清理资源
            if session_manager:
                await session_manager.close()


# 全局单例
chat_service = ChatService()
