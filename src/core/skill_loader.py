import os
import yaml
import frontmatter
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass
from config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SkillMetadata:
    """Skill元数据"""
    name: str
    description: str
    path: str
    has_references: bool = False
    has_scripts: bool = False
    has_assets: bool = False


class SkillLoader:
    """
    Skill加载器
    扫描skills目录，加载每个skill的元数据
    """

    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, SkillMetadata] = {}

    def load_all_skills(self) -> Dict[str, SkillMetadata]:
        """加载所有skill的元数据"""
        if not self.skills_dir.exists():
            logger.warning(f"Skills目录不存在: {self.skills_dir}")
            return {}

        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                metadata = self._load_skill_metadata(skill_dir)
                if metadata:
                    self.skills[metadata.name] = metadata

        logger.info(f"加载了 {len(self.skills)} 个技能")
        return self.skills

    def _load_skill_metadata(self, skill_dir: Path) -> Optional[SkillMetadata]:
        """加载单个skill的元数据"""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None

        try:
            with open(skill_md, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)

            # 提取frontmatter中的name和description
            name = post.metadata.get('name')
            description = post.metadata.get('description')

            if not name or not description:
                logger.warning(f"Skill {skill_dir.name} 缺少name或description")
                return None

            # 检查是否有引用文件
            has_references = (skill_dir / "references").exists()
            has_scripts = (skill_dir / "scripts").exists()
            has_assets = (skill_dir / "assets").exists()

            return SkillMetadata(
                name=name,
                description=description,
                path=str(skill_dir),
                has_references=has_references,
                has_scripts=has_scripts,
                has_assets=has_assets
            )

        except Exception as e:
            logger.error(f"加载skill失败 {skill_dir.name}: {e}")
            return None

    def get_skill_metadata(self, skill_name: str) -> Optional[SkillMetadata]:
        """获取指定skill的元数据"""
        return self.skills.get(skill_name)

    def get_all_skill_descriptions(self) -> List[Dict[str, str]]:
        """获取所有skill的描述（用于Agent判断）"""
        return [
            {"name": skill.name, "description": skill.description}
            for skill in self.skills.values()
        ]
