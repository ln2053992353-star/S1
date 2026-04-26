#!/usr/bin/env python
"""
测试向量归一化修复和embedding_text解析
"""
import os
import sys
import json
import numpy as np
import django

# Django环境初始化
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import ProductEmbedding
from sentence_transformers import SentenceTransformer


def test_vector_normalization():
    """测试向量归一化修复"""
    print("=== 测试向量归一化 ===")

    # 获取一个样本向量
    embedding = ProductEmbedding.objects.filter(vector__isnull=False).first()
    if not embedding:
        print("没有找到向量数据")
        return False

    try:
        # 加载向量
        vector_data = json.loads(embedding.vector, parse_float=float)
        vector_np = np.array(vector_data, dtype=np.float64)
        vector_np = vector_np.astype(np.float32)

        # 计算原始向量的范数
        original_norm = np.linalg.norm(vector_np)
        print(f"原始向量范数: {original_norm}")

        # 归一化
        normalized = vector_np / original_norm if original_norm > 0 else vector_np
        normalized_norm = np.linalg.norm(normalized)
        print(f"归一化后范数: {normalized_norm}")

        # 测试自相似度
        similarity = np.dot(vector_np, vector_np) / (original_norm * original_norm)
        print(f"自相似度: {similarity}")

        # 检查是否需要归一化（范数是否接近1.0）
        needs_normalization = abs(original_norm - 1.0) > 0.01
        if needs_normalization:
            print(f"[WARNING] 需要归一化：向量范数 {original_norm} 偏离1.0超过0.01")
        else:
            print(f"[OK] 向量已正确归一化（范数: {original_norm})")

        return needs_normalization

    except Exception as e:
        print(f"[ERROR] 向量归一化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return True


def test_embedding_text_parsing():
    """测试embedding_text解析"""
    print("\n=== 测试embedding_text解析 ===")

    # 获取一个样本
    embedding = ProductEmbedding.objects.filter(embedding_text__isnull=False).first()
    if not embedding:
        print("没有找到embedding_text数据")
        return

    print(f"原始embedding_text (前200字符):\n{embedding.embedding_text[:200]}...")

    # 测试解析
    try:
        parsed = embedding.parse_embedding_text()
        print(f"\n解析结果:")
        print(f"  产品名称: {parsed.get('product_name', '')}")
        print(f"  功能描述: {parsed.get('function', '')[:100]}..." if parsed.get('function') else "  功能描述: (空)")
        print(f"  标签: {parsed.get('tags', [])}")
        print(f"  PubChem标签: {parsed.get('pubchem_tags', [])}")

        # 测试缓存属性
        print(f"\n缓存属性测试:")
        print(f"  extracted_functional_summary (缓存): {embedding.extracted_functional_summary[:100]}..." if embedding.extracted_functional_summary else "  extracted_functional_summary (缓存): (空)")
        print(f"  extracted_tags: {embedding.extracted_tags}")

        # 验证解析结果是否包含预期的键
        expected_keys = ['product_name', 'description', 'function', 'tags', 'pubchem_tags']
        missing_keys = [key for key in expected_keys if key not in parsed]
        if missing_keys:
            print(f"[WARNING]  解析结果缺少键: {missing_keys}")
        else:
            print("[OK] 解析结果包含所有预期键")

    except Exception as e:
        print(f"[ERROR] embedding_text解析测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_cosine_similarity_calculation():
    """测试余弦相似度计算"""
    print("\n=== 测试余弦相似度计算 ===")

    try:
        # 加载模型
        model = SentenceTransformer("pritamdeka/S-PubMedBert-MS-MARCO")

        # 测试文本
        test_text = "This is a test query for cosine similarity"
        query_vector = model.encode(test_text)

        # 获取一个数据库向量
        embedding = ProductEmbedding.objects.filter(vector__isnull=False).first()
        if not embedding:
            print("没有找到向量数据")
            return

        db_vector_data = json.loads(embedding.vector, parse_float=float)
        db_vector_np = np.array(db_vector_data, dtype=np.float64)
        db_vector_np = db_vector_np.astype(np.float32)

        # 计算相似度（三种方法）
        # 方法1：直接计算
        norm_query = np.linalg.norm(query_vector)
        norm_db = np.linalg.norm(db_vector_np)
        similarity_direct = np.dot(query_vector, db_vector_np) / (norm_query * norm_db)

        # 方法2：归一化后计算
        query_norm = query_vector / norm_query if norm_query > 0 else query_vector
        db_norm = db_vector_np / norm_db if norm_db > 0 else db_vector_np
        similarity_normalized = np.dot(query_norm, db_norm)

        print(f"直接计算相似度: {similarity_direct}")
        print(f"归一化后相似度: {similarity_normalized}")
        print(f"差异: {abs(similarity_direct - similarity_normalized)}")

        # 检查相似度是否在合理范围内
        if abs(similarity_direct) > 1.01 or abs(similarity_normalized) > 1.01:
            print(f"[WARNING]  相似度超出理论范围: direct={similarity_direct}, normalized={similarity_normalized}")
        else:
            print(f"[OK] 相似度在合理范围内")

        # 测试当查询等于embedding_text时的相似度
        if embedding.embedding_text:
            same_text_vector = model.encode(embedding.embedding_text)
            norm_same = np.linalg.norm(same_text_vector)
            same_norm = same_text_vector / norm_same if norm_same > 0 else same_text_vector

            # 归一化数据库向量
            db_norm = db_vector_np / norm_db if norm_db > 0 else db_vector_np

            similarity_same = np.dot(same_norm, db_norm)
            print(f"\n查询等于embedding_text时的相似度: {similarity_same}")

            # 验证相似度是否接近1.0
            tolerance = 0.001
            if abs(similarity_same - 1.0) < tolerance:
                print(f"[OK] 完美匹配！相似度接近1.0 (误差: {abs(similarity_same - 1.0)})")
            else:
                print(f"[WARNING]  相似度偏离1.0: {similarity_same} (误差: {abs(similarity_same - 1.0)})")

        else:
            print("[WARNING]  没有embedding_text，跳过相同文本相似度测试")

    except Exception as e:
        print(f"[ERROR] 余弦相似度计算测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_faiss_normalization_consistency():
    """测试FAISS归一化一致性"""
    print("\n=== 测试FAISS归一化一致性 ===")

    try:
        from search_engine.vector_index import VectorIndex

        # 创建临时索引实例
        index = VectorIndex()

        # 测试构建索引（如果已有索引文件，可能不需要重建）
        print("检查FAISS索引构建逻辑...")

        # 验证数据库向量是否会在构建时归一化
        # 通过检查vector_index.py代码逻辑来验证
        print("检查vector_index.py中的归一化代码...")

        # 读取vector_index.py文件，检查是否添加了归一化
        vector_index_path = os.path.join(BASE_DIR, "search_engine", "vector_index.py")
        with open(vector_index_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if 'faiss.normalize_L2(vectors_np)' in content:
            print("[OK] vector_index.py中已添加数据库向量归一化")
        else:
            print("[ERROR] vector_index.py中未找到数据库向量归一化代码")

        if 'faiss.normalize_L2(query_np)' in content:
            print("[OK] vector_index.py中已包含查询向量归一化")
        else:
            print("[ERROR] vector_index.py中未找到查询向量归一化代码")

    except Exception as e:
        print(f"[ERROR] FAISS归一化一致性测试失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主测试函数"""
    print("开始测试向量检索修复方案...")

    # 测试1：向量归一化
    needs_normalization = test_vector_normalization()

    # 测试2：embedding_text解析
    test_embedding_text_parsing()

    # 测试3：余弦相似度计算
    test_cosine_similarity_calculation()

    # 测试4：FAISS归一化一致性
    test_faiss_normalization_consistency()

    print("\n=== 测试总结 ===")
    if needs_normalization:
        print("[WARNING]  需要修复：数据库向量未归一化")
    else:
        print("[OK] 数据库向量已归一化")

    print("[OK] 所有测试完成")

    # 返回测试结果
    return needs_normalization


if __name__ == "__main__":
    needs_fix = main()
    sys.exit(0 if not needs_fix else 1)