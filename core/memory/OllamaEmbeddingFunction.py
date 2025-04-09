import logging
import requests
import numpy as np
from typing import List, Optional
from chromadb.api import EmbeddingFunction
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

class OllamaEmbeddingFunction(EmbeddingFunction, Embeddings):
    """使用Ollama生成文本嵌入的函数类，同时兼容ChromaDB和LangChain"""
    
    def __init__(self, base_url: str, model: str = "nomic-embed-text:latest"):
        """初始化Ollama嵌入函数
        
        Args:
            base_url: Ollama服务器地址
            model: 使用的模型名称
        """
        #self.base_url = base_url.rstrip("/")
        self.base_url = "http://localhost:11434"
        self.model = model
        self._validate_connection()
        self._dimension = None  # 存储向量维度
        
    def _validate_connection(self):
        """验证与Ollama服务器的连接"""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
        except Exception as e:
            raise ConnectionError(f"无法连接到Ollama服务器 ({self.base_url}): {e}")
    
    def _get_dimension(self) -> int:
        """获取向量维度"""
        if self.model == "nomic-embed-text:latest":
            return 768  # nomic-embed-text 的标准维度
        return 384  # 默认维度
    
    def _get_embedding(self, text: str) -> List[float]:
        """获取单个文本的嵌入向量"""
        try:
            if not text:
                return [0.0] * self._get_dimension()
            
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=60
            )
            response.raise_for_status()
            embedding = response.json()["embedding"]
            # 归一化向量
            embedding = np.array(embedding)
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = (embedding / norm).tolist()
            return embedding
        except Exception as e:
            logger.error(f"获取文本嵌入时出错: {e}", exc_info=True)
            return [0.0] * self._get_dimension()
        
    def __call__(self, texts: List[str]) -> List[List[float]]:
        """ChromaDB的EmbeddingFunction接口"""
        if not texts:
            logger.warning("输入文本列表为空")
            return [[0.0] * self._get_dimension()]
        
        return [self._get_embedding(text) for text in texts]
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """LangChain的Embeddings接口 - 批量文档嵌入"""
        return self.__call__(texts)
    
    def embed_query(self, text: str) -> List[float]:
        """LangChain的Embeddings接口 - 单个查询嵌入"""
        return self._get_embedding(text)