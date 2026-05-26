# core/rag/chunker.py
import hashlib
from typing import List, Tuple

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE,
               chunk_overlap: int = DEFAULT_CHUNK_OVERLAP) -> List[Tuple[str, dict]]:
    """
    文本分块
    使用滑动窗口切分文本，保持块间重叠以保证上下文连续性。
    """
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    if not paragraphs:
        return [(text, {"token_count": len(text) // 4, "paragraph_count": 1})]

    chunks = []
    current_chunk = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = len(para) // 4

        if current_tokens + para_tokens > chunk_size and current_chunk:
            chunk_content = '\n\n'.join(current_chunk)
            chunks.append((chunk_content, {
                'token_count': current_tokens,
                'paragraph_count': len(current_chunk)
            }))

            if chunk_overlap > 0:
                overlap_tokens = 0
                overlap_paras = []
                for p in reversed(current_chunk):
                    p_tokens = len(p) // 4
                    if overlap_tokens + p_tokens <= chunk_overlap:
                        overlap_paras.insert(0, p)
                        overlap_tokens += p_tokens
                    else:
                        break
                current_chunk = overlap_paras
                current_tokens = overlap_tokens
            else:
                current_chunk = []
                current_tokens = 0

        current_chunk.append(para)
        current_tokens += para_tokens

    if current_chunk:
        chunk_content = '\n\n'.join(current_chunk)
        chunks.append((chunk_content, {
            'token_count': current_tokens,
            'paragraph_count': len(current_chunk)
        }))

    return chunks


def compute_content_hash(content: str) -> str:
    """计算内容哈希，用于去重"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()