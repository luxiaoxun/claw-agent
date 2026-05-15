# web/routers/skill_router.py
from dataclasses import dataclass, field
from typing import List, Dict, Any
import os
import zipfile
import shutil
from fastapi import APIRouter, Request, UploadFile, File
from common.response import success_response, fail_response
from config.logging_config import get_logger
from config.settings import SKILLS_DIR

logger = get_logger(__name__)
router = APIRouter(prefix="/skill", tags=["skill"])


@dataclass
class SkillMetadataResponse:
    """Skill元数据响应模型"""
    name: str
    description: str
    path: str
    content: str = ""  # SKILL.md 文件内容
    has_references: bool = False
    has_scripts: bool = False
    has_assets: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "path": self.path,
            "content": self.content,
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
    """获取单个Skill信息（含SKILL.md内容）"""
    try:
        skill_manager = request.app.state.skill_manager

        if not skill_manager:
            logger.warning("SkillManager未初始化")
            return fail_response(message="SkillManager未初始化")

        skill_metadata = skill_manager.get_skill_metadata(skill_name)

        if not skill_metadata:
            logger.warning(f"Skill {skill_name} 不存在")
            return fail_response(message=f"Skill {skill_name} 不存在")

        # 读取 SKILL.md 文件内容
        import os
        skill_md_path = os.path.join(skill_metadata.path, "SKILL.md")
        content = ""
        if os.path.exists(skill_md_path):
            try:
                with open(skill_md_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                logger.warning(f"读取SKILL.md失败: {skill_name}, {e}")

        skill_response = SkillMetadataResponse(
            name=skill_metadata.name,
            description=skill_metadata.description,
            path=skill_metadata.path,
            content=content,
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


@router.post("/import")
async def import_skill(request: Request, file: UploadFile = File(...)):
    """导入Skill包（zip格式）"""
    try:
        if not file.filename.endswith('.zip'):
            return fail_response(message="只支持zip格式的skill包")

        skill_manager = request.app.state.skill_manager
        content = await file.read()

        # 打开zip文件
        import io
        with zipfile.ZipFile(io.BytesIO(content), 'r') as zip_ref:
            # 获取所有条目，找到顶层目录
            entries = zip_ref.namelist()
            if not entries:
                return fail_response(message="zip包内容为空")

            # 找到skill顶层目录（第一个目录）
            skill_dir_prefix = None
            for name in entries:
                # zip条目的分隔符是 /
                parts = name.split('/')
                if len(parts) >= 2 and parts[0]:
                    skill_dir_prefix = parts[0]
                    skill_name = parts[0]
                    break

            if not skill_dir_prefix:
                return fail_response(message="zip包中未找到skill目录")

            # 检查SKILL.md是否存在
            skill_md_path = f"{skill_dir_prefix}/SKILL.md"
            if skill_md_path not in entries:
                return fail_response(message="skill包中缺少SKILL.md文件")

            target_dir = os.path.join(SKILLS_DIR, skill_name)

            # 检查是否已存在
            exists = os.path.exists(target_dir)
            if exists:
                logger.info(f"Skill {skill_name} 已存在，准备覆盖")
                shutil.rmtree(target_dir)
            os.makedirs(target_dir, exist_ok=True)

            # 解压所有文件到目标目录
            for name in entries:
                if not name.startswith(skill_dir_prefix + '/'):
                    continue

                # 获取相对路径
                relative_path = name[len(skill_dir_prefix) + 1:]
                if not relative_path:
                    continue

                target_path = os.path.join(target_dir, relative_path)

                # 创建目录
                if name.endswith('/'):
                    os.makedirs(target_path, exist_ok=True)
                else:
                    parent_dir = os.path.dirname(target_path)
                    if parent_dir:
                        os.makedirs(parent_dir, exist_ok=True)
                    with open(target_path, 'wb') as f:
                        f.write(zip_ref.read(name))

            # 重新加载skills
            skill_manager.reload_skills()

            action = "覆盖" if exists else "导入"
            logger.info(f"Skill {skill_name} {action}成功")
            return success_response(
                message=f"Skill {action}成功",
                data={"name": skill_name, "action": action, "exists": exists}
            )

    except Exception as e:
        logger.error(f"导入Skill失败: {str(e)}")
        return fail_response(message=f"导入Skill失败: {str(e)}")


@router.post("/preview")
async def preview_skill(file: UploadFile = File(...)):
    """预览skill包（获取skill名称，检查是否已存在）"""
    try:
        if not file.filename.endswith('.zip'):
            return fail_response(message="只支持zip格式的skill包")

        content = await file.read()

        # 打开zip文件
        import io
        with zipfile.ZipFile(io.BytesIO(content), 'r') as zip_ref:
            entries = zip_ref.namelist()
            if not entries:
                return fail_response(message="zip包内容为空")

            # 找到skill顶层目录
            skill_dir_prefix = None
            for name in entries:
                parts = name.split('/')
                if len(parts) >= 2 and parts[0]:
                    skill_dir_prefix = parts[0]
                    skill_name = parts[0]
                    break

            if not skill_dir_prefix:
                return fail_response(message="zip包中未找到skill目录")

            # 检查SKILL.md是否存在
            skill_md_path = f"{skill_dir_prefix}/SKILL.md"
            if skill_md_path not in entries:
                return fail_response(message="skill包中缺少SKILL.md文件")

            # 检查是否已存在
            target_dir = os.path.join(SKILLS_DIR, skill_name)
            exists = os.path.exists(target_dir)

            return success_response(
                data={"name": skill_name, "exists": exists},
                message="预览成功"
            )

    except Exception as e:
        logger.error(f"预览Skill失败: {str(e)}")
        return fail_response(message=f"预览Skill失败: {str(e)}")
