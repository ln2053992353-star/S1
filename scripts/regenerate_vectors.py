import os
import sys
import json
import django
from sentence_transformers import SentenceTransformer

# 1. Django 环境初始化
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

# 导入Django settings
from django.conf import settings

# 2. 安全获取模型 (★ 修正点：指向 search_engine)
from django.apps import apps

try:
    # 既然您的模型定义在 search_engine/models.py
    # 这里必须写 'search_engine'，而不是 'database'
    Product = apps.get_model('search_engine', 'Product')
    ProductEmbedding = apps.get_model('search_engine', 'ProductEmbedding')
    print("✅ 成功加载模型！")
except LookupError as e:
    print(f"❌ 无法加载模型: {e}")
    sys.exit(1)


def regenerate_all():
    # 3. 加载嵌入模型（从settings获取配置）
    model_name = getattr(settings, 'EMBEDDING_MODEL_NAME', 'pritamdeka/S-PubMedBert-MS-MARCO')
    embedding_dim = getattr(settings, 'EMBEDDING_DIMENSION', 768)

    print(f"正在加载模型: {model_name} ...")
    model = SentenceTransformer(model_name)

    products = Product.objects.all()
    total = products.count()
    print(f"共找到 {total} 个产品，准备重新生成向量...")

    success_count = 0

    for i, product in enumerate(products):
        try:
            # A. 获取或创建 Embedding
            pe, created = ProductEmbedding.objects.get_or_create(product=product)

            # B. 重新生成文本 (调用您模型里的方法)
            pe.update_embedding_text()
            text_to_embed = pe.embedding_text
            if not text_to_embed:
                text_to_embed = product.product_name

            # C. 生成向量
            vector_array = model.encode(text_to_embed)

            # D. 保存 (更新模型名为全称，方便以后追踪)
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


if __name__ == "__main__":
    regenerate_all()