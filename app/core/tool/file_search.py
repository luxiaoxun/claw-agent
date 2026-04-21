"""
File Search Tool - Search for files by name pattern or content

Search for files by name pattern or content within a directory.
Supports glob patterns for filenames and regex for content search.
"""

import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

from langchain.tools import tool
from pydantic import BaseModel, Field

from config.logging_config import get_logger

logger = get_logger(__name__)

# Sensitive directories to exclude from search
SENSITIVE_DIRS = {
    '.ssh', '.gnupg', '.aws', '.azure', '.config',
    'node_modules', '.git', '.venv', 'venv', 'env',
    '__pycache__', '.pytest_cache', '.mypy_cache'
}


class FileSearchInput(BaseModel):
    """Input parameters for file search tool"""
    pattern: str = Field(
        description="File name pattern (glob syntax) or content search term. Examples: '*.py', 'test_*.json', 'config.*'"
    )
    directory: Optional[str] = Field(
        default=None,
        description="Directory to search in. Defaults to current working directory."
    )
    search_content: bool = Field(
        default=False,
        description="If true, search file contents instead of filenames. Pattern becomes a regex for content matching."
    )
    recursive: bool = Field(
        default=True,
        description="Search recursively in subdirectories. Defaults to true."
    )
    max_results: int = Field(
        default=100,
        description="Maximum number of results to return. Defaults to 100."
    )
    file_extensions: Optional[str] = Field(
        default=None,
        description="Comma-separated list of file extensions to filter (e.g., 'py,js,ts'). Only applies to content search."
    )


@tool("file_search", args_schema=FileSearchInput)
def file_search(
        pattern: str,
        directory: Optional[str] = None,
        search_content: bool = False,
        recursive: bool = True,
        max_results: int = 100,
        file_extensions: Optional[str] = None
) -> str:
    """
    Search for files by name pattern or content within a directory.

    Supports glob patterns for filenames and regex for content search.

    Args:
        pattern: File name pattern (glob syntax) or content search term.
                Examples: '*.py', 'test_*.json', 'config.*'
        directory: Directory to search in. Defaults to current working directory.
        search_content: If true, search file contents instead of filenames.
                       Pattern becomes a regex for content matching.
        recursive: Search recursively in subdirectories. Defaults to true.
        max_results: Maximum number of results to return. Defaults to 100.
        file_extensions: Comma-separated list of file extensions to filter
                        (e.g., 'py,js,ts'). Only applies to content search.

    Returns:
        Formatted string with search results and metadata
    """
    try:
        # Set default directory
        if directory is None:
            directory = os.getcwd()

        search_dir = Path(directory).resolve()
        logger.info(f"Searching in directory: {search_dir}, pattern: {pattern}, content: {search_content}")

        # Validate directory exists and is accessible
        if not search_dir.exists():
            return f"Error: Directory does not exist: {directory}"

        if not search_dir.is_dir():
            return f"Error: Path is not a directory: {directory}"

        # Parse file extensions filter
        extensions = None
        if file_extensions:
            extensions = [ext.strip().lstrip('.') for ext in file_extensions.split(',')]

        results = []

        if search_content:
            # Content search
            try:
                regex_pattern = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                return f"Error: Invalid regex pattern - {e}"

            results = _search_content(
                search_dir, regex_pattern, recursive, max_results, extensions
            )
        else:
            # Filename search
            results = _search_filenames(
                search_dir, pattern, recursive, max_results
            )

        # Format results
        return _format_results(
            results=results,
            search_type="content" if search_content else "filename",
            pattern=pattern,
            directory=str(search_dir),
            truncated=len(results) >= max_results
        )

    except PermissionError as e:
        return f"Error: Permission denied - {e}"
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        return f"Error: Search failed - {str(e)}"


def _search_filenames(
        search_dir: Path,
        pattern: str,
        recursive: bool,
        max_results: int
) -> List[Dict[str, Any]]:
    """Search for files by name pattern."""
    results = []

    try:
        if recursive:
            # Use rglob for recursive search
            for file_path in search_dir.rglob('*'):
                if len(results) >= max_results:
                    break

                if _should_skip_path(file_path):
                    continue

                if file_path.is_file() and file_path.match(pattern):
                    results.append({
                        "path": str(file_path),
                        "name": file_path.name,
                        "size": file_path.stat().st_size,
                        "type": "file"
                    })
        else:
            # Non-recursive search
            for file_path in search_dir.glob('*'):
                if len(results) >= max_results:
                    break

                if file_path.is_file() and file_path.match(pattern):
                    results.append({
                        "path": str(file_path),
                        "name": file_path.name,
                        "size": file_path.stat().st_size,
                        "type": "file"
                    })
    except PermissionError:
        pass

    return results


def _search_content(
        search_dir: Path,
        pattern: re.Pattern,
        recursive: bool,
        max_results: int,
        extensions: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Search for content within files."""
    results = []

    # Get list of files to search
    files_to_search = []

    try:
        if recursive:
            for file_path in search_dir.rglob('*'):
                if _should_skip_path(file_path):
                    continue

                if file_path.is_file():
                    # Filter by extension if specified
                    if extensions:
                        if file_path.suffix.lstrip('.') not in extensions:
                            continue

                    # Skip binary files and large files
                    if _is_binary_file(file_path):
                        continue

                    files_to_search.append(file_path)
        else:
            for file_path in search_dir.glob('*'):
                if file_path.is_file():
                    if extensions:
                        if file_path.suffix.lstrip('.') not in extensions:
                            continue

                    if _is_binary_file(file_path):
                        continue

                    files_to_search.append(file_path)
    except PermissionError:
        pass

    # Search content in files
    for file_path in files_to_search:
        if len(results) >= max_results:
            break

        try:
            matches = _search_file_content(file_path, pattern)
            if matches:
                results.append({
                    "path": str(file_path),
                    "name": file_path.name,
                    "matches": matches,
                    "match_count": len(matches)
                })
        except (PermissionError, UnicodeDecodeError):
            continue

    return results


def _search_file_content(file_path: Path, pattern: re.Pattern) -> List[Dict[str, Any]]:
    """Search for pattern in a single file."""
    matches = []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                match = pattern.search(line)
                if match:
                    matches.append({
                        "line": line_num,
                        "content": line.rstrip('\n\r'),
                        "match": match.group(0)
                    })
    except Exception:
        pass

    return matches


def _should_skip_path(path: Path) -> bool:
    """Check if path should be skipped (sensitive directories)."""
    # Check if any part of the path is in sensitive directories
    for part in path.parts:
        if part in SENSITIVE_DIRS:
            return True
    return False


def _is_binary_file(file_path: Path) -> bool:
    """Check if file is likely binary."""
    # Check file extension
    binary_extensions = {
        '.pyc', '.so', '.dll', '.exe', '.bin', '.dat',
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico',
        '.pdf', '.zip', '.tar', '.gz', '.rar', '.7z',
        '.mp3', '.mp4', '.avi', '.mov', '.wav',
        '.class', '.jar', '.war', '.ear'
    }

    if file_path.suffix.lower() in binary_extensions:
        return True

    # Check file size (skip very large files)
    try:
        if file_path.stat().st_size > 10 * 1024 * 1024:  # 10MB
            return True
    except Exception:
        return True

    return False


def _format_results(
        results: List[Dict[str, Any]],
        search_type: str,
        pattern: str,
        directory: str,
        truncated: bool
) -> str:
    """Format search results into a readable string."""

    output_lines = []
    output_lines.append(f"Search Results")
    output_lines.append(f"{'=' * 60}")
    output_lines.append(f"Search Type: {search_type}")
    output_lines.append(f"Pattern: {pattern}")
    output_lines.append(f"Directory: {directory}")
    output_lines.append(f"Results Found: {len(results)}")
    if truncated:
        output_lines.append(f"Note: Results truncated to {len(results)} (max reached)")
    output_lines.append("")

    if not results:
        output_lines.append("No matching files found.")
        return "\n".join(output_lines)

    if search_type == "filename":
        # Format filename search results
        output_lines.append("Matching Files:")
        output_lines.append("-" * 40)

        for i, result in enumerate(results, 1):
            size_kb = result['size'] / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"
            output_lines.append(f"{i:3}. {result['name']} ({size_str})")
            output_lines.append(f"     Path: {result['path']}")
            output_lines.append("")
    else:
        # Format content search results
        output_lines.append("Files with Matching Content:")
        output_lines.append("-" * 40)

        for i, result in enumerate(results, 1):
            output_lines.append(f"{i:3}. {result['name']}")
            output_lines.append(f"     Path: {result['path']}")
            output_lines.append(f"     Matches: {result['match_count']}")

            # Show first 3 matches
            for match in result['matches'][:3]:
                output_lines.append(f"       Line {match['line']}: {match['content'][:100]}")
                if len(match['content']) > 100:
                    output_lines.append(f"         ...")

            if result['match_count'] > 3:
                output_lines.append(f"       ... and {result['match_count'] - 3} more matches")

            output_lines.append("")

    return "\n".join(output_lines)


if __name__ == "__main__":
    import tempfile

    print("=" * 80)
    print("Testing File Search Tool")
    print("=" * 80)

    # Create a temporary directory with test files
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)

        # Create test files
        (test_dir / "test.py").write_text("def hello():\n    print('Hello World')\n")
        (test_dir / "test.js").write_text("function hello() {\n    console.log('Hello World');\n}\n")
        (test_dir / "utils.py").write_text("def helper():\n    return 'helper'\n")
        (test_dir / "README.md").write_text("# Test Project\nThis is a test.\n")

        # Create subdirectory
        sub_dir = test_dir / "subdir"
        sub_dir.mkdir()
        (sub_dir / "nested.py").write_text("def nested():\n    pass\n")

        print(f"\nTest directory created: {test_dir}")

        # Test 1: Search for Python files by filename
        print("\n1. Testing filename search (Python files):")
        result = file_search.invoke({
            "pattern": "*.py",
            "directory": str(test_dir),
            "search_content": False,
            "recursive": True,
            "max_results": 50
        })
        print(result)

        # Test 2: Search for content
        print("\n2. Testing content search (search for 'Hello'):")
        result = file_search.invoke({
            "pattern": "Hello",
            "directory": str(test_dir),
            "search_content": True,
            "recursive": True,
            "max_results": 50
        })
        print(result)

        # Test 3: Search with file extension filter
        print("\n3. Testing content search with extension filter (only .py files):")
        result = file_search.invoke({
            "pattern": "Hello",
            "directory": str(test_dir),
            "search_content": True,
            "recursive": True,
            "max_results": 50,
            "file_extensions": "py"
        })
        print(result)

        # Test 4: Non-recursive search
        print("\n4. Testing non-recursive filename search:")
        result = file_search.invoke({
            "pattern": "*.py",
            "directory": str(test_dir),
            "search_content": False,
            "recursive": False,
            "max_results": 50
        })
        print(result)

        # Test 5: Search with regex pattern
        print("\n5. Testing content search with regex pattern:")
        result = file_search.invoke({
            "pattern": "def \\w+",
            "directory": str(test_dir),
            "search_content": True,
            "recursive": True,
            "max_results": 50
        })
        print(result)

        # Test 6: Error handling - non-existent directory
        print("\n6. Testing error handling (non-existent directory):")
        result = file_search.invoke({
            "pattern": "*.py",
            "directory": "/nonexistent/directory",
            "search_content": False
        })
        print(result)

        # Test 7: Invalid regex pattern
        print("\n7. Testing error handling (invalid regex):")
        result = file_search.invoke({
            "pattern": "[invalid",
            "directory": str(test_dir),
            "search_content": True
        })
        print(result)
