# web/routers/skill_router.py
from dataclasses import dataclass, field
from typing import List, Dict, Any
from fastapi import APIRouter, Request
from common.response import success_response, fail_response
from config.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/skill", tags=["skill"])


@dataclass
class SkillMetadataResponse:
    """Skill元数据响应模型"""
    name: str
    description: str
    path: str
    has_references: bool = False
    has_scripts: bool = False
    has_assets: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "path": self.path,
            "has_references": self.has_references,
            "has_scripts": self.has_scripts,
            "has_assets": self.has_assets
        }


@dataclass
class SkillsResponse:
    """技能列表响应模型"""
    skills: List[SkillMetadataResponse] = field(default_factory=list)
    total: int = 0

    def __post_init__(self):
        self.total = len(self.skills)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "skills": [skill.to_dict() for skill in self.skills],
            "total": self.total
        }

    @classmethod
    def from_skill_metadata(cls, skills: Dict[str, Any]) -> "SkillsResponse":
        """从SkillManager的skills字典创建响应"""
        skill_responses = []
        for skill_name, skill_metadata in skills.items():
            skill_responses.append(SkillMetadataResponse(
                name=skill_metadata.name,
                description=skill_metadata.description,
                path=skill_metadata.path,
                has_references=skill_metadata.has_references,
                has_scripts=skill_metadata.has_scripts,
                has_assets=skill_metadata.has_assets
            ))
        return cls(skills=skill_responses)


@router.get("/list")
async def list_skills(request: Request):
    """列出所有可用的Skill"""
    try:
        # 从app state中获取skill_manager
        skill_manager = request.app.state.skill_manager

        if not skill_manager or not skill_manager.skills:
            logger.warning("没有找到任何Skill")
            return success_response(
                data={"skills": [], "total": 0},
                message="没有找到任何Skill"
            )

        skills_info = skill_manager.skills
        logger.info(f"获取到 {len(skills_info)} 个Skill")

        response = SkillsResponse.from_skill_metadata(skills_info)

        return success_response(
            data=response.to_dict(),
            message="获取Skill列表成功"
        )

    except Exception as e:
        logger.error(f"获取Skill列表失败: {str(e)}")
        return fail_response(
            data={"skills": [], "total": 0},
            message=f"获取Skill列表失败: {str(e)}"
        )


@router.get("/{skill_name}")
async def get_skill(skill_name: str, request: Request):
    """获取单个Skill信息"""
    try:
        skill_manager = request.app.state.skill_manager

        if not skill_manager:
            logger.warning("SkillManager未初始化")
            return fail_response(message="SkillManager未初始化")

        skill_metadata = skill_manager.get_skill_metadata(skill_name)

        if not skill_metadata:
            logger.warning(f"Skill {skill_name} 不存在")
            return fail_response(message=f"Skill {skill_name} 不存在")

        skill_response = SkillMetadataResponse(
            name=skill_metadata.name,
            description=skill_metadata.description,
            path=skill_metadata.path,
            has_references=skill_metadata.has_references,
            has_scripts=skill_metadata.has_scripts,
            has_assets=skill_metadata.has_assets
        )

        logger.info(f"成功获取Skill信息: {skill_name}")
        return success_response(
            data=skill_response.to_dict(),
            message="获取Skill信息成功"
        )

    except Exception as e:
        logger.error(f"获取Skill信息失败: {str(e)}")
        return fail_response(message=f"获取Skill信息失败: {str(e)}")
