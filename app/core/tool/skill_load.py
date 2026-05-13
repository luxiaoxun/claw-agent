from langchain.tools import tool
from pydantic import BaseModel, Field
from pathlib import Path
from config.logging_config import get_logger
from config.settings import WORKSPACE_DIR

logger = get_logger(__name__)


class SkillLoadInput(BaseModel):
    """Input parameters for skill loading tool"""
    skill_name: str = Field(description="Skill name to load, will read WORKSPACE_DIR/{skill_name}/SKILL.md")


@tool("skill_load", args_schema=SkillLoadInput)
def skill_load(skill_name: str) -> str:
    """
    Load skill content from SKILL.md file.

    Reads skill file from path: WORKSPACE_DIR/{skill_name}/SKILL.md

    Parameters:
    - skill_name: Name of the skill to load
    """
    workspace_dir = Path(WORKSPACE_DIR)

    logger.info(f"Loading skill - skill_name: {skill_name}")

    try:
        # Build skill file path
        skill_path = workspace_dir / "skills" / skill_name / "SKILL.md"

        logger.info(f"Resolved skill path: {skill_path}")

        # Check if file exists
        if not skill_path.exists():
            error_msg = f"Error: Skill not found - '{skill_name}' (expected path: {skill_path})"
            logger.error(f"Skill not found: {skill_name}")
            return error_msg

        # Security check
        if not _is_path_allowed(skill_path, workspace_dir):
            error_msg = f"Error: Access denied - {skill_name} (path not in workspace directory)"
            logger.error(f"Access denied: {skill_path}")
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


def _is_path_allowed(file_path: Path, workspace_dir: Path) -> bool:
    """Check if path is within allowed directory"""
    try:
        resolved_path = file_path.resolve()

        # Allow access to workspace directory
        workspace_resolved = workspace_dir.resolve()
        if str(resolved_path).startswith(str(workspace_resolved)):
            logger.debug(f"Path allowed within workspace: {resolved_path}")
            return True

        # Security check: prevent path traversal
        if '..' in str(file_path) or str(file_path).startswith('/') or str(file_path).startswith('\\'):
            logger.warning(f"Path traversal attempt detected: {file_path}")
            return False

        logger.warning(f"Path not allowed: {resolved_path} (outside workspace)")
        return False
    except Exception as e:
        logger.error(f"Error checking path permission: {str(e)}")
        return False


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
