# scripts/vector_search.py

import os
import sys
import json
import django
import numpy as np

# ================================
# 1. Django 环境初始化
# ================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "smart_search_project.settings"
)

django.setup()

from sentence_transformers import SentenceTransformer

# ⚠️ 修正点 1：从正确的 App (search_engine) 导入模型
# 之前写的是 from database.models ... 这是错的
from search_engine.models import ProductEmbedding

# ================================
# 2. 加载向量模型 (修正为 PubMedBert)
# ================================
# ⚠️ 修正点 2：必须和重生脚本里的模型一致
print("正在加载模型: pritamdeka/S-PubMedBert-MS-MARCO ...")
model = SentenceTransformer("pritamdeka/S-PubMedBert-MS-MARCO")


# ================================
# 3. 余弦相似度计算
# ================================
def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    # 防止除以 0 的情况
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return np.dot(a, b) / (norm_a * norm_b)


# ================================
# 4. 核心搜索函数
# ================================
def vector_search(query, top_k=5):
    """
    输入一句话，返回最相似的 Product 列表
    """
    print(f"正在搜索: '{query}' ...")

    # 1. 把用户的搜索词变成向量
    query_vec = model.encode(query)

    scored = []

    # 2. 遍历数据库里的所有向量
    # select_related 预加载关联的 product 表，防止后续循环查询数据库
    embeddings = ProductEmbedding.objects.select_related("product").all()

    if not embeddings.exists():
        print("⚠️ 警告：数据库里没有任何向量数据！请先运行 regenerate_vectors.py。")
        return []

    for pe in embeddings:
        try:
            # 解析数据库里的 JSON 向量字符串
            product_vec = json.loads(pe.vector)

            # 计算相似度
            score = cosine_similarity(query_vec, product_vec)
            scored.append((score, pe.product))
        except Exception as e:
            print(f"跳过错误数据 ID {pe.id}: {e}")

    # 3. 按分数从高到低排序
    scored.sort(key=lambda x: x[0], reverse=True)

    # 4. 返回前 K 个结果
    return [p for _, p in scored[:top_k]]


# ================================
# 5. 本地测试入口
# ================================
if __name__ == "__main__":
    # 您可以用这里的查询词测试效果
    test_query = "antioxidant produced by yeast"

    results = vector_search(test_query)

    print(f"\n--- '{test_query}' 的搜索结果 ---")
    if results:
        for i, p in enumerate(results):
            print(f"{i + 1}. {p.product_name} (ID: {p.product_id})")
            # 如果想看描述，可以取消下面这行的注释
            # print(f"   描述: {p.description[:50]}...")
    else:
        print("未找到匹配结果。")