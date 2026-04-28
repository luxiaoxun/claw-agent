# core/skill/skill_manager.py
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


class SkillManager:
    """
    Skill管理
    扫描skills目录，加载每个skill的元数据
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SkillManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, skills_dir: str = None):
        # 确保只初始化一次
        if not self._initialized and skills_dir is not None:
            self.skills_dir = Path(skills_dir)
            self.skills: Dict[str, SkillMetadata] = {}
            self._initialized = True
            logger.info(f"SkillManager单例初始化，skills目录: {self.skills_dir}")
        elif not self._initialized:
            raise ValueError("SkillManager初始化时需要提供skills_dir参数")

    @classmethod
    def get_instance(cls) -> "SkillManager":
        """获取单例实例"""
        if cls._instance is None:
            raise RuntimeError("SkillManager尚未初始化，请在lifespan中调用initialize方法")
        return cls._instance

    @classmethod
    def initialize(cls, skills_dir: str) -> "SkillManager":
        """初始化单例实例"""
        if cls._instance is None:
            cls._instance = cls(skills_dir)
        elif not cls._initialized:
            cls._instance.__init__(skills_dir)
        return cls._instance

    def load_all_skills(self) -> Dict[str, SkillMetadata]:
        """加载所有skill的元数据"""
        if not self.skills_dir.exists():
            logger.warning(f"Skills目录不存在: {self.skills_dir}")
            return {}

        loaded_count = 0
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                metadata = self._load_skill_metadata(skill_dir)
                if metadata:
                    self.skills[metadata.name] = metadata
                    loaded_count += 1

        logger.info(f"加载了 {loaded_count} 个技能，总计 {len(self.skills)} 个技能")
        return self.skills

    def _load_skill_metadata(self, skill_dir: Path) -> Optional[SkillMetadata]:
        """加载单个skill的元数据"""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            logger.debug(f"Skill目录 {skill_dir.name} 中没有SKILL.md文件")
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

    def reload_skills(self) -> Dict[str, SkillMetadata]:
        """重新加载所有skills"""
        self.skills.clear()
        return self.load_all_skills()

    def close(self):
        """清理资源"""
        logger.info("SkillManager 清理资源")
        self.skills.clear()
