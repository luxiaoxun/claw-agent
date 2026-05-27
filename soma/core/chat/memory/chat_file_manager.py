# core/chat/memory/chat_file_manager.py
from typing import List, Dict, Any, Optional
from datetime import datetime
from soma.config.logging_config import get_logger
from langchain_core.messages import HumanMessage

logger = get_logger(__name__)


class ChatFileManager:
    """
    聊天文件管理器
    负责管理会话中的文件上下文，包括文件的添加、删除、查询和持久化
    """

    def __init__(self, session_id: str = None, user_id: str = None):
        """
        初始化文件管理器

        Args:
            session_id: 会话ID
            user_id: 用户ID
        """
        self.session_id = session_id
        self.user_id = user_id
        self.file_contexts: List[Dict[str, Any]] = []
        self.max_file_contexts: int = 1  # 最多保留的文件数量
        self._initialized = False

    async def initialize(self, session_id: str = None, user_id: str = None):
        """
        初始化文件管理器

        Args:
            session_id: 会话ID
            user_id: 用户ID
        """
        if session_id:
            self.session_id = session_id
        if user_id:
            self.user_id = user_id

        # 从数据库加载历史文件上下文
        await self._load_from_database()

        self._initialized = True
        logger.info(f"ChatFileManager 初始化完成, session_id: {self.session_id}, 文件数: {len(self.file_contexts)}")
        return self

    async def add_file(self, file_info: Dict[str, Any]) -> bool:
        """
        添加文件到上下文

        Args:
            file_info: 文件信息字典，包含以下字段：
                - original_name: 原始文件名
                - saved_name: 保存的文件名
                - path: 文件路径
                - relative_path: 相对路径
                - url: 访问URL
                - size: 文件大小（字节）
                - timestamp: 上传时间
                - user_id: 用户ID（可选）
                - session_id: 会话ID（可选）

        Returns:
            bool: 是否添加成功
        """
        if not self._initialized:
            logger.warning(f"ChatFileManager 未初始化，无法添加文件")
            return False

        try:
            # 避免重复添加相同文件
            saved_name = file_info.get("saved_name")
            if saved_name and self._is_file_exists(saved_name):
                logger.warning(f"文件已存在于上下文中: {file_info.get('original_name')}")
                return False

            # 添加时间戳（如果没有）
            if "timestamp" not in file_info:
                file_info["timestamp"] = datetime.now().isoformat()

            # 添加会话和用户信息
            if self.session_id and "session_id" not in file_info:
                file_info["session_id"] = self.session_id
            if self.user_id and "user_id" not in file_info:
                file_info["user_id"] = self.user_id

            # 添加到列表
            self.file_contexts.append(file_info)

            # 限制数量
            if len(self.file_contexts) > self.max_file_contexts:
                removed = self.file_contexts.pop(0)
                logger.info(f"移除旧文件上下文: {removed.get('original_name')}")

            # 保存到数据库
            await self._save_to_database(file_info)

            logger.info(f"文件已添加到上下文: {file_info.get('original_name')}, 当前文件数: {len(self.file_contexts)}")
            return True

        except Exception as e:
            logger.error(f"添加文件上下文失败: {str(e)}", exc_info=True)
            return False

    async def remove_file(self, file_id: str, by: str = "saved_name") -> bool:
        """
        从上下文中移除文件

        Args:
            file_id: 文件标识（文件名或保存名）
            by: 标识类型，可选 "saved_name", "original_name", "path"

        Returns:
            bool: 是否移除成功
        """
        if not self._initialized:
            logger.warning(f"ChatFileManager 未初始化，无法移除文件")
            return False

        for i, file_info in enumerate(self.file_contexts):
            if by == "saved_name" and file_info.get("saved_name") == file_id:
                removed = self.file_contexts.pop(i)
                await self._remove_from_database(removed)
                logger.info(f"文件已从上下文中移除: {removed.get('original_name')}")
                return True
            elif by == "original_name" and file_info.get("original_name") == file_id:
                removed = self.file_contexts.pop(i)
                await self._remove_from_database(removed)
                logger.info(f"文件已从上下文中移除: {removed.get('original_name')}")
                return True
            elif by == "path" and file_info.get("path") == file_id:
                removed = self.file_contexts.pop(i)
                await self._remove_from_database(removed)
                logger.info(f"文件已从上下文中移除: {removed.get('original_name')}")
                return True

        logger.warning(f"未找到要移除的文件: {file_id}")
        return False

    async def get_file(self, file_id: str, by: str = "saved_name") -> Optional[Dict[str, Any]]:
        """
        获取文件信息

        Args:
            file_id: 文件标识
            by: 标识类型，可选 "saved_name", "original_name", "path"

        Returns:
            文件信息字典，如果未找到返回 None
        """
        for file_info in self.file_contexts:
            if by == "saved_name" and file_info.get("saved_name") == file_id:
                return file_info.copy()
            elif by == "original_name" and file_info.get("original_name") == file_id:
                return file_info.copy()
            elif by == "path" and file_info.get("path") == file_id:
                return file_info.copy()
        return None

    async def get_all_files(self) -> List[Dict[str, Any]]:
        """
        获取所有文件信息

        Returns:
            文件信息列表（副本）
        """
        return [f.copy() for f in self.file_contexts]

    async def get_files_summary(self) -> str:
        """
        获取文件摘要信息

        Returns:
            文件摘要文本
        """
        if not self.file_contexts:
            return "当前会话中没有上传任何文件。"

        summary = f"当前会话共有 {len(self.file_contexts)} 个文件:\n"
        for idx, file_info in enumerate(self.file_contexts, 1):
            summary += f"{idx}. {file_info.get('original_name')} ({file_info.get('size_mb', 0)} MB)\n"
            if file_info.get('url'):
                summary += f"   访问路径: {file_info.get('url')}\n"

        return summary

    async def get_file_context_message(self) -> Optional[HumanMessage]:
        """
        获取文件上下文的系统消息
        将当前会话中已上传的文件信息转换为 AI 可以理解的消息格式

        Returns:
            HumanMessage 或 None
        """
        if not self.file_contexts:
            return None

        # 构建文件上下文描述
        file_descriptions = []
        for idx, file_info in enumerate(self.file_contexts, 1):
            file_desc = f"{idx}. 文件名: {file_info.get('original_name')}\n"
            file_desc += f"   大小: {file_info.get('size', 0)} Bytes\n"
            if file_info.get('url'):
                file_desc += f"   访问路径: {file_info.get('url')}\n"
            file_desc += f"   上传时间: {file_info.get('timestamp', '未知')}"
            file_descriptions.append(file_desc)

        context_text = (
            f"用户已在本次会话中上传了以下文件，你可以根据这些文件的内容回答用户的问题：\n\n"
            f"{chr(10).join(file_descriptions)}\n\n"
            f"注意：如果需要读取文件内容，请使用相应的工具读取文件路径中的内容。"
        )

        return HumanMessage(content=context_text)

    async def count(self) -> int:
        """
        获取文件数量

        Returns:
            文件数量
        """
        return len(self.file_contexts)

    async def clear(self) -> int:
        """
        清空所有文件上下文

        Returns:
            清空的文件数量
        """
        count = len(self.file_contexts)
        self.file_contexts.clear()
        await self._clear_database()
        logger.info(f"已清空文件上下文，共移除 {count} 个文件")
        return count

    async def is_empty(self) -> bool:
        """
        检查是否为空

        Returns:
            是否为空
        """
        return len(self.file_contexts) == 0

    def _is_file_exists(self, saved_name: str) -> bool:
        """
        检查文件是否已存在

        Args:
            saved_name: 保存的文件名

        Returns:
            是否存在
        """
        return any(f.get("saved_name") == saved_name for f in self.file_contexts)

    async def _save_to_database(self, file_info: Dict[str, Any]):
        """
        保存文件信息到数据库

        Args:
            file_info: 文件信息
        """
        try:
            # TODO: 实现数据库保存逻辑
            # 例如：await self.file_service.save_file_record(file_info)
            logger.debug(f"文件信息已保存到数据库: {file_info.get('original_name')}")
        except Exception as e:
            logger.error(f"保存文件信息到数据库失败: {str(e)}")

    async def _load_from_database(self):
        """
        从数据库加载文件信息
        """
        try:
            # TODO: 实现数据库加载逻辑
            # 例如：self.file_contexts = await self.file_service.get_session_files(self.session_id)
            if self.session_id:
                logger.debug(f"从数据库加载会话文件: {self.session_id}")
        except Exception as e:
            logger.error(f"从数据库加载文件信息失败: {str(e)}")

    async def _remove_from_database(self, file_info: Dict[str, Any]):
        """
        从数据库移除文件信息

        Args:
            file_info: 文件信息
        """
        try:
            # TODO: 实现数据库删除逻辑
            # 例如：await self.file_service.delete_file_record(file_info.get("saved_name"))
            logger.debug(f"文件信息已从数据库移除: {file_info.get('original_name')}")
        except Exception as e:
            logger.error(f"从数据库移除文件信息失败: {str(e)}")

    async def _clear_database(self):
        """
        清空数据库中的文件信息
        """
        try:
            # TODO: 实现数据库清空逻辑
            # 例如：await self.file_service.clear_session_files(self.session_id)
            if self.session_id:
                logger.debug(f"清空会话文件记录: {self.session_id}")
        except Exception as e:
            logger.error(f"清空数据库文件信息失败: {str(e)}")

    async def close(self):
        """
        关闭文件管理器，清理资源
        """
        self._initialized = False
        self.file_contexts.clear()
        logger.debug(f"ChatFileManager 已关闭, session_id: {self.session_id}")
