# service/rag_chroma_store.py
import os
import uuid
from typing import List, Tuple, Optional
import numpy as np
import chromadb
from chromadb.config import Settings as ChromaSettings
from soma.config.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_DIM = 384  # all-MiniLM-L6-v2 的维度


class ChromaStore:
    """ChromaDB 向量存储封装"""

    _instance = None
    _initialized = False

    def __new__(cls, persist_dir: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, persist_dir: str = None):
        if self._initialized:
            return
        self.persist_dir = persist_dir
        self.client = None
        self.collection = None
        self._initialized = True

    def initialize(self, persist_dir: str = None):
        """初始化 ChromaDB"""
        if persist_dir:
            self.persist_dir = persist_dir

        if not self.persist_dir:
            raise ValueError("persist_dir is required for ChromaDB")

        os.makedirs(self.persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        self.collection = self.client.get_or_create_collection(
            name="rag_chunks",
            metadata={"hnsw:space": "cosine"}
        )

        logger.info(f"ChromaDB 初始化完成，persist_dir: {self.persist_dir}")

    def insert_vectors(self, chunk_ids: List[int], embeddings: np.ndarray,
                      documents: List[str], metadatas: List[dict]):
        """批量插入向量"""
        if not chunk_ids:
            return

        ids = [str(cid) for cid in chunk_ids]
        embeddings_list = embeddings.tolist() if isinstance(embeddings, np.ndarray) else embeddings

        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings_list,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"已插入 {len(chunk_ids)} 个向量到 ChromaDB")
        except Exception as e:
            logger.error(f"向量插入失败: {e}")
            raise

    def search(self, query_embedding: np.ndarray, top_k: int = 5,
               similarity_threshold: float = 0.7) -> List[Tuple[int, float]]:
        """
        向量相似度搜索
        Returns: List of (chunk_id, similarity_score) tuples
        """
        if isinstance(query_embedding, np.ndarray):
            query_embedding = query_embedding.tolist()

        try:
            logger.info(f"[ChromaDB] 开始搜索: top_k={top_k}, threshold={similarity_threshold}")
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["distances", "metadatas"]
            )

            logger.info(f"[ChromaDB] 原始结果: {len(results['ids'][0])} 个")
            for i, dist in enumerate(results["distances"][0]):
                score = 1 - dist
                logger.info(f"[ChromaDB] 结果{i}: id={results['ids'][0][i]}, distance={dist:.4f}, score={score:.4f}")

            scored_results = []
            for i, dist in enumerate(results["distances"][0]):
                score = 1 - dist
                if score >= similarity_threshold:
                    chunk_id = int(results["ids"][0][i])
                    scored_results.append((chunk_id, score))

            return scored_results
        except Exception as e:
            logger.error(f"ChromaDB 搜索失败: {e}")
            return []

    def delete_by_chunk_ids(self, chunk_ids: List[int]):
        """删除向量"""
        if not chunk_ids:
            return
        ids = [str(cid) for cid in chunk_ids]
        try:
            self.collection.delete(ids=ids)
            logger.info(f"已从 ChromaDB 删除 {len(chunk_ids)} 个向量")
        except Exception as e:
            logger.error(f"向量删除失败: {e}")

    def delete_by_document_id(self, document_id: int):
        """删除文档的所有向量"""
        try:
            self.collection.delete(
                where={"document_id": document_id}
            )
            logger.info(f"已从 ChromaDB 删除文档 {document_id} 的所有向量")
        except Exception as e:
            logger.error(f"向量删除失败: {e}")

    def reset(self):
        """重置向量存储"""
        try:
            self.collection.delete()
            logger.info("ChromaDB 已重置")
        except Exception as e:
            logger.error(f"ChromaDB 重置失败: {e}")

    def get_chunk_count(self) -> int:
        """获取向量总数"""
        try:
            return self.collection.count()
        except Exception:
            return 0