# utils/file_handler.py
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from config.logging_config import get_logger
from config.settings import WORKSPACE_DIR

logger = get_logger(__name__)


class FileHandler:
    """文件处理器 - 处理文件上传和保存"""

    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(os.path.join(WORKSPACE_DIR, upload_dir))
        self.upload_dir.mkdir(exist_ok=True)

    async def save_file(self, file_data: bytes, filename: str, user_id: str = None, session_id: str = None) -> Dict[
        str, Any]:
        """
        保存文件

        Args:
            file_data: 文件二进制数据
            filename: 原始文件名
            user_id: 用户ID（可选）
            session_id: 会话ID（可选）

        Returns:
            文件信息字典
        """
        # 按日期创建子目录
        date_dir = self.upload_dir / datetime.now().strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        # 构建存储路径（可选：按用户和会话组织）
        if user_id and session_id:
            file_dir = date_dir / user_id / session_id
        elif user_id:
            file_dir = date_dir / user_id
        else:
            file_dir = date_dir / "anonymous"

        file_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名（保留原扩展名）
        original_ext = Path(filename).suffix
        unique_filename = f"{uuid.uuid4().hex}{original_ext}"
        file_path = file_dir / unique_filename

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(file_data)

        # 计算文件大小
        file_size = len(file_data)

        file_info = {
            "original_name": filename,
            "saved_name": unique_filename,
            "path": str(file_path),
            "relative_path": str(file_path.relative_to(self.upload_dir)),
            "size": file_size,
            # "size_mb": round(file_size / (1024 * 1024), 2),
            # "size_kb": round(file_size / 1024, 2),
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "session_id": session_id
        }

        logger.info(f"文件已保存: {file_info}")
        return file_info

    async def get_file_url(self, file_path: str) -> str:
        """获取文件访问URL"""
        try:
            relative_path = Path(file_path).relative_to(self.upload_dir)
            return f"uploads/{relative_path}"
        except Exception:
            return f"uploads/{Path(file_path).name}"
