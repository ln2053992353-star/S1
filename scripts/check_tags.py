#!/usr/bin/env python
import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import Tag, PubChemTag, Product, ProductPubChemTag

def check_tags():
    print("检查标签数据...")

    # 检查普通标签
    tags = Tag.objects.all()[:10]
    print(f"普通标签数量: {Tag.objects.count()}")
    print("前10个普通标签:")
    for tag in tags:
        print(f"  ID: {tag.tag_id}, 名称: {tag.tag_name}, 类别: {tag.tag_category}")

    # 检查PubChem标签
    pubchem_tags = PubChemTag.objects.all()[:10]
    print(f"\nPubChem标签数量: {PubChemTag.objects.count()}")
    print("前10个PubChem标签:")
    for tag in pubchem_tags:
        print(f"  ID: {tag.tag_id}, 名称: {tag.tag_name}, 类别: {tag.tag_category}, 分类: {tag.pubchem_classification}")

    # 检查产品标签关联
    product_tags = Product.objects.filter(tags__isnull=False).distinct()[:5]
    print(f"\n拥有标签的产品数量: {Product.objects.filter(tags__isnull=False).distinct().count()}")
    for product in product_tags:
        tags = product.tags.all()
        print(f"  产品: {product.product_name}, 标签: {[t.tag_name for t in tags]}")

    # 检查产品PubChem标签关联
    product_pubchem_tags = Product.objects.filter(pubchem_tags__isnull=False).distinct()[:5]
    print(f"\n拥有PubChem标签的产品数量: {Product.objects.filter(pubchem_tags__isnull=False).distinct().count()}")
    for product in product_pubchem_tags:
        tags = product.pubchem_tags.all()
        print(f"  产品: {product.product_name}, PubChem标签: {[t.tag_name for t in tags]}")

if __name__ == "__main__":
    check_tags()