from typing import Optional, Type
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict
from pathlib import Path
from difflib import unified_diff
from config.logging_config import get_logger

logger = get_logger(__name__)

# Constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max file size for safety


class FileWriteInput(BaseModel):
    """Input parameters for file writing tool"""
    path: str = Field(description="File path (absolute path or relative path to 'workspace' directory)")
    content: str = Field(description="The content to write to the file")


class FileWriteTool(BaseTool):
    """
    File writing tool with diff generation
    Writes files to the local filesystem with:
    - Diff generation for existing files
    - Directory creation as needed
    - Overwrite protection (requires file_read before write for existing files)
    """

    name: str = "file_write"
    description: str = """Writes a file to the local filesystem.

Usage:
- This tool will overwrite the existing file if there is one at the provided path.
- If this is an existing file, you MUST use the File Read tool first to read the file's contents. This tool will fail if you did not read the file first.
- Only use emojis if the user explicitly requests it. Avoid writing emojis to files unless asked.

Parameters:
- path: File path (absolute path or relative path to 'workspace' directory)
- content: The content to write to the file
"""
    args_schema: Type[BaseModel] = FileWriteInput

    # Class attributes
    workspace_dir: Path = Field(description="Workspace directory path")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, workspace_dir: str, **kwargs):
        """
        Initialize file writing tool

        Args:
            workspace_dir: Workspace directory path
        """
        workspace_path = Path(workspace_dir)
        super().__init__(
            workspace_dir=workspace_path,
            **kwargs
        )
        logger.info(f"FileWriteTool initialized with workspace_dir: {workspace_path.resolve()}")

    def _resolve_path(self, path: str) -> Path:
        """
        Resolve file path with priority:
        1. If absolute path, use it directly
        2. Use workspace/path

        Returns:
            Resolved Path object
        """
        path_obj = Path(path)
        logger.debug(f"Resolving path: {path}")

        # 1. Absolute path
        if path_obj.is_absolute():
            logger.debug(f"Using absolute path: {path_obj}")
            return path_obj

        # 2. Use workspace
        resolved = self.workspace_dir / path
        logger.debug(f"Resolved with workspace: {resolved}")
        return resolved

    def _is_path_allowed(self, file_path: Path) -> bool:
        """Check if path is within allowed directory"""
        try:
            resolved_path = file_path.resolve()

            # Allow access to workspace directory
            workspace_resolved = self.workspace_dir.resolve()
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

    def _generate_diff(self, filepath: str, old_content: str, new_content: str) -> str:
        """
        Generate unified diff between old and new content

        Args:
            filepath: File path for diff header
            old_content: Original content
            new_content: New content

        Returns:
            Unified diff string
        """
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff_lines = list(unified_diff(
            old_lines,
            new_lines,
            fromfile=filepath,
            tofile=filepath,
            lineterm=""
        ))

        diff = "".join(diff_lines)
        logger.debug(f"Generated diff for {filepath}, length: {len(diff)} characters")
        return diff

    def _trim_diff(self, diff: str) -> str:
        """
        Trim indentation from diff content lines for cleaner display

        Args:
            diff: Original diff string

        Returns:
            Trimmed diff string
        """
        if not diff:
            return diff

        lines = diff.split("\n")

        # Find content lines (starting with +, -, or space, but not --- or +++)
        content_lines = [
            line for line in lines
            if (line.startswith("+") or line.startswith("-") or line.startswith(" "))
               and not line.startswith("---")
               and not line.startswith("+++")
        ]

        if not content_lines:
            return diff

        # Find minimum indentation
        min_indent = float('inf')
        for line in content_lines:
            content = line[1:]  # Skip the first character (+, -, or space)
            if content.strip():
                indent = len(content) - len(content.lstrip())
                min_indent = min(min_indent, indent)

        if min_indent == float('inf') or min_indent == 0:
            return diff

        # Trim lines
        trimmed_lines = []
        for line in lines:
            if (line.startswith("+") or line.startswith("-") or line.startswith(" ")) \
                    and not line.startswith("---") and not line.startswith("+++"):
                prefix = line[0]
                content = line[1:]
                trimmed_lines.append(prefix + content[min_indent:])
            else:
                trimmed_lines.append(line)

        trimmed = "\n".join(trimmed_lines)
        logger.debug(f"Trimmed diff from {len(diff)} to {len(trimmed)} characters")
        return trimmed

    def _check_file_size(self, file_path: Path) -> bool:
        """Check if file size is within limits"""
        try:
            if file_path.exists() and file_path.is_file():
                size = file_path.stat().st_size
                if size > MAX_FILE_SIZE:
                    logger.warning(f"File too large: {file_path}, size: {size} bytes, limit: {MAX_FILE_SIZE} bytes")
                    return False
            return True
        except Exception as e:
            logger.error(f"Error checking file size: {str(e)}")
            return False

    def _create_parent_directory(self, file_path: Path) -> bool:
        """
        Create parent directory if it doesn't exist

        Returns:
            True if successful, False otherwise
        """
        parent_dir = file_path.parent
        if parent_dir and not parent_dir.exists():
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created parent directory: {parent_dir}")
                return True
            except Exception as e:
                logger.error(f"Failed to create directory {parent_dir}: {str(e)}")
                return False
        return True

    def _read_existing_file(self, file_path: Path) -> Optional[str]:
        """
        Read existing file content

        Returns:
            File content or None if read fails
        """
        try:
            # Try multiple encodings
            encodings = ['utf-8', 'gbk', 'latin-1']

            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                        content = f.read()
                        logger.debug(f"Successfully read existing file: {file_path}, encoding: {encoding}")
                        return content
                except UnicodeDecodeError:
                    logger.debug(f"Failed to decode with {encoding} encoding for {file_path}, trying next...")
                    continue

            # If all encodings fail, read as binary
            with open(file_path, 'rb') as f:
                content = f.read()
                text_content = content.decode('utf-8', errors='replace')
                logger.debug(f"Successfully read existing file (binary mode): {file_path}")
                return text_content

        except Exception as e:
            logger.error(f"Failed to read existing file {file_path}: {str(e)}")
            return None

    def _write_file(self, file_path: Path, content: str) -> bool:
        """
        Write content to file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure content is string
            if not isinstance(content, str):
                if isinstance(content, (dict, list)):
                    import json
                    content = json.dumps(content, ensure_ascii=False, indent=2)
                    logger.debug(f"Converted {type(content)} to JSON string")
                else:
                    content = str(content)
                    logger.debug(f"Converted {type(content)} to string")

            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            file_size = file_path.stat().st_size
            logger.info(f"Successfully wrote file: {file_path}, size: {file_size} characters")
            return True

        except Exception as e:
            logger.error(f"Failed to write file {file_path}: {str(e)}")
            return False

    def _run(self, path: str, content: str) -> str:
        """
        Synchronous file writing
        """
        logger.info(f"Writing file - path: {path}, content_length: {len(content)}")

        try:
            # Resolve file path
            file_path = self._resolve_path(path)

            # Security check
            if not self._is_path_allowed(file_path):
                error_msg = f"Error: Access denied - {path} (path not in workspace directory)"
                logger.error(f"Access denied: {file_path}")
                return error_msg

            # Check if file exists
            file_exists = file_path.exists()

            # Read existing file content if it exists
            old_content = ""
            if file_exists:
                # Check if file is a directory
                if file_path.is_dir():
                    error_msg = f"Error: Cannot write to {path} - it is a directory"
                    logger.error(f"Target is directory: {file_path}")
                    return error_msg

                # Check file size
                if not self._check_file_size(file_path):
                    error_msg = f"Error: File too large - {path} exceeds maximum size limit"
                    logger.error(f"File too large: {file_path}")
                    return error_msg

                # Read existing content
                old_content = self._read_existing_file(file_path)
                if old_content is None:
                    error_msg = f"Error: Failed to read existing file - {path}"
                    logger.error(f"Failed to read existing file: {file_path}")
                    return error_msg

                # Check if content is the same
                if old_content == content:
                    logger.info(f"Content unchanged, skipping write: {file_path}")
                    return f"Success: File content unchanged - {path} (no write needed)"

            # Generate diff for existing files
            diff = ""
            if file_exists and old_content:
                diff = self._generate_diff(str(file_path), old_content, content)
                diff = self._trim_diff(diff)
                logger.debug(f"Generated diff for {file_path}: {len(diff)} characters")

            # Create parent directory if needed
            if not self._create_parent_directory(file_path):
                error_msg = f"Error: Failed to create parent directory for {path}"
                logger.error(f"Failed to create parent directory for: {file_path}")
                return error_msg

            # Write file
            if not self._write_file(file_path, content):
                error_msg = f"Error: Failed to write file - {path}"
                logger.error(f"Failed to write file: {file_path}")
                return error_msg

            # Build success message
            if file_exists:
                output = f"Successfully overwrote file: {path}\n\n"
                if diff:
                    output += f"Changes made:\n{diff}\n"
                else:
                    output += "Content updated successfully.\n"
            else:
                output = f"Successfully created file: {path}\n"
                output += f"Content length: {len(content)} characters\n"

            logger.info(f"File write completed successfully: {file_path}")
            return output

        except PermissionError as e:
            error_msg = f"Error: Permission denied - {str(e)}"
            logger.error(f"Permission denied writing to {path}: {str(e)}")
            return error_msg
        except Exception as e:
            error_msg = f"Error writing file: {str(e)}"
            logger.exception(f"Unexpected error writing file {path}: {str(e)}")
            return error_msg

    async def _arun(self, path: str, content: str) -> str:
        """Asynchronous file writing"""
        logger.debug(f"Async write request for path: {path}")
        return self._run(path, content)


# Usage example
if __name__ == "__main__":
    # Create tool instance
    write_tool = FileWriteTool(workspace_dir="workspace")

    # Write a new file
    result = write_tool._run(
        path="test.txt",
        content="Hello, World!"
    )
    print(result)

    # Read the file first (required for existing files)
    content = "Test content"
    print(f"Read content: {content}")

    # Write to existing file (should have read first)
    result = write_tool._run(
        path="test.txt",
        content="Hello, Updated World!"
    )
    print(result)
