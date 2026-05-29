# core/rag/rag_chunker.py
import hashlib
import re
from typing import List, Tuple

DEFAULT_CHUNK_SIZE = 300  # 字符数
DEFAULT_CHUNK_OVERLAP = 50


def _is_heading(line: str) -> bool:
    """判断是否是标题行"""
    stripped = line.strip()
    return bool(re.match(r'^#{1,6}\s+', stripped))


def _get_heading_level(line: str) -> int:
    """获取标题级别"""
    match = re.match(r'^(#{1,6})\s+', line.strip())
    return len(match.group(1)) if match else 0


def _clean_text(text: str) -> str:
    """清理文本中的噪声字符"""
    text = re.sub(r'_{5,}\s*', '', text)
    text = re.sub(r'\*{3,}\s*', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _is_table_row(line: str) -> bool:
    """判断是否是 markdown 表格行"""
    stripped = line.strip()
    return stripped.startswith('|') and stripped.endswith('|')


def _is_separator_row(line: str) -> bool:
    """判断是否是表格分隔行（如 | --- | --- |）"""
    stripped = line.strip()
    return bool(re.match(r'^\|[\s\-:|]+\|$', stripped))


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE,
               chunk_overlap: int = DEFAULT_CHUNK_OVERLAP) -> List[Tuple[str, dict]]:
    """
    语义分块 - 保持段落和表格完整性

    策略：
    1. 按 ## 二级标题分割成最小语义单元
    2. 标题和其内容作为一个整体
    3. 表格保持完整性，不跨块分割
    4. 严格控制 chunk 大小不超过 chunk_size * 1.1
    5. 小于 80 字符的块合并到前一个
    """
    text = _clean_text(text)

    if not text.strip():
        return []

    # 第一步：按 ## 二级标题分割
    sections = _split_by_h2(text)

    chunks = []
    for section in sections:
        content = section['content']
        if not content:
            continue

        content_len = len(content)

        # 如果小于限制，直接添加
        if content_len <= chunk_size * 1.1:
            chunks.append((content, _make_meta(content)))
        else:
            # 大于限制，按段落拆分
            sub_chunks = _split_content_by_paragraphs(content, chunk_size, chunk_overlap)
            chunks.extend(sub_chunks)

    # 第二步：合并相邻的小块
    chunks = _merge_small_chunks(chunks, min_size=80)

    return chunks


def _split_by_h2(text: str) -> List[dict]:
    """按 ## 二级标题分割文本"""
    lines = text.split('\n')
    sections = []
    current_lines = []

    for line in lines:
        line = line.rstrip()

        # 检测到 ## 二级标题（新 section 开始）
        if _is_heading(line) and _get_heading_level(line) == 2:
            # 保存之前的 section
            if current_lines:
                section = _build_section(current_lines)
                if section['content']:
                    sections.append(section)
                current_lines = []

        current_lines.append(line)

    # 保存最后一个 section
    if current_lines:
        section = _build_section(current_lines)
        if section['content']:
            sections.append(section)

    return sections


def _build_section(lines: List[str]) -> dict:
    """从行列表构建 section

    section 包含从某个 H2 标题开始，到下一个 H2 标题之前的所有内容
    """
    content = '\n'.join(lines).strip()
    # 找到第一个 H2 标题作为 section 的标题
    heading = ''
    for line in lines:
        if _is_heading(line) and _get_heading_level(line) == 2:
            heading = line.strip()
            break

    return {
        'heading': heading,
        'content': content,
        'raw': content
    }


def _split_content_by_paragraphs(text: str, chunk_size: int, overlap: int) -> List[Tuple[str, dict]]:
    """按段落拆分大文本"""
    # 先识别表格
    segments = _split_into_segments(text)

    chunks = []
    current_chunk = []
    current_len = 0

    for seg_type, seg_content in segments:
        seg_len = len(seg_content)

        if seg_type == 'table':
            # 表格单独处理
            if current_len > 0:
                chunks.append(('\n'.join(current_chunk), _make_meta('\n'.join(current_chunk))))
                current_chunk = []
                current_len = 0

            # 表格可能很大，尝试按行拆分
            if seg_len > chunk_size * 1.1:
                table_chunks = _split_table_by_rows(seg_content, chunk_size, overlap)
                chunks.extend(table_chunks)
            else:
                chunks.append((seg_content, _make_meta(seg_content)))

        elif seg_type == 'text':
            # 普通文本按段落处理
            if current_len + seg_len > chunk_size and current_chunk:
                chunks.append(('\n'.join(current_chunk), _make_meta('\n'.join(current_chunk))))

                # overlap
                if overlap > 0:
                    current_chunk, current_len = _create_overlap(current_chunk, overlap)
                else:
                    current_chunk = []
                    current_len = 0

            current_chunk.append(seg_content)
            current_len += seg_len

    # 保存最后一块
    if current_chunk:
        chunks.append(('\n'.join(current_chunk), _make_meta('\n'.join(current_chunk))))

    return chunks


def _split_into_segments(text: str) -> List[Tuple[str, str]]:
    """将文本分割成段落和表格"""
    lines = text.split('\n')
    segments = []
    current_text_lines = []
    in_table = False
    table_lines = []

    for line in lines:
        if _is_table_row(line):
            if not in_table and current_text_lines:
                # 保存之前的文本（按段落分割）
                for para in _split_paragraphs('\n'.join(current_text_lines)):
                    if para.strip():
                        segments.append(('text', para))
                current_text_lines = []
            in_table = True
            table_lines.append(line)
        elif _is_separator_row(line):
            table_lines.append(line)
        else:
            if in_table and table_lines:
                # 表格结束，保存表格
                table_content = '\n'.join(table_lines).strip()
                if table_content:
                    segments.append(('table', table_content))
                table_lines = []
            in_table = False
            current_text_lines.append(line)

    # 保存最后的内容
    if table_lines:
        table_content = '\n'.join(table_lines).strip()
        if table_content:
            segments.append(('table', table_content))
    elif current_text_lines:
        for para in _split_paragraphs('\n'.join(current_text_lines)):
            if para.strip():
                segments.append(('text', para))

    return segments


def _split_paragraphs(text: str) -> List[str]:
    """按段落分割文本"""
    paragraphs = text.split('\n\n')
    return [p.strip() for p in paragraphs if p.strip()]


def _split_table_by_rows(table_text: str, chunk_size: int, overlap: int) -> List[Tuple[str, dict]]:
    """拆分大表格"""
    lines = table_text.split('\n')
    chunks = []
    current_rows = []
    current_len = 0

    # 保留表头和分隔符
    header_rows = []
    for line in lines:
        # 先检查分隔符（| --- | --- |），否则它会被误判为普通行
        if _is_separator_row(line):
            header_rows.append(line)
            break  # 分隔符后认为是表头结束
        elif _is_table_row(line):
            header_rows.append(line)
        else:
            break  # 非表格行，结束表头

    # 第一个 chunk 包含表头
    current_rows = header_rows.copy()
    current_len = len('\n'.join(current_rows))

    # 继续添加数据行
    for line in lines[len(header_rows):]:
        line_len = len(line)

        # 如果当前行就超过限制，跳过
        if line_len > chunk_size:
            continue

        # 如果加上这行会超限，保存当前 chunk 并开始新的
        if current_len + line_len + 1 > chunk_size and current_rows:
            chunks.append(('\n'.join(current_rows), _make_meta('\n'.join(current_rows))))
            # 新的 chunk 只保留表头
            current_rows = header_rows.copy()
            current_len = len('\n'.join(current_rows))

        current_rows.append(line)
        current_len += line_len + 1  # +1 for newline

    # 保存最后一块
    if current_rows:
        chunks.append(('\n'.join(current_rows), _make_meta('\n'.join(current_rows))))

    return chunks


def _create_overlap(current_lines: List[str], overlap: int) -> Tuple[List[str], int]:
    """创建 overlap"""
    overlap_lines = []
    overlap_len = 0
    for line in reversed(current_lines):
        if overlap_len + len(line) <= overlap:
            overlap_lines.insert(0, line)
            overlap_len += len(line)
        else:
            break
    return overlap_lines, overlap_len


def _merge_small_chunks(chunks: List[Tuple[str, dict]], min_size: int) -> List[Tuple[str, dict]]:
    """合并相邻的小 chunk"""
    if not chunks:
        return chunks

    merged = []
    i = 0
    while i < len(chunks):
        content, meta = chunks[i]
        char_count = meta['char_count']

        # 如果太小且不是最后一个，合并到下一个
        if char_count < min_size and i + 1 < len(chunks):
            next_content, next_meta = chunks[i + 1]
            merged_content = content + '\n' + next_content
            merged_meta = _make_meta(merged_content)
            merged.append((merged_content, merged_meta))
            i += 2
        else:
            merged.append((content, meta))
            i += 1

    return merged


def _make_meta(content: str) -> dict:
    """生成 chunk 元数据"""
    char_count = len(content)
    paragraph_count = len([p for p in content.split('\n\n') if p.strip()])
    line_count = len([l for l in content.split('\n') if l.strip()])
    token_count = char_count // 2
    return {
        'char_count': char_count,
        'token_count': token_count,
        'paragraph_count': paragraph_count,
        'line_count': line_count
    }


def compute_content_hash(content: str) -> str:
    """计算内容哈希，用于去重"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
