from typing import Optional, Type, Union, Dict, Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict
import os
from pathlib import Path
from config.logging_config import get_logger

logger = get_logger(__name__)


class FileReadInput(BaseModel):
    """文件读取工具的输入参数"""
    path: str = Field(description="文件路径，相对于skills目录")
    skill_name: Optional[str] = Field(default=None, description="skill名称，用于定位文件")


class FileReadTool(BaseTool):
    """
    文件读取工具
    Agent通过此工具按需加载skill的详细内容

    支持多种输入格式：
    1. {"path": "data-search/SKILL.md", "skill_name": "data-search"}
    2. {"path": "SKILL.md", "skill_name": "data-search"}
    3. {"path": "data-search/SKILL.md"}
    """

    name: str = "file_read"
    description: str = "读取skill的详细内容文件，包括references/、scripts/等目录下的文件。输入文件路径，输出文件内容。"
    args_schema: Type[BaseModel] = FileReadInput

    # 声明为类属性
    skills_dir: Path = Field(default=Path("skills"), description="skills目录路径")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, skills_dir: str = "skills", **kwargs):
        # 使用 super().__init__ 并传入参数
        super().__init__(skills_dir=Path(skills_dir), **kwargs)

    def _normalize_path(self, path: str, skill_name: Optional[str] = None) -> Path:
        """
        规范化文件路径，兼容多种输入格式

        支持的格式：
        - path包含skill_name: "data-search/SKILL.md"
        - path不包含skill_name，但提供了skill_name参数
        - path是绝对路径或已经包含完整路径
        """
        # 将路径转换为Path对象
        path_obj = Path(path)

        # 情况1：提供了skill_name参数
        if skill_name:
            # 检查path是否已经包含skill_name
            if path_obj.parts and path_obj.parts[0] == skill_name:
                # path已经包含skill_name，直接使用
                return self.skills_dir / path
            else:
                # path不包含skill_name，构建完整路径
                return self.skills_dir / skill_name / path

        # 情况2：没有skill_name参数，尝试从path中提取
        # 检查path是否以skill目录开头
        if len(path_obj.parts) > 1:
            # 检查第一级目录是否是有效的skill目录
            potential_skill_dir = self.skills_dir / path_obj.parts[0]
            if potential_skill_dir.exists() and potential_skill_dir.is_dir():
                # 第一级目录是skill目录，直接使用
                return self.skills_dir / path

        # 情况3：path可能只是文件名，尝试在skills目录下搜索
        # 注意：这种情况需要谨慎，因为可能有多个同名文件
        if path_obj.name.endswith('.md'):
            # 尝试在所有skill目录下查找该文件
            for skill_dir in self.skills_dir.iterdir():
                if skill_dir.is_dir():
                    candidate = skill_dir / path
                    if candidate.exists():
                        return candidate

        # 默认情况：直接拼接skills_dir
        return self.skills_dir / path

    def _find_skill_file(self, skill_name: str, filename: str = "SKILL.md") -> Optional[Path]:
        """
        查找skill文件

        Args:
            skill_name: skill名称
            filename: 要查找的文件名，默认为SKILL.md

        Returns:
            文件路径，如果不存在则返回None
        """
        skill_dir = self.skills_dir / skill_name

        if not skill_dir.exists() or not skill_dir.is_dir():
            return None

        # 查找指定文件
        target_file = skill_dir / filename
        if target_file.exists() and target_file.is_file():
            return target_file

        return None

    def _run(self, path: str, skill_name: Optional[str] = None) -> str:
        """
        同步读取文件内容
        """
        try:
            # 特殊处理：如果skill_name存在且path是"SKILL.md"，直接查找skill文件
            if skill_name and path == "SKILL.md":
                skill_file = self._find_skill_file(skill_name, "SKILL.md")
                if skill_file:
                    file_path = skill_file
                else:
                    return f"错误：未找到skill '{skill_name}' 的 SKILL.md 文件"
            else:
                # 规范化文件路径
                file_path = self._normalize_path(path, skill_name)

            # 安全检查：防止路径遍历攻击
            try:
                resolved_path = file_path.resolve()
                skills_dir_resolved = self.skills_dir.resolve()

                # 检查是否在skills目录内
                if not str(resolved_path).startswith(str(skills_dir_resolved)):
                    return f"错误：禁止访问 {path} - 路径不在skills目录内"

                # 额外检查：确保路径不会向上遍历
                if '..' in path or path.startswith('/') or path.startswith('\\'):
                    return f"错误：禁止访问 {path} - 不允许使用路径遍历"

            except Exception as e:
                return f"错误：路径解析失败 - {str(e)}"

            # 检查文件是否存在
            if not resolved_path.exists():
                # 尝试在skill目录下查找
                if skill_name:
                    # 尝试查找SKILL.md
                    skill_file = self._find_skill_file(skill_name, "SKILL.md")
                    if skill_file:
                        with open(skill_file, 'r', encoding='utf-8') as f:
                            return f.read()

                # 尝试查找其他可能的文件
                possible_paths = [
                    self.skills_dir / skill_name / path if skill_name else None,
                    self.skills_dir / skill_name / "SKILL.md" if skill_name else None,
                    self.skills_dir / path,
                ]

                for possible_path in possible_paths:
                    if possible_path and possible_path.exists() and possible_path.is_file():
                        with open(possible_path, 'r', encoding='utf-8') as f:
                            logger.info(f"找到文件: {possible_path}")
                            return f.read()

                return f"错误：文件不存在 {path} (尝试路径: {file_path})"

            # 检查是否是文件
            if not resolved_path.is_file():
                # 如果是目录，尝试读取目录下的SKILL.md
                if resolved_path.is_dir():
                    skill_md = resolved_path / "SKILL.md"
                    if skill_md.exists():
                        with open(skill_md, 'r', encoding='utf-8') as f:
                            return f.read()
                return f"错误：{path} 不是文件"

            # 读取文件
            with open(resolved_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.debug(f"成功读取文件: {resolved_path}, 大小: {len(content)} 字符")
                return content

        except UnicodeDecodeError as e:
            return f"错误：文件编码错误 - {str(e)}"
        except PermissionError as e:
            return f"错误：权限不足 - {str(e)}"
        except Exception as e:
            return f"读取文件失败: {str(e)}"

    async def _arun(self, path: str, skill_name: Optional[str] = None) -> str:
        """异步读取文件内容"""
        return self._run(path, skill_name)
