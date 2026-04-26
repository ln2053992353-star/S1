import json
import time
from django.core.management.base import BaseCommand
# 使用延迟导入防止循环引用
from django.apps import apps
from sentence_transformers import SentenceTransformer


class Command(BaseCommand):
    help = 'Generate embeddings using local PubMedBert'

    def handle(self, *args, **options):
        # 1. 延迟获取模型类
        Product = apps.get_model('search_engine', 'Product')
        ProductEmbedding = apps.get_model('search_engine', 'ProductEmbedding')

        self.stdout.write("🚀 Loading local PubMedBert model...")
        model = SentenceTransformer('pritamdeka/S-PubMedBert-MS-MARCO')

        products = Product.objects.all()
        count = products.count()
        self.stdout.write(f"Processing {count} products...")

        for i, prod in enumerate(products):
            try:
                # 获取或创建
                embedding_obj, created = ProductEmbedding.objects.get_or_create(product=prod)

                # 准备文本: 优先用 description
                text_content = prod.description if prod.description else prod.product_name
                # 简单清洗
                text_content = text_content[:1000] if text_content else ""

                # 填入基准文本
                embedding_obj.function = text_content
                embedding_obj.update_embedding_text()  # 自动加上 Tag

                # 生成向量 (768维)
                vector = model.encode(embedding_obj.embedding_text).tolist()

                # 保存
                embedding_obj.vector = json.dumps(vector)
                embedding_obj.dim = 768
                embedding_obj.model_name = "S-PubMedBert-MS-MARCO"
                embedding_obj.save()

                if i % 10 == 0:
                    self.stdout.write(f"[{i}/{count}] Updated: {prod.product_name}")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error {prod.product_name}: {e}"))


