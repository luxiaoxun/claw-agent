# service/rag_service.py
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from sqlalchemy import func
from soma.config.logging_config import get_logger
from soma.config.settings import SOMA_DIR
from soma.model.rag_model import KnowledgeCollectionModel, RagDocumentModel, RagChunkModel
from soma.service.database_manager import DatabaseManager
from soma.service.rag_chroma_store import ChromaStore
from soma.service.rag_embedding_service import rag_embedding_service
from soma.core.tool.file.doc_parser import doc_parser_callable
from soma.core.rag.chunker import chunk_text, compute_content_hash

logger = get_logger(__name__)


class RagService:
    """RAG 服务 - 单例模式"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db_manager: Optional[DatabaseManager] = None
        self.chroma_store: Optional[ChromaStore] = None
        self._initialized = True

    def initialize(self, db_path: str):
        """初始化 RAG 服务"""
        self.db_manager = DatabaseManager(db_path)
        self.db_manager.initialize()

        chroma_dir = str(Path(SOMA_DIR) / "chroma")
        self.chroma_store = ChromaStore(chroma_dir)
        self.chroma_store.initialize(chroma_dir)

        rag_embedding_service.initialize()

        logger.info("RAG 服务初始化完成")

    def create_collection(self, name: str, description: str = None,
                          chunk_size: int = 500, chunk_overlap: int = 50) -> Optional[int]:
        """创建知识库集合"""
        logger.info(f"[RAG] 创建知识库: name={name}, chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")
        session = self.db_manager.get_session()
        try:
            collection = KnowledgeCollectionModel(
                name=name, description=description,
                chunk_size=chunk_size, chunk_overlap=chunk_overlap
            )
            session.add(collection)
            session.commit()
            logger.info(f"[RAG] 知识库创建成功: id={collection.id}, name={name}")
            return collection.id
        except Exception as e:
            session.rollback()
            logger.error(f"[RAG] 创建知识库失败: {e}")
            return None
        finally:
            session.close()

    def list_collections(self) -> List[Dict]:
        """获取所有知识库集合"""
        logger.info("[RAG] 获取知识库列表")
        session = self.db_manager.get_session()
        try:
            results = session.query(KnowledgeCollectionModel).all()
            collections = []
            for r in results:
                item = r.to_dict()
                doc_count = session.query(func.count(RagDocumentModel.id)).filter(
                    RagDocumentModel.collection_id == r.id
                ).scalar()
                chunk_count = session.query(func.count(RagChunkModel.id)).join(
                    RagDocumentModel
                ).filter(RagDocumentModel.collection_id == r.id).scalar()
                item['document_count'] = doc_count or 0
                item['chunk_count'] = chunk_count or 0
                collections.append(item)
            logger.info(f"[RAG] 知识库列表: 共 {len(collections)} 个")
            return collections
        finally:
            session.close()

    def get_collection(self, collection_id: int) -> Optional[Dict]:
        """获取单个知识库"""
        session = self.db_manager.get_session()
        try:
            r = session.query(KnowledgeCollectionModel).filter(
                KnowledgeCollectionModel.id == collection_id
            ).first()
            if not r:
                return None
            item = r.to_dict()
            doc_count = session.query(func.count(RagDocumentModel.id)).filter(
                RagDocumentModel.collection_id == r.id
            ).scalar()
            item['document_count'] = doc_count or 0
            return item
        finally:
            session.close()

    def update_collection(self, collection_id: int, name: str = None,
                          description: str = None, chunk_size: int = None,
                          chunk_overlap: int = None) -> bool:
        """更新知识库"""
        session = self.db_manager.get_session()
        try:
            collection = session.query(KnowledgeCollectionModel).filter(
                KnowledgeCollectionModel.id == collection_id
            ).first()
            if not collection:
                return False
            if name is not None:
                collection.name = name
            if description is not None:
                collection.description = description
            if chunk_size is not None:
                collection.chunk_size = chunk_size
            if chunk_overlap is not None:
                collection.chunk_overlap = chunk_overlap
            collection.update_time = datetime.now()
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"更新知识库失败: {e}")
            return False
        finally:
            session.close()

    def delete_collection(self, collection_id: int) -> bool:
        """删除知识库集合（级联删除）"""
        logger.info(f"[RAG] 删除知识库: collection_id={collection_id}")
        session = self.db_manager.get_session()
        try:
            docs = session.query(RagDocumentModel.id).filter(
                RagDocumentModel.collection_id == collection_id
            ).all()
            doc_ids = [d[0] for d in docs]
            logger.info(f"[RAG] 删除知识库: 关联文档数={len(doc_ids)}")

            if doc_ids:
                for doc_id in doc_ids:
                    self.chroma_store.delete_by_document_id(doc_id)

            collection = session.query(KnowledgeCollectionModel).filter(
                KnowledgeCollectionModel.id == collection_id
            ).first()
            if collection:
                session.delete(collection)
                session.commit()
                logger.info(f"[RAG] 删除知识库完成: collection_id={collection_id}")
                return True
            logger.warning(f"[RAG] 删除知识库失败: 不存在 collection_id={collection_id}")
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"删除知识库失败: {e}")
            return False
        finally:
            session.close()

    def list_documents(self, collection_id: int) -> List[Dict]:
        """获取集合中的文档列表"""
        session = self.db_manager.get_session()
        try:
            results = session.query(RagDocumentModel).filter(
                RagDocumentModel.collection_id == collection_id
            ).all()
            return [r.to_dict() for r in results]
        finally:
            session.close()

    def ingest_document(self, collection_id: int, file_path: str,
                        overwrite: bool = False) -> Optional[Dict]:
        """摄入文档到知识库"""
        logger.info(f"[RAG] 摄入文档: collection_id={collection_id}, file={file_path}, overwrite={overwrite}")
        session = self.db_manager.get_session()
        try:
            collection = session.query(KnowledgeCollectionModel).filter(
                KnowledgeCollectionModel.id == collection_id
            ).first()
            if not collection:
                logger.warning(f"[RAG] 知识库不存在: collection_id={collection_id}")
                return None

            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")

            logger.info(f"[RAG] 解析文档: {file_path_obj.name}")
            file_type = file_path_obj.suffix.lstrip('.').lower()
            markdown_content = doc_parser_callable(str(file_path))

            if markdown_content.startswith("Error:"):
                raise RuntimeError(f"文档解析失败: {markdown_content}")

            logger.info(f"[RAG] 分块: {file_path_obj.name}, markdown长度={len(markdown_content)}, chunk_size={collection.chunk_size}")
            chunks = chunk_text(
                markdown_content,
                chunk_size=int(collection.chunk_size),
                chunk_overlap=int(collection.chunk_overlap)
            )
            logger.info(f"[RAG] 分块完成: {file_path_obj.name}, 块数={len(chunks)}")

            doc = RagDocumentModel(
                collection_id=collection_id,
                file_name=file_path_obj.name,
                file_path=str(file_path_obj.absolute()),
                file_type=file_type,
                file_size=file_path_obj.stat().st_size,
                markdown_content=markdown_content,
                token_count=len(markdown_content) // 4
            )
            session.add(doc)
            session.flush()

            chunk_ids = []
            texts = []
            metadatas = []
            for idx, (content, meta) in enumerate(chunks):
                content_hash = compute_content_hash(content)

                existing = session.query(RagChunkModel).filter(
                    RagChunkModel.content_hash == content_hash
                ).first()
                if existing and not overwrite:
                    continue

                chunk = RagChunkModel(
                    document_id=doc.id,
                    chunk_index=idx,
                    content=content,
                    content_hash=content_hash,
                    token_count=meta.get('token_count'),
                    metadata_=json.dumps(meta)
                )
                session.add(chunk)
                session.flush()
                chunk_ids.append(chunk.id)
                texts.append(content)
                metadatas.append({
                    "document_id": doc.id,
                    "document_name": file_path_obj.name,
                    "collection_id": collection_id,
                    "chunk_index": idx
                })

            session.commit()

            if texts:
                logger.info(f"[RAG] 向量化: {file_path_obj.name}, chunk数={len(texts)}")
                embeddings = rag_embedding_service.embed_texts(texts)
                logger.info(f"[RAG] 存入向量库: {file_path_obj.name}")
                self.chroma_store.insert_vectors(chunk_ids, embeddings, texts, metadatas)

            logger.info(f"[RAG] 文档摄入完成: {file_path_obj.name}, 块数={len(chunk_ids)}")
            return {
                "document_id": doc.id,
                "file_name": doc.file_name,
                "chunks_created": len(chunk_ids),
                "total_chunks": len(chunks)
            }
        except Exception as e:
            logger.error(f"[RAG] 摄入文档失败: {e}")
            return None
        finally:
            session.close()

    def delete_document(self, collection_id: int, document_id: int) -> bool:
        """删除文档"""
        session = self.db_manager.get_session()
        try:
            doc = session.query(RagDocumentModel).filter(
                RagDocumentModel.id == document_id,
                RagDocumentModel.collection_id == collection_id
            ).first()
            if not doc:
                return False

            self.chroma_store.delete_by_document_id(document_id)

            session.delete(doc)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"删除文档失败: {e}")
            return False
        finally:
            session.close()

    def search(self, query: str, collection_ids: Optional[List[int]] = None,
               top_k: int = 5, similarity_threshold: float = 0.5) -> List[Dict]:
        """知识库检索"""
        logger.info(f"[RAG] 检索: query={query[:50]}..., collection_ids={collection_ids}, top_k={top_k}, threshold={similarity_threshold}")
        query_embedding = rag_embedding_service.embed_query(query)

        results = self.chroma_store.search(
            query_embedding, top_k * 2, similarity_threshold
        )

        if not results:
            logger.info("[RAG] 检索完成: 无结果（低于阈值或无数据）")
            return []

        logger.info(f"[RAG] 向量搜索完成: 初步结果={len(results)} 个, 分数范围={results[0][1]:.3f} - {results[-1][1]:.3f}")

        chunk_ids = [r[0] for r in results]
        distances = {r[0]: r[1] for r in results}

        session = self.db_manager.get_session()
        try:
            chunks = session.query(RagChunkModel).filter(
                RagChunkModel.id.in_(chunk_ids)
            ).join(RagDocumentModel).all()

            search_results = []
            for chunk in chunks:
                if collection_ids and chunk.document.collection_id not in collection_ids:
                    continue

                search_results.append({
                    "id": chunk.id,
                    "content": chunk.content,
                    "score": distances.get(chunk.id, 0),
                    "document_id": chunk.document_id,
                    "document_name": chunk.document.file_name,
                    "collection_id": chunk.document.collection_id,
                    "metadata": chunk.metadata_
                })

            search_results.sort(key=lambda x: x['score'], reverse=True)
            result = search_results[:top_k]
            logger.info(f"[RAG] 检索完成: 返回 {len(result)} 条结果")
            return result
        finally:
            session.close()

    def search_all(self, query: str, top_k: int = 5,
                   similarity_threshold: float = 0.7) -> List[Dict]:
        """搜索所有知识库"""
        return self.search(query, collection_ids=None, top_k=top_k,
                           similarity_threshold=similarity_threshold)


# 全局单例
rag_service = RagService()
