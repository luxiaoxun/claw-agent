# web/routers/workspace_router.py
import os
from fastapi import APIRouter
from typing import Optional, List
from pydantic import BaseModel
from soma.config.settings import WORKSPACE_DIR
from soma.config.logging_config import get_logger
from soma.common.response import success_response, fail_response

logger = get_logger(__name__)
router = APIRouter(prefix="/workspace", tags=["workspace"])


class FileNode(BaseModel):
    """文件树节点模型"""
    name: str
    path: str
    is_directory: bool
    children: Optional[List["FileNode"]] = None


class WorkspaceItem(BaseModel):
    """工作空间条目模型"""
    name: str
    path: str
    is_directory: bool
    size: int = 0
    modified_time: Optional[float] = None


FileNode.model_rebuild()


def is_hidden(path: str) -> bool:
    """检查路径是否为隐藏目录（排除.soma）"""
    basename = os.path.basename(path)
    # 排除所有.开头的目录，包括.soma
    return basename.startswith('.')


def build_file_tree(dir_path: str, max_depth: int = 3, current_depth: int = 0) -> List[FileNode]:
    """递归构建文件树，排除隐藏目录"""
    if current_depth >= max_depth:
        return []

    tree = []
    try:
        entries = sorted(os.scandir(dir_path), key=lambda x: (not x.is_dir(), x.name.lower()))
        for entry in entries:
            # 跳过隐藏目录
            if entry.is_dir() and is_hidden(entry.path):
                continue

            children = None
            if entry.is_dir():
                children = build_file_tree(entry.path, max_depth, current_depth + 1)

            tree.append(FileNode(
                name=entry.name,
                path=entry.path,
                is_directory=entry.is_dir(),
                children=children if entry.is_dir() else None
            ))
    except PermissionError:
        logger.warning(f"权限不足，无法访问目录: {dir_path}")
    except Exception as e:
        logger.error(f"读取目录失败 {dir_path}: {str(e)}")

    return tree


@router.get("/tree")
async def get_workspace_tree():
    """获取工作空间目录树（排除隐藏目录）"""
    try:
        logger.info(f"获取工作空间目录树: {WORKSPACE_DIR}")

        if not os.path.exists(WORKSPACE_DIR):
            return fail_response(message=f"工作空间目录不存在: {WORKSPACE_DIR}")

        tree = build_file_tree(WORKSPACE_DIR)

        return success_response(
            data={
                "workspace_dir": WORKSPACE_DIR,
                "tree": tree
            },
            message="获取目录树成功"
        )

    except Exception as e:
        logger.error(f"获取目录树失败: {str(e)}")
        return fail_response(message=f"获取目录树失败: {str(e)}")


@router.get("/list")
async def list_workspace(path: Optional[str] = None):
    """列出指定路径下的文件和目录（排除隐藏目录）"""
    try:
        target_path = path if path and os.path.exists(path) else WORKSPACE_DIR

        logger.info(f"列出工作空间目录: {target_path}")

        if not os.path.exists(target_path):
            return fail_response(message=f"路径不存在: {target_path}")

        if not os.path.isdir(target_path):
            return fail_response(message=f"路径不是目录: {target_path}")

        items = []
        entries = sorted(os.scandir(target_path), key=lambda x: (not x.is_dir(), x.name.lower()))

        for entry in entries:
            # 跳过隐藏目录
            if entry.is_dir() and is_hidden(entry.path):
                continue

            stat = entry.stat()
            items.append(WorkspaceItem(
                name=entry.name,
                path=entry.path,
                is_directory=entry.is_dir(),
                size=stat.st_size if not entry.is_dir() else 0,
                modified_time=stat.st_mtime
            ))

        return success_response(
            data={
                "path": target_path,
                "items": [item.model_dump() for item in items]
            },
            message="获取目录内容成功"
        )

    except Exception as e:
        logger.error(f"列出目录失败: {str(e)}")
        return fail_response(message=f"列出目录失败: {str(e)}")


@router.get("/read")
async def read_file(path: str):
    """读取文件内容"""
    try:
        if not path:
            return fail_response(message="文件路径不能为空")

        # 安全检查：确保路径在WORKSPACE_DIR内
        abs_workspace = os.path.abspath(WORKSPACE_DIR)
        abs_path = os.path.abspath(path)

        if not abs_path.startswith(abs_workspace):
            return fail_response(message="路径不在工作空间内")

        if not os.path.exists(abs_path):
            return fail_response(message="文件不存在")

        if os.path.isdir(abs_path):
            return fail_response(message="路径是目录而非文件")

        # 读取文件内容（限制大小为1MB）
        file_size = os.path.getsize(abs_path)
        if file_size > 1024 * 1024:
            return fail_response(message="文件过大，最大支持1MB")

        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return success_response(
            data={
                "path": abs_path,
                "name": os.path.basename(abs_path),
                "size": file_size,
                "content": content
            },
            message="读取文件成功"
        )

    except UnicodeDecodeError:
        return fail_response(message="文件编码不支持，请使用UTF-8编码的文件")
    except Exception as e:
        logger.error(f"读取文件失败 {path}: {str(e)}")
        return fail_response(message=f"读取文件失败: {str(e)}")
