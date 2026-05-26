# service/rag_embedding_service.py
import os
import threading
from typing import List
import numpy as np
from soma.config.settings import WORKSPACE_DIR
from soma.config.logging_config import get_logger

logger = get_logger(__name__)

# Default model: local path or HuggingFace model name
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_DIM = 384
DEFAULT_MODEL_PATH = os.path.join(WORKSPACE_DIR, ".soma", "models", DEFAULT_MODEL_NAME)

# Configure HuggingFace mirror for Chinese network (used when local path not found)
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')


class RagEmbeddingService:
    """RAG 文本向量化服务 - 使用本地 sentence-transformers 模型"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.model = None
        self.model_name = DEFAULT_MODEL_NAME
        self.dimension = DEFAULT_DIM
        self._loading_lock = threading.Lock()
        self._loading_complete = threading.Event()
        self._initialized = True

    def initialize(self, model_path: str = DEFAULT_MODEL_PATH):
        """初始化本地 embedding 模型（异步加载，不阻塞启动）

        Args:
            model_path: 本地模型路径，如果不存在则从 HuggingFace 下载
        """
        self.model_name = model_path
        self.dimension = DEFAULT_DIM

        # Start loading in background thread
        thread = threading.Thread(target=self._load_model_background, args=(model_path,), daemon=True)
        thread.start()

        logger.info(f"RAG EmbeddingService 启动异步加载: {model_path}")

    def _load_model_background(self, model_path: str):
        """后台线程加载模型"""
        try:
            from sentence_transformers import SentenceTransformer

            # Check if local path exists
            local_exists = os.path.exists(model_path)

            if local_exists:
                logger.info(f"从本地加载 embedding 模型: {model_path}")
                self.model = SentenceTransformer(model_path)
            else:
                logger.info(f"本地模型不存在，从 HuggingFace 下载: {model_path}")
                self.model = SentenceTransformer(model_path)

            self.dimension = self.model.get_embedding_dimension()
            self._loading_complete.set()
            logger.info(f"RAG EmbeddingService 模型加载完成: dimension={self.dimension}")
        except Exception as e:
            logger.error(f"加载 embedding 模型失败: {e}")
            self._loading_complete.set()  # 即使失败也要设置，防止永久阻塞

    def wait_for_ready(self, timeout: float = 60.0) -> bool:
        """等待模型加载完成"""
        return self._loading_complete.wait(timeout=timeout)

    def is_ready(self) -> bool:
        """检查模型是否已加载"""
        return self.model is not None

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """批量向量化文本"""
        if not self.model:
            logger.warning("Embedding 模型未就绪，使用 mock 向量")
            return self._mock_embeddings(len(texts))

        try:
            # normalize_embeddings=True 使余弦相似度计算更稳定
            embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            return embeddings
        except Exception as e:
            logger.error(f"Embedding 请求失败: {e}")
            return self._mock_embeddings(len(texts))

    def embed_query(self, query: str) -> np.ndarray:
        """向量化查询文本"""
        embeddings = self.embed_texts([query])
        return embeddings[0]

    def _mock_embeddings(self, n: int) -> np.ndarray:
        """Mock embeddings for testing when model is not available"""
        return np.random.rand(n, self.dimension).astype(np.float32)


# 全局单例
rag_embedding_service = RagEmbeddingService()
