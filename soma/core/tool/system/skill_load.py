from langchain.tools import tool
from pydantic import BaseModel, Field
from pathlib import Path
from soma.config.logging_config import get_logger
from soma.config.settings import SKILLS_DIR

logger = get_logger(__name__)


class SkillLoadInput(BaseModel):
    skill_name: str = Field(description="Skill name to load")


@tool("skill_load", args_schema=SkillLoadInput)
def skill_load(skill_name: str) -> str:
    """
    Load skill content from SKILL.md file.

    Reads skill file from path: SKILLS_DIR/{skill_name}/SKILL.md
    """
    skill_dir = Path(SKILLS_DIR)

    logger.info(f"Loading skill - skill_name: {skill_name}")

    try:
        # Build skill file path
        skill_path = skill_dir / skill_name / "SKILL.md"

        logger.info(f"Resolved skill path: {skill_path}")

        # Check if file exists
        if not skill_path.exists():
            error_msg = f"Error: Skill not found - '{skill_name}' (expected path: {skill_path})"
            logger.error(f"Skill not found: {skill_name}")
            return error_msg

        # Check if it's a file
        if not skill_path.is_file():
            error_msg = f"Error: {skill_name} is not a valid skill (SKILL.md not found)"
            logger.error(f"Path is not a file: {skill_path}")
            return error_msg

        # Read skill file as text
        logger.info(f"Processing skill file: {skill_path}")
        content = _read_text_file(skill_path)

        # Add skill metadata header
        result = f"[Skill: {skill_name}]\nPath: {skill_path}\n\n{content}"

        return result

    except PermissionError as e:
        error_msg = f"Error: Permission denied - {str(e)}"
        logger.error(f"Permission denied reading skill {skill_name}: {str(e)}")
        return error_msg
    except Exception as e:
        error_msg = f"Error reading skill: {str(e)}"
        logger.error(f"Unexpected error reading skill {skill_name}: {str(e)}")
        return error_msg


def _read_text_file(filepath: Path) -> str:
    """Read text file and return original content"""
    try:
        # Try multiple encodings
        encodings = ['utf-8', 'gbk', 'latin-1']

        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding, errors='replace') as f:
                    content = f.read()
                    logger.info(
                        f"Successfully read text file: {filepath}, size: {len(content)} characters, encoding: {encoding}")
                    return content
            except UnicodeDecodeError:
                logger.debug(f"Failed to decode with {encoding} encoding for {filepath}, trying next...")
                continue

        # If all encodings fail, read as binary and decode with replacement
        with open(filepath, 'rb') as f:
            content = f.read()
            text_content = content.decode('utf-8', errors='replace')
            logger.info(
                f"Successfully read text file (binary mode): {filepath}, size: {len(text_content)} characters")
            return text_content

    except Exception as e:
        error_msg = f"Error reading file: {str(e)}"
        logger.error(f"Failed to read text file {filepath}: {str(e)}")
        return error_msg
