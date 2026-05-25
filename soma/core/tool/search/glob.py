"""
Glob Tool - Fast file pattern matching

Fast file pattern matching tool that:
- Supports glob patterns like "**/*.js" or "src/**/*.ts"
- Returns matching file paths sorted by modification time
- Uses ripgrep for fast searching when available, falls back to Python's glob
"""

import os
import shutil
import glob as python_glob
import subprocess
from typing import Optional, List, Dict, Any

from langchain.tools import tool
from pydantic import BaseModel, Field

from soma.config.logging_config import get_logger

logger = get_logger(__name__)

MAX_FILES = 100


class GlobInput(BaseModel):
    """Input parameters for glob tool"""
    pattern: str = Field(
        description='Glob pattern to match files, e.g. "**/*.js", "*.py", "src/**/*.ts". Use ** for recursive matching.'
    )
    path: Optional[str] = Field(
        default=None,
        description="Directory to search in. Defaults to current working directory."
    )
    max_results: int = Field(
        default=100,
        description="Maximum number of results to return"
    )


def find_ripgrep() -> Optional[str]:
    """Find ripgrep executable"""
    for name in ['rg', 'ripgrep']:
        path = shutil.which(name)
        if path:
            return path
    return None


def fallback_glob(cwd: str, pattern: str) -> List[str]:
    """Fallback glob using Python's glob module"""
    if not pattern.startswith("**/") and not pattern.startswith("**\\"):
        pattern = "**/" + pattern

    full_pattern = os.path.join(cwd, pattern)
    matches = []

    for filepath in python_glob.glob(full_pattern, recursive=True):
        if os.path.isfile(filepath):
            rel_path = os.path.relpath(filepath, cwd)
            matches.append(rel_path)

    return matches


def ripgrep_files(
    rg_path: str,
    cwd: str,
    glob_patterns: List[str]
) -> List[str]:
    """Find files using ripgrep --files"""
    args = [
        rg_path,
        "--files",
        "--hidden",
        "--follow",
        "--no-messages"
    ]

    for pattern in glob_patterns:
        args.extend(["--glob", pattern])

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=60
        )
        output = result.stdout

        files = []
        for line in output.strip().split('\n'):
            if line.strip():
                files.append(line.strip())

        return files
    except Exception as e:
        logger.warning(f"ripgrep_files failed: {e}")
        return []


@tool("glob", args_schema=GlobInput)
def glob(
        pattern: str,
        path: Optional[str] = None,
        max_results: int = 100
) -> str:
    """
    Fast file pattern matching tool.

    Supports glob patterns like "**/*.js", "src/**/*.ts", "*.py".
    Returns matching file paths sorted by modification time.

    Usage:
    - Find all Python files: pattern="**/*.py"
    - Find all JavaScript files: pattern="**/*.js"
    - Find files in src directory: pattern="src/**/*.ts"
    - Search in specific directory: path="/path/to/dir"

    Args:
        pattern: Glob pattern to match files (e.g. "**/*.js", "*.py")
        path: Directory to search in. Defaults to current working directory.
        max_results: Maximum number of results to return (default 100)
    """
    if not pattern:
        return "Error: pattern is required"

    # Use current directory if path not specified
    search_path = os.path.abspath(path) if path else os.getcwd()

    if not os.path.exists(search_path):
        return f"Error: Directory does not exist - {search_path}"

    if not os.path.isdir(search_path):
        return f"Error: Path is not a directory - {search_path}"

    logger.info(f"Glob - pattern: {pattern}, path: {search_path}, max: {max_results}")

    files: List[Dict[str, Any]] = []

    # Try ripgrep first, fallback to Python glob
    rg_path = find_ripgrep()

    try:
        if rg_path:
            # Use ripgrep for fast file listing
            rg_files = ripgrep_files(rg_path, search_path, [pattern])

            for filepath in rg_files:
                full_path = os.path.join(search_path, filepath)
                if os.path.isfile(full_path):
                    try:
                        stat = os.stat(full_path)
                        files.append({
                            'path': full_path,
                            'mtime': stat.st_mtime
                        })
                    except OSError:
                        pass
        else:
            logger.info("ripgrep not found, using Python glob fallback")
            for filepath in fallback_glob(search_path, pattern):
                full_path = os.path.join(search_path, filepath)
                try:
                    stat = os.stat(full_path)
                    files.append({
                        'path': full_path,
                        'mtime': stat.st_mtime
                    })
                except OSError:
                    pass

    except Exception as e:
        logger.error(f"Glob search failed: {e}")
        return f"Error: Glob search failed - {str(e)}"

    # Sort by modification time (most recent first)
    files.sort(key=lambda x: x['mtime'], reverse=True)

    # Truncate results
    truncated = len(files) > max_results
    final_files = files[:max_results]

    if not final_files:
        return f"No files found matching pattern: {pattern}"

    # Build output
    output_lines = [
        f"Found {len(final_files)} files",
        f"Pattern: {pattern}",
        f"Path: {search_path}",
        "",
        "Matching files:"
    ]

    for f in final_files:
        output_lines.append(f['path'])

    if truncated:
        output_lines.append("")
        output_lines.append(f"(Results truncated to {max_results} files)")

    logger.info(f"Glob completed - found {len(final_files)} files")
    return "\n".join(output_lines)


if __name__ == "__main__":
    print("=" * 80)
    print("Testing Glob Tool")
    print("=" * 80)

    # Test 1: Find Python files
    print("\n1. Find Python files:")
    result = glob.invoke({
        "pattern": "**/*.py",
        "path": "D:/work/workspace/soma",
        "max_results": 20
    })
    print(result[:1000])

    # Test 2: Find JSON files
    print("\n2. Find JSON files:")
    result = glob.invoke({
        "pattern": "**/*.json",
        "path": "D:/work/workspace/soma",
        "max_results": 10
    })
    print(result[:500])