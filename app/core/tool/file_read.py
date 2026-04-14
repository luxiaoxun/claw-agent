from typing import Optional, List
from langchain.tools import tool
from pydantic import BaseModel, Field
from pathlib import Path
import base64
import mimetypes
from config.logging_config import get_logger
from config.settings import WORKSPACE_DIR

logger = get_logger(__name__)

# Constants
MAX_BYTES = 50 * 1024  # 50KB

# Binary file extensions
BINARY_EXTENSIONS = {
    '.zip', '.tar', '.gz', '.exe', '.dll', '.so', '.class', '.jar', '.war',
    '.7z', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods',
    '.odp', '.bin', '.dat', '.obj', '.o', '.a', '.lib', '.wasm', '.pyc', '.pyo'
}

# Supported image MIME types
IMAGE_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'
}


class FileReadInput(BaseModel):
    """Input parameters for file reading tool"""
    path: str = Field(description="File path (absolute path or relative path to workspace directory)")
    skill_name: Optional[str] = Field(default=None, description="Skill name for locating skill files")


@tool("file_read", args_schema=FileReadInput)
def file_read(path: str, skill_name: Optional[str] = None) -> str:
    """
    Read file content with support for multiple formats:
    - Text files: Returns original file content
    - Image files: Returns base64 encoded data
    - PDF files: Returns base64 encoded data
    - Automatically detects and rejects binary files

    Parameters:
    - path: File path (absolute path or relative path to 'workspace' directory)
    - skill_name: Skill name (optional, for reading files under 'workspace/skills')
    """
    # Initialize paths
    workspace_dir = Path(WORKSPACE_DIR)
    skills_dir = workspace_dir / "skills"

    logger.info(f"Reading file - path: {path}, skill_name: {skill_name}")

    try:
        # Resolve file path
        file_path = _resolve_path(
            path=path,
            skill_name=skill_name,
            workspace_dir=workspace_dir,
            skills_dir=skills_dir
        )

        logger.info(f"Resolved file path: {file_path}")
        if not file_path or not file_path.exists():
            # Try to find similar files
            search_dir = None
            if skill_name:
                search_dir = skills_dir / skill_name
            elif workspace_dir.exists():
                search_dir = workspace_dir

            if search_dir and search_dir.exists():
                suggestions = _find_similar_files(search_dir, Path(path).name)
                if suggestions:
                    error_msg = f"Error: File not found - {path}\n\nDid you mean one of these?\n" + "\n".join(
                        suggestions)
                else:
                    error_msg = f"Error: File not found - {path}"
            else:
                error_msg = f"Error: File not found - {path}"

            logger.error(f"File not found: {path}")
            return error_msg

        # Security check
        if not _is_path_allowed(file_path, workspace_dir):
            error_msg = f"Error: Access denied - {path} (path not in workspace directory)"
            logger.error(f"Access denied: {file_path}")
            return error_msg

        # Check if it's a file
        if not file_path.is_file():
            if file_path.is_dir():
                error_msg = f"Error: {path} is a directory, please specify a file name"
                logger.error(f"Path is a directory: {file_path}")
                return error_msg
            error_msg = f"Error: {path} is not a file"
            logger.error(f"Path is not a file: {file_path}")
            return error_msg

        # Get MIME type
        mime_type = _get_mime_type(file_path)

        # Handle images
        if mime_type in IMAGE_MIME_TYPES:
            logger.info(f"Processing image file: {file_path}")
            return _read_image(file_path, mime_type)

        # Handle PDFs
        if mime_type == 'application/pdf':
            logger.info(f"Processing PDF file: {file_path}")
            return _read_pdf(file_path, mime_type)

        # Detect binary files (excluding images and PDFs)
        if _is_binary_file(file_path):
            error_msg = f"Error: Cannot read binary file - {path} (MIME type: {mime_type})"
            logger.error(f"Binary file rejected: {file_path}, MIME type: {mime_type}")
            return error_msg

        # Read text file
        logger.info(f"Processing text file: {file_path}")
        return _read_text_file(file_path)

    except PermissionError as e:
        error_msg = f"Error: Permission denied - {str(e)}"
        logger.error(f"Permission denied reading {path}: {str(e)}")
        return error_msg
    except Exception as e:
        error_msg = f"Error reading file: {str(e)}"
        logger.error(f"Unexpected error reading file {path}: {str(e)}")
        return error_msg


def _resolve_path(path: str, skill_name: Optional[str], workspace_dir: Path, skills_dir: Path) -> Optional[Path]:
    """
    Resolve file path with priority:
    1. If absolute path exists, use it directly
    2. If skill_name provided, search under workspace/skills/skill_name
    3. Search under workspace with relative path
    4. Search under workspace/skills

    Returns:
        Resolved Path object, None if not found
    """
    path_obj = Path(path).resolve()
    logger.debug(f"Resolving path: {path}, skill_name: {skill_name}")

    # 1. Absolute path
    if path_obj.is_absolute():
        if path_obj.exists():
            logger.debug(f"Found absolute path: {path_obj}")
            return path_obj
        else:
            logger.debug(f"Absolute path does not exist: {path_obj}")

    # 2. Use skill_name
    if skill_name:
        candidate = skills_dir / skill_name / path
        if candidate.exists():
            logger.debug(f"Found path with skill_name: {candidate}")
            return candidate
        # Try with just filename
        candidate = skills_dir / skill_name / Path(path).name
        if candidate.exists():
            logger.debug(f"Found filename with skill_name: {candidate}")
            return candidate

    # 3. Search under workspace
    candidate = workspace_dir / path
    if candidate.exists():
        logger.debug(f"Found path under workspace: {candidate}")
        return candidate

    # 4. Search under workspace/skills
    candidate = skills_dir / path
    if candidate.exists():
        logger.debug(f"Found path under skill: {candidate}")
        return candidate

    logger.info(f"Path not found: {path}")
    return None


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


def _is_binary_file(filepath: Path) -> bool:
    """Check if file is binary"""
    # Check extension
    ext = filepath.suffix.lower()
    if ext in BINARY_EXTENSIONS:
        logger.debug(f"Binary file detected by extension: {filepath} (extension: {ext})")
        return True

    # Check content
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(4096)
            if not chunk:
                return False

            # Check for null bytes
            if b'\x00' in chunk:
                logger.debug(f"Binary file detected by null bytes: {filepath}")
                return True

            # Count non-printable characters
            non_printable = sum(
                1 for byte in chunk
                if byte < 9 or (byte > 13 and byte < 32)
            )

            # Consider binary if >30% non-printable
            is_binary = non_printable / len(chunk) > 0.3
            if is_binary:
                logger.debug(
                    f"Binary file detected by content analysis: {filepath} (non-printable ratio: {non_printable / len(chunk):.2f})")
            return is_binary
    except Exception as e:
        logger.error(f"Error checking binary file: {str(e)}")
        return False


def _get_mime_type(filepath: Path) -> str:
    """Get MIME type of file"""
    mime_type, _ = mimetypes.guess_type(str(filepath))
    mime_type = mime_type or 'application/octet-stream'
    logger.debug(f"Detected MIME type for {filepath}: {mime_type}")
    return mime_type


def _find_similar_files(directory: Path, filename: str, max_suggestions: int = 3) -> List[str]:
    """Find similar files in directory for error suggestions"""
    try:
        if not directory.exists():
            return []

        entries = [f.name for f in directory.iterdir() if f.is_file()]
        filename_lower = filename.lower()

        suggestions = []
        for entry in entries:
            entry_lower = entry.lower()
            if filename_lower in entry_lower or entry_lower in filename_lower:
                suggestions.append(str(directory / entry))

        suggestions = suggestions[:max_suggestions]
        if suggestions:
            logger.debug(f"Found similar files for {filename}: {suggestions}")
        return suggestions
    except Exception as e:
        logger.error(f"Error finding similar files: {str(e)}")
        return []


def _read_image(filepath: Path, mime_type: str) -> str:
    """Read image file and return base64 encoded data"""
    try:
        with open(filepath, 'rb') as f:
            content = f.read()

        data_url = f"data:{mime_type};base64,{base64.b64encode(content).decode('utf-8')}"

        logger.info(f"Successfully read image: {filepath}, size: {len(content)} bytes")
        return data_url
    except Exception as e:
        error_msg = f"Error reading image: {str(e)}"
        logger.error(f"Failed to read image {filepath}: {str(e)}")
        return error_msg


def _read_pdf(filepath: Path, mime_type: str) -> str:
    """Read PDF file and return base64 encoded data"""
    try:
        with open(filepath, 'rb') as f:
            content = f.read()

        data_url = f"data:{mime_type};base64,{base64.b64encode(content).decode('utf-8')}"

        logger.info(f"Successfully read PDF: {filepath}, size: {len(content)} bytes")
        return data_url
    except Exception as e:
        error_msg = f"Error reading PDF: {str(e)}"
        logger.error(f"Failed to read PDF {filepath}: {str(e)}")
        return error_msg


def _read_text_file(filepath: Path) -> str:
    """Read text file and return original content"""
    try:
        # Check file size
        file_size = filepath.stat().st_size
        if file_size > MAX_BYTES:
            logger.warning(f"Large file detected: {filepath}, size: {file_size} bytes")

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
