import os.path
from typing import Optional, Type, Dict, Any, List
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

from config import WORK_DIR
from config.logging_config import get_logger
from utils.command_executor import execute_local_command, DEFAULT_COMMAND_TIMEOUT

logger = get_logger(__name__)


class CommandExecuteInput(BaseModel):
    """Command execution tool input parameters"""
    command: str = Field(
        description="Complete command to execute (including interpreter, e.g.: python script.py, bash script.sh, node script.js)")
    working_dir: Optional[str] = Field(
        default=None,
        description="Working directory for command execution"
    )
    timeout: int = Field(
        default=30,
        description="Command execution timeout (seconds), default 30 seconds"
    )
    args: Optional[str] = Field(
        default=None,
        description="Command line arguments to pass to the command"
    )


class CommandExecuteTool(BaseTool):
    """
    Command execution tool
    Agent executes various types of commands (Python, Shell, Node.js, etc.) through this tool
    The command parameter directly contains the complete command and interpreter information

    Supports multiple command types:
    1. Python command: python script.py or python3 script.py
    2. Shell command: bash script.sh or sh script.sh
    3. Node.js/JavaScript command: node script.js
    """

    name: str = "command_execute"
    description: str = """
    Execute command code or command files. The command parameter needs to contain the complete command and interpreter information.

    Usage examples:
    1. Execute Python file: {"command": "python /path/to/script.py"}
    2. Execute Shell command: {"command": "bash -c 'ls -la'"}
    3. Execute Node.js code: {"command": "node -e 'console.log(\"Hello\");'"}
    4. Execute with arguments: {"command": "python /path/to/script.py", "args": "--verbose --debug"}
    5. Execute Python code: {"command": "python3 -c 'print(\"Hello World\")'"}

    Notes:
    - Command execution has a timeout limit (default 30 seconds)
    - Output will be truncated to prevent oversized output (default 100000 characters)
    - Working directory can be specified, default uses current directory
    """
    args_schema: Type[BaseModel] = CommandExecuteInput

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _execute_command(
            self,
            command: str,
            working_dir: Optional[str] = None,
            timeout: int = 30,
            args: Optional[str] = None
    ) -> str:
        """
        Execute command

        Args:
            command: Complete command (including interpreter)
            working_dir: Working directory
            timeout: Timeout duration
            args: Command line arguments

        Returns:
            Execution result
        """
        try:
            # Build complete command
            full_command = command
            if args:
                full_command = f"{command} {args}"

            # Execute command
            logger.info(f"Execute command: {full_command}, cwd: {working_dir}, timeout: {timeout}")
            result = execute_local_command(
                command=full_command,
                cwd=working_dir,
                timeout=timeout
            )

            # Format output
            output = result.output
            if result.exit_code != 0:
                logger.info(f"Execute command failed: {full_command}\n{output}")
                output = f"Command execution failed (exit_code: {result.exit_code})\n{output}"

            if result.truncated:
                output += "\n\nWarning: command execution result is truncated (exceeds the size limit)"

            return output

        except Exception as e:
            logger.error(f"Execute command error: {e}", exc_info=True)
            return f"Error: execute command failed - {str(e)}"

    def _run(
            self,
            command: str,
            working_dir: Optional[str] = None,
            timeout: int = 30,
            args: Optional[str] = None
    ) -> str:
        """
        Synchronously execute command

        Args:
            command: Complete command (including interpreter)
            working_dir: Working directory
            timeout: Timeout duration
            args: Command line arguments

        Returns:
            Execution result
        """
        try:
            # Log execution information
            logger.info(f"Execute command: {command}, args: {args}")
            if working_dir:
                logger.info(f"Working directory: {working_dir}")
            else:
                working_dir = os.path.join(WORK_DIR, "workspace/skills")
                logger.info(f"Working directory: {working_dir}")
            if timeout != DEFAULT_COMMAND_TIMEOUT:
                logger.info(f"Timeout: {timeout} seconds")

            # Execute command
            result = self._execute_command(
                command=command,
                working_dir=working_dir,
                timeout=timeout,
                args=args
            )

            return result

        except Exception as e:
            logger.error(f"Command execution failed: {e}", exc_info=True)
            return f"Command execution failed: {str(e)}"

    async def _arun(
            self,
            command: str,
            working_dir: Optional[str] = None,
            timeout: int = 30,
            args: Optional[str] = None
    ) -> str:
        """Asynchronously execute command"""
        # Currently using synchronous implementation because execute_local_command is synchronous
        return self._run(command, working_dir, timeout, args)
