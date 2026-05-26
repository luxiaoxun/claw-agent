# web/routers/rag_router.py
import os
import uuid
from fastapi import APIRouter, Body, UploadFile, File, Form, HTTPException
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from soma.config.logging_config import get_logger
from soma.config.settings import WORKSPACE_DIR
from soma.common.response import success_response, fail_response
from soma.service.rag_service import rag_service
from soma.core.rag.rag_tool import rag_search, rag_ingest

logger = get_logger(__name__)
router = APIRouter(prefix="/rag", tags=["rag"])


# ==================== Request Models ====================

class CreateCollectionRequest(BaseModel):
    name: str
    description: Optional[str] = None
    chunk_size: int = 500
    chunk_overlap: int = 50


class UpdateCollectionRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None


class SearchRequest(BaseModel):
    query: str
    collection_ids: Optional[List[int]] = None
    top_k: int = 5
    similarity_threshold: float = 0.7


# ==================== Collection CRUD ====================

@router.get("/collection/list")
async def list_collections():
    """获取知识库集合列表"""
    try:
        collections = rag_service.list_collections()
        return success_response(data={"collections": collections})
    except Exception as e:
        logger.error(f"获取知识库列表失败: {e}")
        return fail_response(message=f"获取知识库列表失败: {str(e)}")


@router.post("/collection/create")
async def create_collection(body: CreateCollectionRequest = Body(...)):
    """创建知识库集合"""
    try:
        collection_id = rag_service.create_collection(
            name=body.name,
            description=body.description,
            chunk_size=body.chunk_size,
            chunk_overlap=body.chunk_overlap
        )
        if collection_id is None:
            return fail_response(message="创建知识库失败，可能是名称已存在")
        return success_response(data={"collection_id": collection_id}, message="知识库创建成功")
    except Exception as e:
        logger.error(f"创建知识库失败: {e}")
        return fail_response(message=f"创建知识库失败: {str(e)}")


@router.post("/collection/{collection_id}/update")
async def update_collection(collection_id: int, body: UpdateCollectionRequest = Body(...)):
    """更新知识库集合"""
    try:
        ok = rag_service.update_collection(
            collection_id=collection_id,
            name=body.name,
            description=body.description,
            chunk_size=body.chunk_size,
            chunk_overlap=body.chunk_overlap
        )
        if not ok:
            return fail_response(message="更新失败，知识库不存在")
        return success_response(message="知识库更新成功")
    except Exception as e:
        logger.error(f"更新知识库失败: {e}")
        return fail_response(message=f"更新知识库失败: {str(e)}")


@router.post("/collection/{collection_id}/delete")
async def delete_collection(collection_id: int):
    """删除知识库集合"""
    try:
        ok = rag_service.delete_collection(collection_id)
        if not ok:
            return fail_response(message="删除失败，知识库不存在")
        return success_response(message="知识库删除成功")
    except Exception as e:
        logger.error(f"删除知识库失败: {e}")
        return fail_response(message=f"删除知识库失败: {str(e)}")


# ==================== Document Operations ====================

@router.get("/collection/{collection_id}/documents")
async def list_documents(collection_id: int):
    """获取知识库中的文档列表"""
    try:
        documents = rag_service.list_documents(collection_id)
        return success_response(data={"documents": documents})
    except Exception as e:
        logger.error(f"获取文档列表失败: {e}")
        return fail_response(message=f"获取文档列表失败: {str(e)}")


@router.post("/collection/{collection_id}/document/upload")
async def upload_document(collection_id: int, file: UploadFile = File(...), overwrite: bool = Form(False)):
    """上传文档到知识库"""
    try:
        collection = rag_service.get_collection(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="知识库不存在")

        suffix = os.path.splitext(file.filename)[1].lower()
        if suffix not in ['.pdf', '.docx', '.doc', '.txt']:
            return fail_response(message="不支持的文件类型，仅支持 PDF/DOCX/DOC/TXT")

        # 保存到 uploads/YYYY-MM-DD/ 目录
        today = datetime.now().strftime("%Y-%m-%d")
        upload_dir = os.path.join(WORKSPACE_DIR, "uploads", today)
        os.makedirs(upload_dir, exist_ok=True)

        # 生成唯一文件名
        import uuid
        unique_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
        file_path = os.path.join(upload_dir, unique_name)

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        try:
            result = rag_service.ingest_document(collection_id, file_path, overwrite=overwrite)
            if not result:
                return fail_response(message="文档处理失败")
            return success_response(data=result, message="文档上传成功")
        except Exception as e:
            logger.error(f"处理文档失败: {e}")
            return fail_response(message=f"文档处理失败: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传文档失败: {e}")
        return fail_response(message=f"上传文档失败: {str(e)}")


@router.post("/collection/{collection_id}/document/{document_id}/delete")
async def delete_document(collection_id: int, document_id: int):
    """删除文档"""
    try:
        ok = rag_service.delete_document(collection_id, document_id)
        if not ok:
            return fail_response(message="删除失败，文档不存在")
        return success_response(message="文档删除成功")
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        return fail_response(message=f"删除文档失败: {str(e)}")


# ==================== Search ====================

@router.post("/search")
async def search_knowledge(body: SearchRequest = Body(...)):
    """知识库检索"""
    try:
        results = rag_service.search(
            query=body.query,
            collection_ids=body.collection_ids,
            top_k=body.top_k,
            similarity_threshold=body.similarity_threshold
        )
        return success_response(data={"results": results, "total": len(results)})
    except Exception as e:
        logger.error(f"知识库检索失败: {e}")
        return fail_response(message=f"知识库检索失败: {str(e)}")


# ==================== Tool Info ====================

@router.get("/tools/info")
async def get_rag_tools_info():
    """获取 RAG tools 信息（供 Agent 显示）"""
    try:
        return success_response(data={
            "tools": [
                {
                    "name": "rag_search",
                    "description": "Search knowledge bases for relevant information",
                    "args": ["query", "collection_names", "top_k"]
                },
                {
                    "name": "rag_ingest",
                    "description": "Ingest a document into a knowledge collection",
                    "args": ["collection_name", "file_path"]
                }
            ]
        })
    except Exception as e:
        logger.error(f"获取工具信息失败: {e}")
        return fail_response(message=f"获取工具信息失败: {str(e)}")
