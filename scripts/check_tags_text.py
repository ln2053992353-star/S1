#!/usr/bin/env python
import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import ProductEmbedding

def check_tags_text():
    print("检查ProductEmbedding中的tags_text字段...")

    embeddings = ProductEmbedding.objects.filter(tags_text__isnull=False)[:20]
    total_with_tags = ProductEmbedding.objects.filter(tags_text__isnull=False).count()
    total_embeddings = ProductEmbedding.objects.count()

    print(f"ProductEmbedding总数: {total_embeddings}")
    print(f"具有tags_text的嵌入数: {total_with_tags} ({total_with_tags/total_embeddings*100:.1f}%)")

    print("\ntags_text示例:")
    for emb in embeddings:
        print(f"  产品: {emb.product.product_name}")
        print(f"  tags_text: '{emb.tags_text}'")
        print()

    # 检查tags_text是否包含原始标签数据
    # 查看是否有未解析的原始文本
    print("\n检查可能包含原始标签文本的嵌入...")
    raw_patterns = [';', ',', '|', '\\n']
    for pattern in raw_patterns:
        count = ProductEmbedding.objects.filter(tags_text__contains=pattern).count()
        print(f"  包含'{pattern}'的tags_text数量: {count}")

if __name__ == "__main__":
    check_tags_text()