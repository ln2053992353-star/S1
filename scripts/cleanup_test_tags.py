#!/usr/bin/env python
"""
清理测试创建的PubChem标签
"""
import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import PubChemTag, ProductPubChemTag, Product

def cleanup_test_tags():
    """清理测试标签"""
    # 测试标签名称
    test_tag_names = ['Organic compounds', 'Benzenoids', 'Phenols', 'Antioxidants']

    # 查找并删除测试标签
    test_tags = PubChemTag.objects.filter(tag_name__in=test_tag_names)
    tag_count = test_tags.count()

    if tag_count > 0:
        print(f"找到 {tag_count} 个测试标签:")
        for tag in test_tags:
            print(f"  - {tag.tag_name} (ID: {tag.tag_id})")

        # 先删除关联
        ProductPubChemTag.objects.filter(pubchem_tag__in=test_tags).delete()
        print(f"删除了关联记录")

        # 删除标签
        deleted_count, _ = test_tags.delete()
        print(f"删除了 {deleted_count} 个测试标签")
    else:
        print("没有找到测试标签")

    # 清理Alpha-Terpineol的标签关联
    alpha_product = Product.objects.filter(product_name='Alpha-Terpineol').first()
    if alpha_product:
        tag_count = alpha_product.pubchem_tags.count()
        if tag_count > 0:
            alpha_product.pubchem_tags.clear()
            print(f"清理了 Alpha-Terpineol 的 {tag_count} 个标签关联")

    # 最终统计
    total_tags = PubChemTag.objects.count()
    total_relations = ProductPubChemTag.objects.count()
    products_with_tags = Product.objects.filter(pubchem_tags__isnull=False).distinct().count()

    print(f"\n清理后状态:")
    print(f"PubChem标签总数: {total_tags}")
    print(f"产品-标签关联总数: {total_relations}")
    print(f"有PubChem标签的产品数: {products_with_tags}")

if __name__ == "__main__":
    cleanup_test_tags()