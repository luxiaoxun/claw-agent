"""
Edit Tool - File editing with string replacement

Performs exact string replacements in files with multiple fallback strategies:
- Simple exact match
- Line-trimmed matching
- Block anchor matching (for multi-line blocks)
- Whitespace normalized matching
- Indentation flexible matching
- Escape normalized matching
- Context-aware matching

Ported from original edit.ts implementation.
"""

import os
import re
from pathlib import Path
from typing import Optional, Generator, List
from difflib import unified_diff

from langchain.tools import tool
from pydantic import BaseModel, Field

from config.logging_config import get_logger

logger = get_logger(__name__)

# Constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max file size for safety

# Similarity thresholds for block anchor fallback matching
SINGLE_CANDIDATE_SIMILARITY_THRESHOLD = 0.0
MULTIPLE_CANDIDATES_SIMILARITY_THRESHOLD = 0.3


class EditInput(BaseModel):
    """Input parameters for edit tool"""
    filePath: str = Field(
        description="The absolute path to the file to modify"
    )
    oldString: str = Field(
        description="The text to replace (must be found in the file)"
    )
    newString: str = Field(
        description="The text to replace it with (must be different from oldString)"
    )
    replaceAll: bool = Field(
        default=False,
        description="Replace all occurrences of oldString (default false)"
    )


def levenshtein(a: str, b: str) -> int:
    """
    Calculate Levenshtein distance between two strings

    Args:
        a: First string
        b: Second string

    Returns:
        Edit distance
    """
    if not a or not b:
        return max(len(a), len(b))

    # Use dynamic programming
    m, n = len(a), len(b)
    matrix = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        matrix[i][0] = i
    for j in range(n + 1):
        matrix[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            matrix[i][j] = min(
                matrix[i - 1][j] + 1,  # deletion
                matrix[i][j - 1] + 1,  # insertion
                matrix[i - 1][j - 1] + cost  # substitution
            )

    return matrix[m][n]


def normalize_line_endings(text: str) -> str:
    """Normalize line endings to Unix style"""
    return text.replace("\r\n", "\n")


def generate_diff(filepath: str, old_content: str, new_content: str) -> str:
    """Generate unified diff between old and new content"""
    old_lines = normalize_line_endings(old_content).splitlines(keepends=True)
    new_lines = normalize_line_endings(new_content).splitlines(keepends=True)

    diff_lines = list(unified_diff(
        old_lines,
        new_lines,
        fromfile=filepath,
        tofile=filepath,
        lineterm=""
    ))

    return "".join(diff_lines)


def trim_diff(diff: str) -> str:
    """Trim indentation from diff content lines"""
    if not diff:
        return diff

    lines = diff.split("\n")

    content_lines = [
        line for line in lines
        if (line.startswith("+") or line.startswith("-") or line.startswith(" "))
           and not line.startswith("---")
           and not line.startswith("+++")
    ]

    if not content_lines:
        return diff

    min_indent = float('inf')
    for line in content_lines:
        content = line[1:]
        if content.strip():
            indent = len(content) - len(content.lstrip())
            min_indent = min(min_indent, indent)

    if min_indent == float('inf') or min_indent == 0:
        return diff

    trimmed_lines = []
    for line in lines:
        if (line.startswith("+") or line.startswith("-") or line.startswith(" ")) \
                and not line.startswith("---") and not line.startswith("+++"):
            prefix = line[0]
            content = line[1:]
            trimmed_lines.append(prefix + content[int(min_indent):])
        else:
            trimmed_lines.append(line)

    return "\n".join(trimmed_lines)


def _safe_relpath(path: str, start: Optional[str]) -> str:
    """Return a relative path when possible, otherwise keep the absolute path."""
    if not start:
        return path
    try:
        return os.path.relpath(path, start)
    except ValueError:
        return path


# Replacer type: Generator that yields potential matches
def simple_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Simple exact match replacer"""
    yield find


def line_trimmed_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Match with trimmed line comparison"""
    original_lines = content.split("\n")
    search_lines = find.split("\n")

    if search_lines and search_lines[-1] == "":
        search_lines.pop()

    for i in range(len(original_lines) - len(search_lines) + 1):
        matches = True

        for j in range(len(search_lines)):
            original_trimmed = original_lines[i + j].strip()
            search_trimmed = search_lines[j].strip()

            if original_trimmed != search_trimmed:
                matches = False
                break

        if matches:
            # Calculate match indices
            match_start = sum(len(original_lines[k]) + 1 for k in range(i))
            match_end = match_start
            for k in range(len(search_lines)):
                match_end += len(original_lines[i + k])
                if k < len(search_lines) - 1:
                    match_end += 1

            yield content[match_start:match_end]


def block_anchor_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Match using first/last lines as anchors"""
    original_lines = content.split("\n")
    search_lines = find.split("\n")

    if len(search_lines) < 3:
        return

    if search_lines and search_lines[-1] == "":
        search_lines.pop()

    first_line = search_lines[0].strip()
    last_line = search_lines[-1].strip()
    search_block_size = len(search_lines)

    # Collect candidate positions
    candidates = []
    for i in range(len(original_lines)):
        if original_lines[i].strip() != first_line:
            continue

        for j in range(i + 2, len(original_lines)):
            if original_lines[j].strip() == last_line:
                candidates.append({"start": i, "end": j})
                break

    if not candidates:
        return

    # Single candidate: use relaxed threshold
    if len(candidates) == 1:
        start, end = candidates[0]["start"], candidates[0]["end"]
        actual_size = end - start + 1

        similarity = 0.0
        lines_to_check = min(search_block_size - 2, actual_size - 2)

        if lines_to_check > 0:
            for j in range(1, min(search_block_size - 1, actual_size - 1)):
                orig_line = original_lines[start + j].strip()
                search_line = search_lines[j].strip()
                max_len = max(len(orig_line), len(search_line))
                if max_len == 0:
                    continue
                distance = levenshtein(orig_line, search_line)
                similarity += (1 - distance / max_len) / lines_to_check
                if similarity >= SINGLE_CANDIDATE_SIMILARITY_THRESHOLD:
                    break
        else:
            similarity = 1.0

        if similarity >= SINGLE_CANDIDATE_SIMILARITY_THRESHOLD:
            match_start = sum(len(original_lines[k]) + 1 for k in range(start))
            match_end = match_start
            for k in range(start, end + 1):
                match_end += len(original_lines[k])
                if k < end:
                    match_end += 1
            yield content[match_start:match_end]
        return

    # Multiple candidates: find best match
    best_match = None
    max_similarity = -1

    for candidate in candidates:
        start, end = candidate["start"], candidate["end"]
        actual_size = end - start + 1

        similarity = 0.0
        lines_to_check = min(search_block_size - 2, actual_size - 2)

        if lines_to_check > 0:
            for j in range(1, min(search_block_size - 1, actual_size - 1)):
                orig_line = original_lines[start + j].strip()
                search_line = search_lines[j].strip()
                max_len = max(len(orig_line), len(search_line))
                if max_len == 0:
                    continue
                distance = levenshtein(orig_line, search_line)
                similarity += 1 - distance / max_len
            similarity /= lines_to_check
        else:
            similarity = 1.0

        if similarity > max_similarity:
            max_similarity = similarity
            best_match = candidate

    if max_similarity >= MULTIPLE_CANDIDATES_SIMILARITY_THRESHOLD and best_match:
        start, end = best_match["start"], best_match["end"]
        match_start = sum(len(original_lines[k]) + 1 for k in range(start))
        match_end = match_start
        for k in range(start, end + 1):
            match_end += len(original_lines[k])
            if k < end:
                match_end += 1
        yield content[match_start:match_end]


def whitespace_normalized_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Match with normalized whitespace"""

    def normalize(text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip()

    normalized_find = normalize(find)
    lines = content.split("\n")

    # Single line matches
    for line in lines:
        if normalize(line) == normalized_find:
            yield line
        else:
            normalized_line = normalize(line)
            if normalized_find in normalized_line:
                words = find.strip().split()
                if words:
                    pattern = r'\s+'.join(re.escape(w) for w in words)
                    try:
                        match = re.search(pattern, line)
                        if match:
                            yield match.group(0)
                    except re.error:
                        pass

    # Multi-line matches
    find_lines = find.split("\n")
    if len(find_lines) > 1:
        for i in range(len(lines) - len(find_lines) + 1):
            block = lines[i:i + len(find_lines)]
            if normalize("\n".join(block)) == normalized_find:
                yield "\n".join(block)


def indentation_flexible_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Match with flexible indentation"""

    def remove_indentation(text: str) -> str:
        text_lines = text.split("\n")
        non_empty = [l for l in text_lines if l.strip()]
        if not non_empty:
            return text

        min_indent = min(
            len(l) - len(l.lstrip())
            for l in non_empty
        )

        return "\n".join(
            l if not l.strip() else l[min_indent:]
            for l in text_lines
        )

    normalized_find = remove_indentation(find)
    content_lines = content.split("\n")
    find_lines = find.split("\n")

    for i in range(len(content_lines) - len(find_lines) + 1):
        block = "\n".join(content_lines[i:i + len(find_lines)])
        if remove_indentation(block) == normalized_find:
            yield block


def trimmed_boundary_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Match with trimmed boundaries"""
    trimmed_find = find.strip()

    if trimmed_find == find:
        return

    if trimmed_find in content:
        yield trimmed_find

    lines = content.split("\n")
    find_lines = find.split("\n")

    for i in range(len(lines) - len(find_lines) + 1):
        block = "\n".join(lines[i:i + len(find_lines)])
        if block.strip() == trimmed_find:
            yield block


def multi_occurrence_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Yield all exact matches"""
    start = 0
    while True:
        idx = content.find(find, start)
        if idx == -1:
            break
        yield find
        start = idx + len(find)


def replace(content: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """
    Replace old_string with new_string in content

    Uses multiple replacer strategies to find the best match.

    Args:
        content: File content
        old_string: String to find
        new_string: Replacement string
        replace_all: Replace all occurrences

    Returns:
        Modified content

    Raises:
        ValueError: If old_string not found or ambiguous
    """
    if old_string == new_string:
        raise ValueError("oldString and newString must be different")

    not_found = True

    # Try each replacer strategy
    replacers = [
        simple_replacer,
        line_trimmed_replacer,
        block_anchor_replacer,
        whitespace_normalized_replacer,
        indentation_flexible_replacer,
        trimmed_boundary_replacer,
        multi_occurrence_replacer,
    ]

    for replacer in replacers:
        for search in replacer(content, old_string):
            idx = content.find(search)
            if idx == -1:
                continue

            not_found = False

            if replace_all:
                return content.replace(search, new_string)

            # Check for multiple occurrences
            last_idx = content.rfind(search)
            if idx != last_idx:
                continue

            return content[:idx] + new_string + content[idx + len(search):]

    if not_found:
        raise ValueError("oldString not found in content")

    raise ValueError(
        "Found multiple matches for oldString. Provide more surrounding lines "
        "in oldString to identify the correct match."
    )


def _resolve_absolute_path(filePath: str) -> str:
    """Resolve absolute path"""
    if os.path.isabs(filePath):
        return filePath
    # Use current working directory as base
    return os.path.abspath(filePath)


@tool("file_edit", args_schema=EditInput)
def file_edit(
        filePath: str,
        oldString: str,
        newString: str,
        replaceAll: bool = False,
) -> str:
    """
    Performs exact string replacements in files.

    Usage:
    - You must use your `Read` tool at least once before editing a file. CRITICAL: After each successful edit, the file content changes. You MUST re-read the file with `Read` before making any further edits to that file, otherwise oldString will not match the updated content and the edit will fail.
    - The edit will FAIL if `oldString` is not found in the file.
    - The edit will FAIL if `oldString` is found multiple times in the file. Either provide a larger string with more surrounding context to make it unique or use `replaceAll` to change every instance of `oldString`.
    - Use `replaceAll` for replacing and renaming strings across the file.

    Args:
        filePath: The absolute path to the file to modify
        oldString: The text to replace (must be found in the file)
        newString: The text to replace it with (must be different from oldString)
        replaceAll: Replace all occurrences of oldString (default false)
    """
    # Validate inputs
    if not filePath:
        return "Error: filePath is required"

    if oldString == newString:
        return "Error: oldString and newString must be different"

    # Resolve absolute path
    filepath = _resolve_absolute_path(filePath)
    logger.info(f"Editing file: {filepath}")

    # Handle empty oldString (create new file)
    if oldString == "":
        diff = trim_diff(generate_diff(filepath, "", newString))
        logger.info(f"Creating new file: {filepath}")

        # Create parent directory if needed
        parent_dir = os.path.dirname(filepath)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(newString)
        except Exception as e:
            return f"Error: Failed to write file - {str(e)}"

        result = "Successfully created file.\n"
        if diff:
            result += f"\nChanges:\n{diff}"
        else:
            result += "Content written successfully."

        return result

    # Check if file exists
    if not os.path.exists(filepath):
        return f"Error: File {filepath} not found"

    if os.path.isdir(filepath):
        return f"Error: Path is a directory, not a file: {filepath}"

    # Check file size
    try:
        file_size = os.path.getsize(filepath)
        if file_size > MAX_FILE_SIZE:
            return f"Error: File too large - {filepath} exceeds maximum size limit ({MAX_FILE_SIZE} bytes)"
    except Exception as e:
        return f"Error: Failed to check file size - {str(e)}"

    # Read existing file
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content_old = f.read()
    except Exception as e:
        return f"Error: Failed to read file - {str(e)}"

    # Perform replacement
    try:
        content_new = replace(content_old, oldString, newString, replaceAll)
    except ValueError as e:
        return f"Error: {str(e)}"

    # Generate diff
    diff = trim_diff(generate_diff(
        filepath,
        normalize_line_endings(content_old),
        normalize_line_endings(content_new)
    ))

    # Write file
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content_new)
    except Exception as e:
        return f"Error: Failed to write file - {str(e)}"

    # Calculate additions and deletions
    old_lines = set(content_old.split("\n"))
    new_lines = set(content_new.split("\n"))
    additions = sum(1 for line in new_lines if line not in old_lines)
    deletions = sum(1 for line in old_lines if line not in new_lines)

    # Build result message
    result = "Edit applied successfully.\n"
    if diff:
        result += f"\nChanges:\n{diff}\n"
    else:
        result += "Content updated successfully.\n"

    result += f"\nSummary: {additions} additions, {deletions} deletions"

    logger.info(f"Successfully edited file: {filepath}")
    return result


if __name__ == "__main__":
    import tempfile

    print("=" * 80)
    print("Testing Edit Tool")
    print("=" * 80)

    # Create a temporary test file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        test_file = f.name
        f.write("Hello World\nThis is a test file.\nHello again!")

    print(f"\nTest file created: {test_file}")

    # Test 1: Simple replacement
    print("\n1. Testing simple replacement:")
    result = file_edit.invoke({
        "filePath": test_file,
        "oldString": "Hello World",
        "newString": "Hello Universe"
    })
    print(result)

    # Test 2: Read the file to verify
    print("\n2. Verifying file content:")
    with open(test_file, 'r') as f:
        print(f.read())

    # Test 3: Replace all occurrences
    print("\n3. Testing replace all:")
    result = file_edit.invoke({
        "filePath": test_file,
        "oldString": "Hello",
        "newString": "Hi",
        "replaceAll": True
    })
    print(result)

    # Test 4: Verify final content
    print("\n4. Final file content:")
    with open(test_file, 'r') as f:
        print(f.read())

    # Test 5: Error handling - oldString not found
    print("\n5. Testing error handling (not found):")
    result = file_edit.invoke({
        "filePath": test_file,
        "oldString": "Not Found",
        "newString": "Something"
    })
    print(result)

    # Clean up
    os.unlink(test_file)
    print(f"\nTest file deleted: {test_file}")
