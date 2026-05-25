"""
CSV Parser Tool - Parse and process CSV data

Supports reading, writing, and basic transformations of CSV files.
Uses Python's built-in csv module with optional pandas for advanced operations.
"""

import csv
import io
import json
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from langchain.tools import tool
from pydantic import BaseModel, Field

from soma.config.logging_config import get_logger
from soma.config.settings import WORKSPACE_DIR

logger = get_logger(__name__)

MAX_ROWS = 10000  # Maximum rows to return


class CsvReadInput(BaseModel):
    """Input parameters for CSV read operation"""
    path: str = Field(
        description="File path to CSV file (absolute or relative to workspace)"
    )
    encoding: Optional[str] = Field(
        default="utf-8",
        description="File encoding (utf-8, gbk, latin-1, etc.)"
    )
    delimiter: Optional[str] = Field(
        default=None,
        description="CSV delimiter (comma, tab, semicolon, etc.). Auto-detected if not specified."
    )
    has_header: bool = Field(
        default=True,
        description="Whether the CSV has a header row"
    )
    max_rows: int = Field(
        default=1000,
        description="Maximum number of data rows to return (excluding header)"
    )


class CsvWriteInput(BaseModel):
    """Input parameters for CSV write operation"""
    path: str = Field(
        description="File path to write CSV (absolute or relative to workspace/outputs)"
    )
    data: Union[List[Dict[str, Any]], str] = Field(
        description="Data to write: either a JSON array of objects or a CSV string"
    )
    headers: Optional[List[str]] = Field(
        default=None,
        description="Column headers (required if data is a 2D array without header row)"
    )
    encoding: str = Field(
        default="utf-8",
        description="File encoding"
    )
    delimiter: str = Field(
        default=",",
        description="CSV delimiter"
    )
    overwrite: bool = Field(
        default=True,
        description="Whether to overwrite existing file"
    )


class CsvFilterInput(BaseModel):
    """Input parameters for CSV filtering operation"""
    path: str = Field(
        description="File path to CSV file"
    )
    filter_expr: str = Field(
        description="Filter expression in format: column OPERATOR value (e.g., 'age > 18', 'name == John', 'city contains Bei')"
    )
    encoding: Optional[str] = Field(
        default="utf-8",
        description="File encoding"
    )
    delimiter: Optional[str] = Field(
        default=None,
        description="CSV delimiter"
    )
    has_header: bool = Field(
        default=True,
        description="Whether the CSV has a header row"
    )
    output_path: Optional[str] = Field(
        default=None,
        description="Optional output path for filtered results"
    )


def _resolve_path(path: str, workspace_dir: Path, create_output: bool = False) -> Path:
    """Resolve file path"""
    path_obj = Path(path)

    if path_obj.is_absolute():
        return path_obj

    if create_output:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        return workspace_dir / "outputs" / today / path
    return workspace_dir / path


def _detect_delimiter(content: str) -> str:
    """Auto-detect CSV delimiter"""
    try:
        dialect = csv.Sniffer().sniff(content[:8192], delimiters=',;\t|')
        return dialect.delimiter
    except csv.Error:
        return ','


def _parse_filter_expr(expr: str) -> tuple:
    """
    Parse filter expression into (column, operator, value)

    Supported operators: ==, !=, >, <, >=, <=, contains, startswith, endswith
    """
    expr = expr.strip()

    # Parse operators
    operators = [
        ('==', '=='),
        ('!=', '!='),
        ('>=', '>='),
        ('<=', '<='),
        ('>', '>'),
        ('<', '<'),
    ]

    for op, op_str in operators:
        if op in expr:
            parts = expr.split(op, 1)
            column = parts[0].strip()
            value = parts[1].strip().strip('"\'')
            return column, op_str, value

    # String operators
    for op_str in [' contains ', ' startswith ', ' endswith ']:
        if op_str in expr:
            parts = expr.split(op_str, 1)
            column = parts[0].strip()
            value = parts[1].strip().strip('"\'')
            return column, op_str.strip(), value

    raise ValueError(f"Invalid filter expression: {expr}")


def _match_filter(row: Dict[str, Any], column: str, operator: str, value: str) -> bool:
    """Apply filter to a single row"""
    if column not in row:
        return False

    cell_value = str(row[column])

    if operator == '==':
        return cell_value == value
    elif operator == '!=':
        return cell_value != value
    elif operator == '>':
        try:
            return float(cell_value) > float(value)
        except ValueError:
            return cell_value > value
    elif operator == '<':
        try:
            return float(cell_value) < float(value)
        except ValueError:
            return cell_value < value
    elif operator == '>=':
        try:
            return float(cell_value) >= float(value)
        except ValueError:
            return cell_value >= value
    elif operator == '<=':
        try:
            return float(cell_value) <= float(value)
        except ValueError:
            return cell_value <= value
    elif operator == 'contains':
        return value.lower() in cell_value.lower()
    elif operator == 'startswith':
        return cell_value.lower().startswith(value.lower())
    elif operator == 'endswith':
        return cell_value.lower().endswith(value.lower())

    return False


@tool("csv_read", args_schema=CsvReadInput)
def csv_read(
        path: str,
        encoding: Optional[str] = "utf-8",
        delimiter: Optional[str] = None,
        has_header: bool = True,
        max_rows: int = 1000,
) -> str:
    """
    Read and parse a CSV file, returning structured data.

    Usage:
    - Automatically detects delimiter if not specified
    - Returns JSON array of objects (one per row)
    - Large files are truncated to max_rows

    Args:
        path: File path to CSV file
        encoding: File encoding (utf-8, gbk, latin-1, etc.)
        delimiter: CSV delimiter (auto-detected if not specified)
        has_header: Whether the CSV has a header row
        max_rows: Maximum number of data rows to return
    """
    workspace_dir = Path(WORKSPACE_DIR)

    try:
        file_path = _resolve_path(path, workspace_dir)

        if not file_path.exists():
            return f"Error: File not found - {path}"

        logger.info(f"Reading CSV file: {file_path}")

        # Read file content
        encodings = [encoding, 'utf-8', 'gbk', 'latin-1'] if encoding not in ['utf-8', 'gbk', 'latin-1'] else [encoding]
        content = None
        for enc in encodings:
            try:
                content = file_path.read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            return f"Error: Failed to read file with available encodings"

        # Detect delimiter
        if delimiter is None:
            delimiter = _detect_delimiter(content)

        # Parse CSV
        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        rows = list(reader)

        if not rows:
            return "Error: CSV file is empty"

        result_lines = [
            "=" * 60,
            "CSV Read",
            "=" * 60,
            f"File: {file_path}",
            f"Encoding: {encodings[0]}",
            f"Delimiter: '{delimiter}'",
            f"Total rows (including header): {len(rows)}",
            f"Has header: {has_header}",
        ]

        # Process rows
        if has_header and len(rows) > 0:
            headers = rows[0]
            data_rows = rows[1:]
        else:
            # Generate headers like col_0, col_1, ...
            headers = [f"col_{i}" for i in range(len(rows[0]))]
            data_rows = rows

        # Limit rows
        if len(data_rows) > max_rows:
            result_lines.append(f"Note: Truncated to {max_rows} rows (file has {len(data_rows)} data rows)")
            data_rows = data_rows[:max_rows]

        # Build JSON output
        data = []
        for row in data_rows:
            row_dict = {}
            for i, header in enumerate(headers):
                if i < len(row):
                    row_dict[header] = row[i].strip()
                else:
                    row_dict[header] = ""
            data.append(row_dict)

        result_lines.append("")
        result_lines.append(f"Data ({len(data)} rows):")
        result_lines.append(json.dumps(data, ensure_ascii=False, indent=2))

        logger.info(f"CSV read completed - {len(data)} rows")
        return "\n".join(result_lines)

    except Exception as e:
        logger.error(f"CSV read error: {e}")
        return f"Error reading CSV: {str(e)}"


@tool("csv_write", args_schema=CsvWriteInput)
def csv_write(
        path: str,
        data: Union[List[Dict[str, Any]], str],
        headers: Optional[List[str]] = None,
        encoding: str = "utf-8",
        delimiter: str = ",",
        overwrite: bool = True,
) -> str:
    """
    Write data to a CSV file.

    Usage:
    - Data can be a JSON array of objects or a CSV string
    - If data is array of objects, keys become headers
    - If data is 2D array, provide headers parameter

    Args:
        path: File path to write CSV
        data: Data to write (JSON array or CSV string)
        headers: Column headers (required if data is 2D array without header row)
        encoding: File encoding
        delimiter: CSV delimiter
        overwrite: Whether to overwrite existing file
    """
    workspace_dir = Path(WORKSPACE_DIR)

    try:
        file_path = _resolve_path(path, workspace_dir, create_output=True)

        # Check if exists
        if file_path.exists() and not overwrite:
            return f"Error: File already exists - {path}"

        logger.info(f"Writing CSV file: {file_path}")

        # Create parent directory
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Parse input data
        rows_data: List[List[str]] = []

        if isinstance(data, str):
            # Parse as CSV string
            reader = csv.reader(io.StringIO(data), delimiter=delimiter)
            rows_data = list(reader)

            if headers and rows_data and len(rows_data) > 0:
                # Check if first row is header
                if len(rows_data[0]) == len(headers):
                    # Insert headers at beginning
                    rows_data.insert(0, headers)

        elif isinstance(data, list):
            if not data:
                return "Error: Data array is empty"

            # Convert objects to rows
            if isinstance(data[0], dict):
                # Get headers from keys
                if headers is None:
                    headers = list(data[0].keys())

                # Write header
                rows_data.append(headers)

                # Write data rows
                for item in data:
                    row = [str(item.get(h, "")) for h in headers]
                    rows_data.append(row)
            else:
                # 2D array
                if headers:
                    rows_data.append(headers)
                rows_data.extend([[str(cell) for cell in row] for row in data])
        else:
            return f"Error: Unsupported data type - {type(data)}"

        # Write to file
        with open(file_path, 'w', encoding=encoding, newline='') as f:
            writer = csv.writer(f, delimiter=delimiter)
            writer.writerows(rows_data)

        result_lines = [
            "=" * 60,
            "CSV Write",
            "=" * 60,
            f"File: {file_path}",
            f"Encoding: {encoding}",
            f"Delimiter: '{delimiter}'",
            f"Rows written: {len(rows_data)}",
        ]

        if headers:
            result_lines.append(f"Columns: {len(headers)}")
            result_lines.append(f"Headers: {headers}")

        logger.info(f"CSV write completed - {len(rows_data)} rows")
        return "\n".join(result_lines)

    except Exception as e:
        logger.error(f"CSV write error: {e}")
        return f"Error writing CSV: {str(e)}"


@tool("csv_filter", args_schema=CsvFilterInput)
def csv_filter(
        path: str,
        filter_expr: str,
        encoding: Optional[str] = "utf-8",
        delimiter: Optional[str] = None,
        has_header: bool = True,
        output_path: Optional[str] = None,
) -> str:
    """
    Filter CSV rows based on a condition expression.

    Filter expressions:
    - Comparison: age > 18, score >= 80, name == John
    - String: city contains Bei, url startswith https, email endswith .com

    Args:
        path: File path to CSV file
        filter_expr: Filter expression (e.g., 'age > 18', 'name contains John')
        encoding: File encoding
        delimiter: CSV delimiter (auto-detected if not specified)
        has_header: Whether the CSV has a header row
        output_path: Optional path to save filtered results
    """
    workspace_dir = Path(WORKSPACE_DIR)

    try:
        file_path = _resolve_path(path, workspace_dir)

        if not file_path.exists():
            return f"Error: File not found - {path}"

        logger.info(f"Filtering CSV file: {file_path}, filter: {filter_expr}")

        # Read file content
        encodings = [encoding, 'utf-8', 'gbk', 'latin-1'] if encoding not in ['utf-8', 'gbk', 'latin-1'] else [encoding]
        content = None
        for enc in encodings:
            try:
                content = file_path.read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            return f"Error: Failed to read file with available encodings"

        # Detect delimiter
        if delimiter is None:
            delimiter = _detect_delimiter(content)

        # Parse CSV
        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        rows = list(reader)

        if not rows:
            return "Error: CSV file is empty"

        # Parse filter expression
        column, operator, value = _parse_filter_expr(filter_expr)

        # Get headers and data rows
        if has_header and len(rows) > 0:
            headers = rows[0]
            data_rows = rows[1:]
        else:
            headers = [f"col_{i}" for i in range(len(rows[0]))]
            data_rows = rows

        # Filter rows
        filtered_rows = []
        matched_count = 0

        for row in data_rows:
            row_dict = {}
            for i, header in enumerate(headers):
                if i < len(row):
                    row_dict[header] = row[i].strip()
                else:
                    row_dict[header] = ""

            if _match_filter(row_dict, column, operator, value):
                filtered_rows.append(row)
                matched_count += 1

        result_lines = [
            "=" * 60,
            "CSV Filter",
            "=" * 60,
            f"File: {file_path}",
            f"Filter: {column} {operator} {value}",
            f"Total rows: {len(data_rows)}",
            f"Matched rows: {matched_count}",
        ]

        if output_path:
            # Write filtered results
            output_file_path = _resolve_path(output_path, workspace_dir, create_output=True)
            output_file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, delimiter=delimiter)
                if has_header:
                    writer.writerow(headers)
                writer.writerows(filtered_rows)

            result_lines.append(f"Output: {output_file_path}")

        # Add filtered data preview
        if filtered_rows:
            result_lines.append("")
            result_lines.append("Filtered data preview (first 10 rows):")
            preview_rows = filtered_rows[:10]

            if has_header:
                result_lines.append(f"Headers: {headers}")

            for i, row in enumerate(preview_rows, 1):
                result_lines.append(f"Row {i}: {row}")

            if len(filtered_rows) > 10:
                result_lines.append(f"... and {len(filtered_rows) - 10} more rows")

        logger.info(f"CSV filter completed - matched {matched_count}/{len(data_rows)} rows")
        return "\n".join(result_lines)

    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        logger.error(f"CSV filter error: {e}")
        return f"Error filtering CSV: {str(e)}"


if __name__ == "__main__":
    import tempfile

    print("=" * 80)
    print("Testing CSV Parser Tool")
    print("=" * 80)

    # Create test CSV
    test_csv = """name,age,city,score
Alice,25,Beijing,95.5
Bob,30,Shanghai,88.0
Charlie,22,Beijing,92.0
David,35,Guangzhou,78.5
Eve,28,Shenzhen,91.0"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write(test_csv)
        test_file = f.name

    print(f"\nTest file created: {test_file}")
    print(f"Content:\n{test_csv}")

    # Test 1: Read CSV
    print("\n1. Testing CSV read:")
    result = csv_read.invoke({
        "path": test_file,
        "encoding": "utf-8",
        "max_rows": 10
    })
    print(result[:1000])

    # Test 2: Filter CSV
    print("\n2. Testing CSV filter (age > 25):")
    result = csv_filter.invoke({
        "path": test_file,
        "filter_expr": "age > 25",
        "encoding": "utf-8"
    })
    print(result)

    # Test 3: Filter with string contains
    print("\n3. Testing CSV filter (city contains Bei):")
    result = csv_filter.invoke({
        "path": test_file,
        "filter_expr": "city contains Bei",
        "encoding": "utf-8"
    })
    print(result)

    # Test 4: Write CSV
    print("\n4. Testing CSV write:")
    new_data = [
        {"name": "Frank", "age": 40, "city": "Chengdu", "score": 85.0},
        {"name": "Grace", "age": 32, "city": "Wuhan", "score": 89.5}
    ]
    result = csv_write.invoke({
        "path": "test_output.csv",
        "data": new_data
    })
    print(result)

    import os

    os.unlink(test_file)
    print(f"\nTest file deleted: {test_file}")
