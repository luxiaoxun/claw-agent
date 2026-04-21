"""
Doc Parser Tool - Convert PDF/Word documents to Markdown

Parses PDF, DOCX, or DOC files into Markdown and writes the result to an .md file.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import importlib
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Callable, Optional

from defusedxml import ElementTree as DefusedET
from langchain.tools import tool
from pydantic import BaseModel, Field

from config.logging_config import get_logger

logger = get_logger(__name__)

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".doc"}
WORD_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
DOCX_SOFT_BREAK_TOKEN = "<<CLAW_AGENT_DOCX_SOFT_BREAK>>"


class DocParserInput(BaseModel):
    """Input parameters for document parser tool"""
    input_path: str = Field(
        description="Absolute or relative path to the source PDF / DOCX / DOC file."
    )
    output_path: Optional[str] = Field(
        default=None,
        description="Optional output markdown path. Absolute paths are used directly. Relative paths are resolved inside the workspace directory."
    )
    overwrite: bool = Field(
        default=True,
        description="Whether to overwrite an existing markdown output file."
    )


def _normalize_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    fenced_block_pattern = re.compile(r"(^```.*?^```[ \t]*$)", re.MULTILINE | re.DOTALL)
    parts = fenced_block_pattern.split(text)
    normalized_parts: list[str] = []

    for part in parts:
        if not part:
            continue
        if fenced_block_pattern.fullmatch(part):
            normalized_parts.append(_normalize_fenced_block(part))
        else:
            normalized_parts.append(_normalize_text_segment(part))

    result = "".join(normalized_parts).strip()
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.replace(DOCX_SOFT_BREAK_TOKEN, "\n")


def _normalize_text_segment(text: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", text)

    paragraphs = re.split(r"\n\s*\n+", text)
    normalized: list[str] = []
    for paragraph in paragraphs:
        raw_lines = [line.rstrip() for line in paragraph.splitlines() if line.strip()]
        if not raw_lines:
            continue
        if any(_looks_like_markdown(line) for line in raw_lines):
            normalized.append("\n".join(raw_lines))
        else:
            normalized.append(" ".join(line.strip() for line in raw_lines))

    if not normalized:
        return ""
    return "\n\n".join(normalized) + "\n\n"


def _normalize_fenced_block(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return ""
    return "\n".join(lines) + "\n\n"


def _looks_like_markdown(line: str) -> bool:
    stripped = line.lstrip()
    markdown_prefixes = ("#", "-", "*", "+", ">", "|", "```")
    ordered_list = re.match(r"^\d+\.\s", stripped)
    return stripped.startswith(markdown_prefixes) or ordered_list is not None


def _safe_xml_fromstring(payload: bytes | str) -> ET.Element:
    return DefusedET.fromstring(payload)


def _sanitize_stem(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._")
    return stem or "document"


def _default_output_path(input_file: Path, workspace_dir: Path) -> Path:
    """Create default output path in workspace outputs directory"""
    today = dt.date.today().isoformat()
    output_dir = workspace_dir / "outputs" / today
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = input_file.suffix.lower().lstrip(".") or "file"
    return output_dir / f"{_sanitize_stem(input_file)}_{suffix}.md"


def _resolve_input_path(input_path: str, workspace_dir: Path) -> Path:
    """Resolve input file path"""
    path = Path(input_path).expanduser()
    if path.is_absolute():
        return path.resolve()

    # Try relative to workspace
    workspace_path = workspace_dir / input_path
    if workspace_path.exists():
        return workspace_path.resolve()

    # Fall back to current directory
    return path.resolve()


def _resolve_output_path(input_file: Path, output_path: Optional[str], workspace_dir: Path) -> Path:
    """Resolve output file path"""
    if not output_path:
        return _default_output_path(input_file, workspace_dir)

    path = Path(output_path).expanduser()
    if not path.is_absolute():
        path = workspace_dir / output_path
    if path.suffix.lower() != ".md":
        path = path.with_suffix(".md")
    return path.resolve()


def _extract_with_markitdown(file_path: Path) -> str:
    markitdown = importlib.import_module("markitdown")
    markitdown_cls = getattr(markitdown, "MarkItDown")

    result = markitdown_cls().convert(str(file_path))
    return _normalize_markdown(result.text_content or "")


def _extract_pdf_with_pymupdf(file_path: Path) -> str:
    fitz = importlib.import_module("fitz")

    document = fitz.open(file_path)
    try:
        text_parts = [page.get_text() for page in document]
    finally:
        document.close()
    return _normalize_markdown("\n\n".join(text_parts))


def _extract_pdf_with_pypdf(file_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(file_path))
    text_parts = [page.extract_text() or "" for page in reader.pages]
    return _normalize_markdown("\n\n".join(text_parts))


def _word_tag(name: str) -> str:
    return f"{{{WORD_NAMESPACE['w']}}}{name}"


def _docx_styles(archive: zipfile.ZipFile) -> dict[str, str]:
    try:
        styles_xml = archive.read("word/styles.xml")
    except KeyError:
        return {}

    root = _safe_xml_fromstring(styles_xml)
    styles: dict[str, str] = {}
    for style in root.findall("w:style", WORD_NAMESPACE):
        style_id = style.get(_word_tag("styleId")) or style.get("styleId")
        name = style.find("w:name", WORD_NAMESPACE)
        style_name = ""
        if name is not None:
            style_name = name.get(_word_tag("val")) or name.get("val") or ""
        if style_id:
            styles[style_id] = style_name
    return styles


def _format_docx_text(text: str, style_name: str) -> str:
    if not text:
        return ""

    style_name = style_name.lower()
    if "heading 1" in style_name or style_name == "title":
        return f"# {text}"
    if "heading 2" in style_name:
        return f"## {text}"
    if "heading 3" in style_name:
        return f"### {text}"
    if "heading 4" in style_name:
        return f"#### {text}"
    if "heading 5" in style_name:
        return f"##### {text}"
    if "heading 6" in style_name:
        return f"###### {text}"
    if "list bullet" in style_name:
        return f"- {text}"
    if "list number" in style_name:
        return f"1. {text}"
    return text


def _run_text(run: ET.Element) -> str:
    properties = run.find("w:rPr", WORD_NAMESPACE)
    text_parts: list[str] = []
    for node in run.iter():
        if node is run:
            continue
        if node.tag == _word_tag("t"):
            text = node.text or ""
            if properties is not None and text:
                if properties.find("w:b", WORD_NAMESPACE) is not None:
                    text = f"**{text}**"
                if properties.find("w:i", WORD_NAMESPACE) is not None:
                    text = f"*{text}*"
                if properties.find("w:u", WORD_NAMESPACE) is not None:
                    text = f"__{text}__"
            text_parts.append(text)
        elif node.tag == _word_tag("br"):
            text_parts.append(DOCX_SOFT_BREAK_TOKEN)

    text = "".join(text_parts)
    if not text:
        return ""
    return text


def _paragraph_text(paragraph: ET.Element, styles: dict[str, str]) -> str:
    style_name = ""
    style_node = paragraph.find("w:pPr/w:pStyle", WORD_NAMESPACE)
    if style_node is not None:
        style_id = style_node.get(_word_tag("val")) or style_node.get("val") or ""
        style_name = styles.get(style_id, style_id)

    parts: list[str] = []
    for child in paragraph:
        if child.tag == _word_tag("r"):
            parts.append(_run_text(child))
        elif child.tag == _word_tag("hyperlink"):
            for run in child.findall("w:r", WORD_NAMESPACE):
                parts.append(_run_text(run))
        elif child.tag == _word_tag("br"):
            parts.append("\n")

    text = "".join(parts).strip()
    return _format_docx_text(text, style_name)


def _table_to_markdown(table: ET.Element, styles: dict[str, str]) -> str:
    rows: list[str] = []
    for row_index, row in enumerate(table.findall("w:tr", WORD_NAMESPACE)):
        cells = []
        for cell in row.findall("w:tc", WORD_NAMESPACE):
            cell_parts = []
            for paragraph in cell.findall("w:p", WORD_NAMESPACE):
                paragraph_text = _paragraph_text(paragraph, styles)
                if paragraph_text:
                    cell_parts.append(paragraph_text)
            cell_text = (
                " ".join(cell_parts)
                .strip()
                .replace(DOCX_SOFT_BREAK_TOKEN, " ")
                .replace("\n", " ")
                .replace("|", r"\|")
            )
            cells.append(cell_text)
        if not cells:
            continue
        rows.append("| " + " | ".join(cells) + " |")
        if row_index == 0:
            rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
    return "\n".join(rows)


def _extract_docx_with_zipxml(file_path: Path) -> str:
    with zipfile.ZipFile(file_path) as archive:
        document_xml = archive.read("word/document.xml")
        styles = _docx_styles(archive)

    root = _safe_xml_fromstring(document_xml)
    body = root.find("w:body", WORD_NAMESPACE)
    if body is None:
        return ""

    blocks: list[str] = []
    for child in body:
        if child.tag == _word_tag("p"):
            formatted = _paragraph_text(child, styles)
            if formatted:
                blocks.append(formatted)
        elif child.tag == _word_tag("tbl"):
            table_md = _table_to_markdown(child, styles)
            if table_md:
                blocks.append(table_md)
    return _normalize_markdown("\n\n".join(blocks))


def _extract_doc_with_olefile(file_path: Path) -> str:
    olefile = importlib.import_module("olefile")

    if not olefile.isOleFile(str(file_path)):
        return ""

    with olefile.OleFileIO(str(file_path)) as ole:
        if not ole.exists("WordDocument"):
            return ""
        stream = ole.openstream("WordDocument")
        data = stream.read()

    for encoding in ("utf-16le", "gbk", "utf-8"):
        try:
            text = data.decode(encoding, errors="ignore")
            break
        except Exception:
            continue
    else:
        return ""

    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x0b", "\n").replace("\x0c", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    normalized = _normalize_markdown(text)
    if not _looks_like_readable_text(normalized):
        return ""
    return normalized


def _looks_like_readable_text(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 20:
        return False

    readable_chars = sum(
        1
        for char in compact
        if char.isalnum() or "\u4e00" <= char <= "\u9fff" or char in ".,;:!?()[]{}<>-_/#%&@'\"，。；：？！、（）【】《》"
    )
    return readable_chars / len(compact) >= 0.6


def _extract_with_pandoc(file_path: Path) -> str:
    command = ["pandoc", str(file_path), "-t", "markdown", "--wrap=none"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "pandoc conversion failed")
    return _normalize_markdown(result.stdout)


def _run_extractors(file_path: Path) -> tuple[str, str, list[str]]:
    extractors: list[tuple[str, Callable[[Path], str]]]
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        extractors = [
            ("markitdown", _extract_with_markitdown),
            ("pymupdf", _extract_pdf_with_pymupdf),
            ("pypdf", _extract_pdf_with_pypdf),
        ]
    elif suffix == ".docx":
        extractors = [
            ("markitdown", _extract_with_markitdown),
            ("docx-xml", _extract_docx_with_zipxml),
            ("pandoc", _extract_with_pandoc),
        ]
    else:
        extractors = [
            ("markitdown", _extract_with_markitdown),
            ("pandoc", _extract_with_pandoc),
            ("olefile", _extract_doc_with_olefile),
        ]

    errors: list[str] = []
    for parser_name, extractor in extractors:
        try:
            content = extractor(file_path)
        except ImportError as exc:
            errors.append(f"{parser_name}: {exc}")
            continue
        except FileNotFoundError as exc:
            errors.append(f"{parser_name}: {exc}")
            continue
        except Exception as exc:
            errors.append(f"{parser_name}: {exc}")
            continue

        if content and content.strip():
            return content, parser_name, errors
        errors.append(f"{parser_name}: extracted empty content")

    return "", "", errors


@tool("doc_parser", args_schema=DocParserInput)
def doc_parser(
        input_path: str,
        output_path: Optional[str] = None,
        overwrite: bool = True,
) -> str:
    """
    Parse a PDF, DOCX, or DOC file into Markdown and write the result to an .md file.

    If output_path is omitted, the markdown file is written to the workspace outputs
    directory for today.

    Args:
        input_path: Absolute or relative path to the source PDF / DOCX / DOC file.
        output_path: Optional output markdown path. Absolute paths are used directly.
                    Relative paths are resolved inside the workspace directory.
        overwrite: Whether to overwrite an existing markdown output file.

    Returns:
        Formatted string with conversion result and metadata
    """
    # Get workspace directory from environment or use current directory
    workspace_dir = Path.cwd()

    # Resolve input path
    input_file = _resolve_input_path(input_path, workspace_dir)
    if not input_file.exists():
        return f"Error: Input file not found: {input_file}"

    if input_file.suffix.lower() not in SUPPORTED_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
        return f"Error: Unsupported file type: {input_file.suffix or '(none)'}. Supported: {supported}"

    # Resolve output path
    output_file = _resolve_output_path(input_file, output_path, workspace_dir)
    if output_file.exists() and not overwrite:
        return f"Error: Output file already exists: {output_file}"

    logger.info(f"Parsing document: {input_file}")

    # Run extractors
    try:
        # Run in thread pool for CPU-intensive operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        markdown, parser_name, errors = loop.run_until_complete(
            asyncio.to_thread(_run_extractors, input_file)
        )
        loop.close()
    except Exception as e:
        return f"Error: Failed to parse document - {str(e)}"

    if not markdown:
        error_lines = "\n".join(errors) if errors else "No parser produced content."
        return f"Error: Failed to parse document: {input_file.name}\n{error_lines}"

    # Create output directory if needed
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write output file
    try:
        output_file.write_text(markdown + "\n", encoding="utf-8")
    except Exception as e:
        return f"Error: Failed to write output file - {str(e)}"

    # Format result
    result_lines = [
        "=" * 60,
        "Document Parsed Successfully",
        "=" * 60,
        f"Input File: {input_file}",
        f"Output File: {output_file}",
        f"Parser Used: {parser_name}",
        f"Characters: {len(markdown):,}",
        f"Overwrite: {overwrite}",
        "",
        "The markdown content has been written to the output file."
    ]

    if errors:
        result_lines.append("")
        result_lines.append("Parser Errors (fallback succeeded):")
        for error in errors[:3]:  # Show first 3 errors
            result_lines.append(f"  - {error}")

    logger.info(f"Successfully parsed {input_file} using {parser_name}")
    return "\n".join(result_lines)


# Optional: Provide a wrapper function for easier testing
def doc_parser_callable(
        input_path: str,
        output_path: Optional[str] = None,
        overwrite: bool = True,
) -> str:
    """
    Wrapper function for direct testing.
    """
    return doc_parser.invoke({
        "input_path": input_path,
        "output_path": output_path,
        "overwrite": overwrite
    })


if __name__ == "__main__":
    print("=" * 80)
    print("Testing Doc Parser Tool")
    print("=" * 80)

    # Note: This example requires actual document files to test
    # The following shows the structure of using the tool

    # Example with a PDF file
    print("\n1. Testing with PDF file (example structure):")
    result = doc_parser.invoke({
        "input_path": "path/to/document.pdf",
        "output_path": None,  # Auto-generate output path
        "overwrite": True
    })
    print(result[:500] if len(result) > 500 else result)

    # Example with custom output path
    print("\n2. Testing with custom output path:")
    result = doc_parser.invoke({
        "input_path": "path/to/document.docx",
        "output_path": "custom/output.md",
        "overwrite": False
    })
    print(result)

    # Example with error handling
    print("\n3. Testing error handling (non-existent file):")
    result = doc_parser.invoke({
        "input_path": "nonexistent.pdf",
        "output_path": None
    })
    print(result)
