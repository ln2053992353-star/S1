"""
向量索引管理模块（FAISS）
提供高效的向量相似度搜索，替代线性扫描
"""

import numpy as np
import json
import logging
import os
import pickle
from typing import List, Tuple, Optional, Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)

# 尝试导入FAISS，如果不可用则使用回退模式
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS not available, falling back to linear scan")

from .models import Product, ProductEmbedding


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """计算两个向量的余弦相似度，确保结果在[-1, 1]范围内"""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0

    similarity = float(np.dot(a, b) / (norm_a * norm_b))

    # 数值稳定性检查
    if similarity > 1.0:
        similarity = 1.0
    elif similarity < -1.0:
        similarity = -1.0

    return similarity


class VectorIndex:
    """FAISS向量索引管理器"""

    def __init__(self, index_path: str = None):
        """
        初始化向量索引

        Args:
            index_path: 索引保存路径，如果为None则使用默认路径
        """
        # 从settings获取索引路径或使用默认路径
        self.index_path = index_path or getattr(
            settings, 'FAISS_INDEX_PATH',
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data",
                "faiss_index.bin"
            )
        )
        self.product_ids: List[int] = []  # 索引位置对应的产品ID
        self.index = None
        # 从settings获取向量维度，默认768（PubMedBert维度）
        self.dimension = getattr(settings, 'EMBEDDING_DIMENSION', 768)
        self.is_initialized = False

        # 确保数据目录存在
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)

    def build_from_database(self, force_rebuild: bool = False) -> bool:
        """
        从数据库构建或加载FAISS索引

        Args:
            force_rebuild: 是否强制重新构建索引

        Returns:
            bool: 是否成功构建/加载
        """
        # 如果索引文件存在且不需要强制重建，尝试加载
        if os.path.exists(self.index_path) and not force_rebuild:
            try:
                return self._load_index()
            except Exception as e:
                logger.warning(f"Failed to load existing index: {e}, rebuilding...")

        # 构建新索引
        try:
            # 获取所有有效向量（使用配置的模型名称）
            model_name = getattr(settings, 'EMBEDDING_MODEL_NAME', 'pritamdeka/S-PubMedBert-MS-MARCO')
            embeddings = ProductEmbedding.objects.filter(
                vector__isnull=False,
                model_name=model_name
            ).select_related('product')

            total = embeddings.count()
            if total == 0:
                logger.error("No embeddings found in database")
                return False

            logger.info(f"Building FAISS index from {total} embeddings...")

            # 准备数据
            vectors = []
            self.product_ids = []

            for i, pe in enumerate(embeddings):
                try:
                    # 使用更精确的JSON解析，保留float精度
                    vector_data = json.loads(pe.vector, parse_float=float)

                    # 转换为numpy数组，先使用float64保持精度，再转换为FAISS需要的float32
                    vector_np = np.array(vector_data, dtype=np.float64)
                    vector_np = vector_np.astype(np.float32)

                    if len(vector_np) != self.dimension:
                        logger.warning(f"Embedding dimension mismatch for product {pe.product_id}: "
                                     f"expected {self.dimension}, got {len(vector_np)}")
                        continue

                    vectors.append(vector_np)
                    self.product_ids.append(pe.product_id)

                    if (i + 1) % 100 == 0:
                        logger.debug(f"Processed {i + 1}/{total} embeddings")

                except Exception as e:
                    logger.warning(f"Failed to process embedding for product {pe.product_id}: {e}")
                    continue

            if not vectors:
                logger.error("No valid vectors found")
                return False

            # 转换为numpy数组
            vectors_np = np.array(vectors, dtype=np.float32)

            # 关键修复：对数据库向量进行归一化
            faiss.normalize_L2(vectors_np)

            # 构建FAISS索引 (使用内积索引，因为向量已归一化)
            # 对于余弦相似度，使用内积索引（向量已归一化）
            self.index = faiss.IndexFlatIP(self.dimension)
            self.index.add(vectors_np)

            # 保存索引
            self._save_index()

            self.is_initialized = True
            logger.info(f"FAISS index built successfully with {len(vectors)} vectors")
            return True

        except Exception as e:
            logger.error(f"Failed to build FAISS index: {e}")
            if FAISS_AVAILABLE:
                raise
            return False

    def _save_index(self):
        """保存索引到文件"""
        if self.index is None:
            return

        try:
            # 保存FAISS索引
            faiss.write_index(self.index, self.index_path)

            # 保存产品ID映射
            meta_path = self.index_path + ".meta"
            with open(meta_path, 'wb') as f:
                pickle.dump({
                    'product_ids': self.product_ids,
                    'dimension': self.dimension
                }, f)

            logger.info(f"Index saved to {self.index_path}")
        except Exception as e:
            logger.error(f"Failed to save index: {e}")

    def _load_index(self) -> bool:
        """从文件加载索引"""
        try:
            # 加载FAISS索引
            self.index = faiss.read_index(self.index_path)

            # 加载产品ID映射
            meta_path = self.index_path + ".meta"
            if os.path.exists(meta_path):
                with open(meta_path, 'rb') as f:
                    meta = pickle.load(f)
                    self.product_ids = meta['product_ids']
                    self.dimension = meta.get('dimension', 768)
            else:
                # 如果没有元数据文件，需要重新构建
                logger.warning("No metadata file found, index needs rebuilding")
                return False

            self.is_initialized = True
            logger.info(f"Index loaded from {self.index_path} with {len(self.product_ids)} vectors")
            return True

        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            return False

    def search(
        self,
        query_vector: List[float],
        top_k: int = 20,
        threshold: float = 0.2
    ) -> List[Tuple[int, float]]:
        """
        搜索相似向量

        Args:
            query_vector: 查询向量
            top_k: 返回结果数量
            threshold: 相似度阈值

        Returns:
            List[Tuple[int, float]]: (产品ID, 相似度分数) 列表
        """
        if not self.is_initialized or self.index is None:
            raise RuntimeError("Index not initialized. Call build_from_database() first.")

        if len(query_vector) != self.dimension:
            raise ValueError(f"Query vector dimension mismatch: expected {self.dimension}, got {len(query_vector)}")

        # 转换为numpy数组并归一化（FAISS内积索引需要归一化向量）
        query_np = np.array([query_vector], dtype=np.float32)
        faiss.normalize_L2(query_np)  # 归一化以支持余弦相似度

        # 搜索
        distances, indices = self.index.search(query_np, min(top_k * 2, len(self.product_ids)))

        # 转换距离为相似度分数（内积距离就是余弦相似度，因为向量已归一化）
        results = []
        for _, (distance, idx) in enumerate(zip(distances[0], indices[0])):
            if idx == -1:  # FAISS返回-1表示没有足够结果
                continue

            similarity = float(distance)  # 内积距离即余弦相似度
            if similarity < threshold:
                continue

            product_id = self.product_ids[idx]
            results.append((product_id, similarity))

        # 按相似度降序排序并限制数量
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def search_with_fallback(
        self,
        query_vector: List[float],
        top_k: int = 20,
        threshold: float = 0.2
    ) -> List[Tuple[int, float]]:
        """
        搜索相似向量，如果FAISS不可用则回退到线性扫描

        Args:
            query_vector: 查询向量
            top_k: 返回结果数量
            threshold: 相似度阈值

        Returns:
            List[Tuple[int, float]]: (产品ID, 相似度分数) 列表
        """
        if FAISS_AVAILABLE and self.is_initialized:
            return self.search(query_vector, top_k, threshold)
        else:
            # 回退到线性扫描
            logger.warning("FAISS not available, using linear scan fallback")
            return self._linear_scan(query_vector, top_k, threshold)

    def _linear_scan(
        self,
        query_vector: List[float],
        top_k: int = 20,
        threshold: float = 0.2
    ) -> List[Tuple[int, float]]:
        """线性扫描回退方法"""
        query_np = np.array(query_vector)
        query_norm = np.linalg.norm(query_np)
        if query_norm == 0:
            return []

        results = []

        # 获取所有嵌入（使用配置的模型名称）
        model_name = getattr(settings, 'EMBEDDING_MODEL_NAME', 'pritamdeka/S-PubMedBert-MS-MARCO')
        embeddings = ProductEmbedding.objects.filter(
            vector__isnull=False,
            model_name=model_name
        ).select_related('product')

        for pe in embeddings:
            try:
                # 使用更精确的JSON解析，保持一致性
                vector_data = json.loads(pe.vector, parse_float=float)
                vector_np = np.array(vector_data, dtype=np.float64)
                vector_np = vector_np.astype(np.float32)

                if len(vector_np) != self.dimension:
                    continue

                similarity = _cosine_similarity(query_np, vector_np)

                if similarity > threshold:
                    results.append((pe.product_id, similarity))

            except Exception as e:
                logger.debug(f"Error processing embedding for product {pe.product_id}: {e}")
                continue

        # 按相似度降序排序并限制数量
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def get_index_stats(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        if not self.is_initialized or self.index is None:
            return {"initialized": False}

        return {
            "initialized": True,
            "vector_count": len(self.product_ids),
            "dimension": self.dimension,
            "faiss_available": FAISS_AVAILABLE,
            "index_path": self.index_path
        }


# 全局索引实例
_global_index = None


def get_vector_index() -> VectorIndex:
    """获取全局向量索引实例（单例模式）"""
    global _global_index
    if _global_index is None:
        _global_index = VectorIndex()
    return _global_index


def initialize_index(force_rebuild: bool = False) -> bool:
    """初始化全局向量索引"""
    index = get_vector_index()
    return index.build_from_database(force_rebuild)


def search_similar_vectors(
    query_vector: List[float],
    top_k: int = 20,
    threshold: float = 0.2,
    use_fallback: bool = True
) -> List[Tuple[int, float]]:
    """
    搜索相似向量（便捷函数）

    Args:
        query_vector: 查询向量
        top_k: 返回结果数量
        threshold: 相似度阈值
        use_fallback: 是否允许回退到线性扫描

    Returns:
        List[Tuple[int, float]]: (产品ID, 相似度分数) 列表
    """
    index = get_vector_index()

    if not index.is_initialized:
        # 尝试初始化索引
        if not index.build_from_database():
            if use_fallback:
                logger.warning("Index initialization failed, using linear scan")
                return index._linear_scan(query_vector, top_k, threshold)
            else:
                raise RuntimeError("Vector index not initialized and fallback disabled")

    if use_fallback:
        return index.search_with_fallback(query_vector, top_k, threshold)
    else:
        return index.search(query_vector, top_k, threshold)