# core/rag/rag_tool.py
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import Optional, List

from soma.service.rag_service import rag_service


class RagSearchInput(BaseModel):
    query: str = Field(description="The search query to retrieve relevant knowledge from the knowledge base.")
    collection_names: Optional[List[str]] = Field(
        default=None,
        description="Specific knowledge collection names to search in. If empty, search all collections."
    )
    top_k: int = Field(default=5, description="Maximum number of results to return.")


class RagIngestInput(BaseModel):
    collection_name: str = Field(description="Target knowledge collection name.")
    file_path: str = Field(description="Absolute or relative path to the document file (PDF, DOCX, DOC, TXT).")


def _format_rag_results(results: List[dict]) -> str:
    """格式化 RAG 检索结果"""
    if not results:
        return "No relevant knowledge found for the query."

    lines = ["[Knowledge Base]"]

    for i, result in enumerate(results, 1):
        lines.append(f"[{i}] {result.get('document_name', 'unknown')} (score:{result.get('score', 0):.2f})")
        content = result.get('content', '')
        lines.append(content[:500] + "..." if len(content) > 500 else content)

    return "\n".join(lines)


@tool("rag_search", args_schema=RagSearchInput)
def rag_search(query: str, collection_names: Optional[List[str]] = None, top_k: int = 5) -> str:
    """
    Search knowledge bases for relevant information.

    IMPORTANT: Always use this tool proactively when answering questions about:
    - TDA, DDAN, DDEI, AE or other NDR-related products
    - Product manuals, user guides, operation documentation
    - Troubleshooting, problem handling, or technical specifications

    Do NOT wait for user to explicitly say "search knowledge base".

    Returns:
        Formatted string containing search results with source attribution.
    """
    try:
        collection_ids = None
        if collection_names:
            all_collections = rag_service.list_collections()
            collection_ids = [
                c['id'] for c in all_collections
                if c['name'] in collection_names
            ]
            if not collection_ids:
                return f"No knowledge collections found with names: {', '.join(collection_names)}"

        results = rag_service.search(query, collection_ids=collection_ids, top_k=top_k)
        return _format_rag_results(results)
    except Exception as e:
        return f"Error searching knowledge base: {str(e)}"


@tool("rag_ingest", args_schema=RagIngestInput)
def rag_ingest(collection_name: str, file_path: str) -> str:
    """
    Ingest a document into a knowledge collection.

    Parses the document, splits it into chunks, and stores it in the specified
    knowledge collection for future retrieval.

    Returns:
        Formatted string with ingestion status and document metadata.
    """
    try:
        all_collections = rag_service.list_collections()
        collection = next((c for c in all_collections if c['name'] == collection_name), None)

        if not collection:
            return f"Knowledge collection '{collection_name}' not found."

        result = rag_service.ingest_document(collection['id'], file_path)

        if not result:
            return f"Failed to ingest document: {file_path}"

        return (
            f"Document ingested successfully:\n"
            f"  File: {result['file_name']}\n"
            f"  Collection: {collection_name}\n"
            f"  Chunks created: {result['chunks_created']}\n"
            f"  Total chunks: {result['total_chunks']}"
        )
    except Exception as e:
        return f"Error ingesting document: {str(e)}"
