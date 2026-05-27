import os.path
from typing import Optional
from langchain.tools import tool
from pydantic import BaseModel, Field

from soma.config.logging_config import get_logger
from soma.config.settings import WORKSPACE_DIR
from soma.utils.command_executor import execute_local_command, DEFAULT_COMMAND_TIMEOUT

logger = get_logger(__name__)

MAX_OUTPUT_LENGTH = 100000  # 10万字符


class BashInput(BaseModel):
    """Bash tool input parameters"""
    command: str = Field(
        description="Complete command to execute (including interpreter, arguments, e.g.: python script.py --verbose)"
    )
    cwd: Optional[str] = Field(
        default=None,
        description="Working directory for command execution"
    )
    timeout: int = Field(
        default=30,
        description="Command execution timeout (seconds), default 30 seconds"
    )


@tool("bash", args_schema=BashInput)
def bash(
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30,
) -> str:
    """
    Execute commands or scripts.

    Working directory defaults to WORKSPACE_DIR/.soma/skills/ for scripts under skills directory.

    Usage:
    - Execute Python file: {"command": "python script.py"}
    - Execute with arguments: {"command": "python script.py --verbose --debug"}
    - Execute Shell command: {"command": "bash -c 'ls -la'"}
    - Execute Node.js code: {"command": "node -e 'console.log(\"Hello\")'"}
    - Specify working directory: {"command": "python script.py", "cwd": "/path/to/dir"}

    Notes:
    - Command execution has a timeout limit (default 30 seconds, max 120 seconds)
    - Output is truncated to prevent oversized output (max 100000 characters)
    - Working directory defaults to WORKSPACE_DIR/.soma/skills/
    """
    # Input validation
    if not command or not command.strip():
        return "Error: command is required"

    try:
        # Handle working directory
        if cwd:
            working_dir = cwd
            logger.info(f"Working directory: {working_dir}")
        else:
            working_dir = os.path.join(WORKSPACE_DIR, ".soma", "skills")
            logger.info(f"Working directory: {working_dir}")

        if timeout != DEFAULT_COMMAND_TIMEOUT:
            logger.info(f"Timeout: {timeout} seconds")

        # Execute command
        logger.info(f"Execute command: {command}, cwd: {working_dir}, timeout: {timeout}")
        result = execute_local_command(
            command=command,
            cwd=working_dir,
            timeout=timeout
        )

        # Format output
        output = result.output
        if result.exit_code != 0:
            logger.info(f"Execute command failed: {command}, exit_code: {result.exit_code}")
            output = f"Command failed (exit_code: {result.exit_code})\n{output}"

        if result.truncated:
            output += f"\n\n[Output truncated, exceeds {MAX_OUTPUT_LENGTH} characters limit]"

        # Final length check
        if len(output) > MAX_OUTPUT_LENGTH:
            output = output[:MAX_OUTPUT_LENGTH] + f"\n\n[Output truncated at {MAX_OUTPUT_LENGTH} characters]"

        return output

    except Exception as e:
        logger.error(f"Command execution failed: {e}", exc_info=True)
        return f"Error: Command execution failed - {str(e)}"