# scripts/vectorize_products.py

import os
import sys
import json
import django

# ================================
# 1. 手动把“项目根目录”加入 Python 路径
# ================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# ================================
# 2. 指定 Django settings
# ================================
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "smart_search_project.settings"
)

# ================================
# 3. 初始化 Django
# ================================
django.setup()

# 导入Django settings
from django.conf import settings

# ================================
# 4. 正常导入
# ================================
from sentence_transformers import SentenceTransformer
from search_engine.models import Product, ProductEmbedding

# ================================
# 5. 加载模型（从settings获取配置）
# ================================
model_name = getattr(settings, 'EMBEDDING_MODEL_NAME', 'pritamdeka/S-PubMedBert-MS-MARCO')
embedding_dim = getattr(settings, 'EMBEDDING_DIMENSION', 768)

model = SentenceTransformer(model_name)
print(f"Embedding model loaded: {model_name} (dimension: {embedding_dim})")

# ================================
# 6. 遍历 Product，生成向量
# ================================
products = Product.objects.all()
total = products.count()
print(f"共找到 {total} 个产品，准备生成向量...")

success_count = 0

for i, product in enumerate(products):
    try:
        # 获取或创建 ProductEmbedding
        pe, created = ProductEmbedding.objects.get_or_create(product=product)

        # 更新嵌入文本（使用模型中的方法）
        pe.update_embedding_text()
        text_to_embed = pe.embedding_text
        if not text_to_embed:
            # 回退：使用产品名称
            text_to_embed = product.product_name

        # 生成向量 (768维)
        vector_array = model.encode(text_to_embed)

        # 保存向量和模型信息
        pe.vector = json.dumps(vector_array.tolist())
        pe.model_name = model_name
        pe.dim = embedding_dim
        pe.save()

        success_count += 1
        if (i + 1) % 10 == 0:
            print(f"进度: {i + 1}/{total} 已完成")

    except Exception as e:
        print(f"❌ 处理出错 ID {product.product_id}: {str(e)}")

print(f"\n🎉 全部完成！成功更新了 {success_count} 个产品的向量。")
