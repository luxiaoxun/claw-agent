"""
Grep Tool - Code content search using regex

Fast content search tool that:
- Searches file contents using regular expressions
- Supports full regex syntax
- Filter files by pattern (include parameter)
- Returns results sorted by modification time
- Uses ripgrep when available, falls back to Python's re module
"""

import os
import shutil
import re
import fnmatch
import subprocess
from typing import Optional, List, Dict, Any

from langchain.tools import tool
from pydantic import BaseModel, Field

from soma.config.logging_config import get_logger

logger = get_logger(__name__)

MAX_LINE_LENGTH = 2000
MAX_MATCHES = 100


class GrepInput(BaseModel):
    """Input parameters for grep tool"""
    pattern: str = Field(
        description="The regex pattern to search for in file contents (e.g. 'log.*Error', 'function\\s+\\w+')"
    )
    path: Optional[str] = Field(
        default=None,
        description="Directory to search in. Defaults to current working directory."
    )
    include: Optional[str] = Field(
        default=None,
        description='File pattern filter, e.g. "*.js", "*.{ts,tsx}". Only search files matching this pattern.'
    )
    max_results: int = Field(
        default=100,
        description="Maximum number of matches to return"
    )


def find_ripgrep() -> Optional[str]:
    """Find ripgrep executable"""
    for name in ['rg', 'ripgrep']:
        path = shutil.which(name)
        if path:
            return path
    return None


def fallback_grep(
        pattern: str,
        search_path: str,
        include: Optional[str] = None,
        max_matches: int = MAX_MATCHES
) -> List[Dict[str, Any]]:
    """Fallback grep using Python's re module"""
    matches = []

    try:
        regex = re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")

    for root, dirs, files in os.walk(search_path):
        # Skip hidden and common ignore directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in (
            'node_modules', '__pycache__', '.git', 'dist', 'build', 'target'
        )]

        for filename in files:
            # Apply include filter
            if include:
                patterns = []
                if '{' in include:
                    match = re.match(r'\*\.?\{([^}]+)\}', include)
                    if match:
                        exts = match.group(1).split(',')
                        patterns = [f"*.{ext.strip()}" for ext in exts]
                else:
                    patterns = [include]

                if not any(fnmatch.fnmatch(filename, p) for p in patterns):
                    continue

            filepath = os.path.join(root, filename)

            try:
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            stat = os.stat(filepath)
                            matches.append({
                                'path': filepath,
                                'modTime': stat.st_mtime,
                                'lineNum': line_num,
                                'lineText': line.rstrip('\n\r')
                            })

                            if len(matches) >= max_matches * 10:
                                return matches

            except (IOError, OSError):
                continue

    return matches


def ripgrep_search(
        rg_path: str,
        pattern: str,
        search_path: str,
        include: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search using ripgrep"""
    args = [
        rg_path,
        "-nH",  # Line numbers, filenames
        "--hidden",
        "--follow",
        "--no-messages",
        "--field-match-separator=|",
        "--regexp", pattern
    ]

    if include:
        args.extend(["--glob", include])

    args.append(search_path)

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=120
        )
        output = result.stdout

        # Exit codes: 0 = matches found, 1 = no matches, 2 = errors
        if result.returncode == 1 or (result.returncode == 2 and not output.strip()):
            return []

        matches = []
        for line in output.strip().split('\n'):
            if not line:
                continue

            parts = line.split('|', 2)
            if len(parts) < 3:
                continue

            filepath, line_num_str, line_text = parts

            try:
                line_num = int(line_num_str)
            except ValueError:
                continue

            try:
                stat = os.stat(filepath)
                mod_time = stat.st_mtime
            except OSError:
                mod_time = 0

            matches.append({
                'path': filepath,
                'modTime': mod_time,
                'lineNum': line_num,
                'lineText': line_text
            })

        return matches
    except Exception as e:
        logger.warning(f"ripgrep_search failed: {e}")
        return []


@tool("grep", args_schema=GrepInput)
def grep(
        pattern: str,
        path: Optional[str] = None,
        include: Optional[str] = None,
        max_results: int = 100
) -> str:
    """
    Search file contents using regular expressions.

    Fast content search tool that:
    - Searches file contents using regular expressions
    - Supports full regex syntax (e.g. "log.*Error", "function\\s+\\w+")
    - Filter files by pattern with include parameter (e.g. "*.js", "*.{ts,tsx}")
    - Returns file paths and line numbers with matches sorted by modification time

    Usage:
    - Search for pattern: pattern="log.*Error"
    - Filter by file type: pattern="TODO", include="*.py"
    - Search in specific directory: path="/path/to/dir", pattern="class.*"
    """
    if not pattern:
        return "Error: pattern is required"

    search_path = os.path.abspath(path) if path else os.getcwd()

    if not os.path.exists(search_path):
        return f"Error: Directory does not exist - {search_path}"

    if not os.path.isdir(search_path):
        return f"Error: Path is not a directory - {search_path}"

    logger.info(f"Grep - pattern: {pattern}, path: {search_path}, include: {include}, max: {max_results}")

    matches: List[Dict[str, Any]] = []

    try:
        rg_path = find_ripgrep()

        if rg_path:
            matches = ripgrep_search(rg_path, pattern, search_path, include)
        else:
            logger.info("ripgrep not found, using Python regex fallback")
            matches = fallback_grep(pattern, search_path, include, max_results)

    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"Error: Search failed - {str(e)}"

    # Sort by modification time (most recent first)
    matches.sort(key=lambda x: x['modTime'], reverse=True)

    # Truncate results
    truncated = len(matches) > max_results
    final_matches = matches[:max_results]

    if not final_matches:
        return f"No files found matching pattern: {pattern}"

    # Build output
    output_lines = [
        f"Found {len(final_matches)} matches",
        f"Pattern: {pattern}",
        f"Path: {search_path}",
        f"Include: {include or '*'}",
        "",
        "Matching results:"
    ]

    current_file = ""
    for match in final_matches:
        if current_file != match['path']:
            if current_file:
                output_lines.append("")
            current_file = match['path']
            output_lines.append(f"{match['path']}:")

        # Truncate long lines
        line_text = match['lineText']
        if len(line_text) > MAX_LINE_LENGTH:
            line_text = line_text[:MAX_LINE_LENGTH] + "..."

        output_lines.append(f"  Line {match['lineNum']}: {line_text}")

    if truncated:
        output_lines.append("")
        output_lines.append(f"(Results truncated to {max_results} matches)")

    logger.info(f"Grep completed - found {len(final_matches)} matches")
    return "\n".join(output_lines)


if __name__ == "__main__":
    print("=" * 80)
    print("Testing Grep Tool")
    print("=" * 80)

    # Test 1: Search for Python files containing "tool"
    print("\n1. Search for 'tool' in Python files:")
    result = grep.invoke({
        "pattern": "tool",
        "path": "D:/work/workspace/soma",
        "include": "*.py",
        "max_results": 20
    })
    print(result[:2000])

    # Test 2: Search for "class.*Input"
    print("\n2. Search for 'class.*Input' pattern:")
    result = grep.invoke({
        "pattern": r"class\s+\w+Input",
        "path": "D:/work/workspace/soma",
        "max_results": 10
    })
    print(result[:1000])
