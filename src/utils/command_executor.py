"""Command execution utilities for sandbox backends.

This module provides unified command execution logic that is shared across
different local sandbox backends (FilesystemSandboxBackend, StateSandboxBackend).

Features:
- Unified subprocess execution with timeout support
- Consistent stdout/stderr handling
- Standardized error responses
- Output truncation support
"""

import subprocess
from typing import Optional

from deepagents.backends.protocol import ExecuteResponse

# Command execution defaults
DEFAULT_COMMAND_TIMEOUT = 30  # seconds
DEFAULT_MAX_OUTPUT_SIZE = 100000  # characters


def execute_local_command(
        command: str,
        cwd: Optional[str] = None,
        timeout: int = DEFAULT_COMMAND_TIMEOUT,
        max_output_size: int = DEFAULT_MAX_OUTPUT_SIZE,
) -> ExecuteResponse:
    """Execute a shell command locally with unified error handling.

    This function provides a standardized way to execute shell commands
    across different sandbox backends. It handles:
    - Subprocess execution with shell=True
    - Timeout enforcement
    - stdout/stderr combination
    - Output truncation via create_execute_response

    Args:
        command: Shell command to execute
        cwd: Working directory for command execution (None uses current directory)
        timeout: Maximum execution time in seconds (default: 30)
        max_output_size: Maximum output size in characters for truncation (default: 100000)

    Returns:
        ExecuteResponse with combined output, exit code, and truncation flag

    Example:
        >>> result = execute_local_command("ls -la", cwd="/tmp", timeout=10)
        >>> print(result.exit_code)
        0
        >>> print(result.output)
        total 0
        ...
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            encoding='utf-8',
            errors='replace'  # 替换无法解码的字符
        )

        output = combine_stdout_stderr(result.stdout, result.stderr)

        return create_execute_response(
            output=output,
            exit_code=result.returncode,
            max_output_size=max_output_size,
        )

    except subprocess.TimeoutExpired:
        return create_timeout_error_response(timeout)
    except Exception as e:
        return create_error_response(str(e))


def combine_stdout_stderr(stdout: Optional[str], stderr: Optional[str]) -> str:
    """Combine stdout and stderr into a single output string.

    Args:
        stdout: Standard output from command execution
        stderr: Standard error from command execution

    Returns:
        Combined output string with stderr appended after stdout (if both exist)
    """
    output = ""
    if stdout:
        output += stdout
    if stderr:
        if output:
            output += "\n"
        output += stderr
    return output


def create_timeout_error_response(timeout: int) -> ExecuteResponse:
    """Create a standardized timeout error response.

    Args:
        timeout: The timeout value in seconds that was exceeded

    Returns:
        ExecuteResponse with timeout error message
    """
    return ExecuteResponse(
        output=f"Error: Command execution timed out ({timeout} seconds limit)",
        exit_code=-1,
        truncated=False,
    )


def create_error_response(error_message: str) -> ExecuteResponse:
    """Create a standardized error response.

    Args:
        error_message: The error message to include in the response

    Returns:
        ExecuteResponse with error message
    """
    return ExecuteResponse(
        output=f"Error executing command: {error_message}",
        exit_code=-1,
        truncated=False,
    )


def create_execute_response(
        output: str,
        exit_code: int,
        max_output_size: int,
        default_output: str = "(no output)",
) -> ExecuteResponse:
    """Create an ExecuteResponse with automatic output truncation.

    This is a convenience function that combines output truncation
    and ExecuteResponse creation, reducing code duplication across
    different backend implementations.

    Args:
        output: Command output string (may be empty)
        exit_code: Command exit code
        max_output_size: Maximum output size before truncation
        default_output: Default output string if output is empty (default: "(no output)")

    Returns:
        ExecuteResponse with truncated output and truncation flag

    Examples:
        >>> response = create_execute_response("output", 0, 100)
        >>> response.exit_code
        0
        >>> response.truncated
        False
        >>> response = create_execute_response("x" * 200, 0, 100)
        >>> response.truncated
        True
    """
    # Use default output if empty
    if not output:
        output = default_output

    # Truncate if necessary
    truncated_output, truncated = truncate_output(output, max_output_size)

    return ExecuteResponse(
        output=truncated_output,
        exit_code=exit_code,
        truncated=truncated,
    )


def truncate_output(output: str, max_size: int) -> tuple[str, bool]:
    """Truncate command output if it exceeds the maximum size.

    Args:
        output: Original command output string
        max_size: Maximum output size in characters

    Returns:
        Tuple of (truncated_output, is_truncated)

    Examples:
        >>> truncate_output("short output", 100)
        ('short output', False)
        >>> truncate_output("x" * 200, 100)
        ('x' * 100, True)
    """
    if len(output) > max_size:
        return output[:max_size], True
    return output, False
