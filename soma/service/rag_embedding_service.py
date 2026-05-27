# service/rag_embedding_service.py
import os
import threading
from typing import List
import numpy as np
from soma.config.settings import WORKSPACE_DIR
from soma.config.logging_config import get_logger

logger = get_logger(__name__)

# Configure HuggingFace mirror for Chinese network
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')

# Model configurations
MODEL_CONFIGS = {
    # 英文优化模型
    "all-MiniLM-L6-v2": {
        "dim": 384,
        "hf_name": "sentence-transformers/all-MiniLM-L6-v2",
        "description": "英文优化模型，中文效果一般"
    },
    # 多语言支持模型（推荐中文）
    "bge-base-zh": {
        "dim": 768,
        "hf_name": "BAAI/bge-base-zh",
        "description": "中文优化模型，效果好"
    },
    "bge-large-zh": {
        "dim": 1024,
        "hf_name": "BAAI/bge-large-zh",
        "description": "中文优化大模型，效果最佳"
    },
    "paraphrase-multilingual-MiniLM-L12-v2": {
        "dim": 384,
        "hf_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "description": "多语言模型，支持中文"
    },
}

# Default model - 改成支持中文的模型
DEFAULT_MODEL = "bge-base-zh"


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
        self.model_name = DEFAULT_MODEL
        self.dimension = MODEL_CONFIGS[DEFAULT_MODEL]["dim"]
        self._loading_lock = threading.Lock()
        self._loading_complete = threading.Event()
        self._initialized = True

    def initialize(self, model_name: str = DEFAULT_MODEL):
        """初始化本地 embedding 模型（异步加载，不阻塞启动）

        Args:
            model_name: 模型名称，支持: all-MiniLM-L6-v2, bge-base-zh, bge-large-zh,
                       paraphrase-multilingual-MiniLM-L12-v2
        """
        if model_name not in MODEL_CONFIGS:
            logger.warning(f"未知的模型 {model_name}，使用默认 {DEFAULT_MODEL}")
            model_name = DEFAULT_MODEL

        self.model_name = model_name
        self.dimension = MODEL_CONFIGS[model_name]["dim"]

        # 模型本地存储路径
        model_path = os.path.join(WORKSPACE_DIR, ".soma", "models", model_name)

        # Start loading in background thread
        thread = threading.Thread(target=self._load_model_background, args=(model_name, model_path), daemon=True)
        thread.start()

        logger.info(f"RAG EmbeddingService 启动异步加载: {model_name}, 路径: {model_path}")

    def _load_model_background(self, model_name: str, model_path: str):
        """后台线程加载模型"""
        try:
            from sentence_transformers import SentenceTransformer

            # Check if local path exists
            local_exists = os.path.exists(model_path)

            if local_exists:
                logger.info(f"从本地加载 embedding 模型: {model_path}")
                self.model = SentenceTransformer(model_path)
            else:
                # 从 HuggingFace 下载
                hf_name = MODEL_CONFIGS[model_name]["hf_name"]
                logger.info(f"本地模型不存在，从 HuggingFace 下载: {hf_name}")
                self.model = SentenceTransformer(hf_name)
                # 保存到本地
                self.model.save(model_path)
                logger.info(f"模型已保存到: {model_path}")

            self.dimension = self.model.get_embedding_dimension()
            self._loading_complete.set()
            logger.info(f"RAG EmbeddingService 模型加载完成: {model_name}, dimension={self.dimension}")
        except Exception as e:
            logger.error(f"加载 embedding 模型失败: {e}")
            self._loading_complete.set()  # 即使失败也要设置，防止永久阻塞

    def wait_for_ready(self, timeout: float = 60.0) -> bool:
        """等待模型加载完成"""
        return self._loading_complete.wait(timeout=timeout)

    def is_ready(self) -> bool:
        """检查模型是否已加载"""
        return self.model is not None

    def get_model_info(self) -> dict:
        """获取当前模型信息"""
        return {
            "name": self.model_name,
            "dimension": self.dimension,
            "description": MODEL_CONFIGS.get(self.model_name, {}).get("description", ""),
            "ready": self.is_ready()
        }

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