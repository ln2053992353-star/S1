#!/usr/bin/env python
import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import YeastPubChemData, Product, PubChemTag, ProductPubChemTag

def check_pubchem_status():
    print("检查PubChem数据状态...")

    # 检查YeastPubChemData记录
    pubchem_data = YeastPubChemData.objects.all()
    total_products = Product.objects.count()
    total_pubchem = pubchem_data.count()
    print(f"产品总数: {total_products}")
    print(f"有PubChem数据记录的产品: {total_pubchem} ({total_pubchem/total_products*100:.1f}%)")

    # 检查有CID的产品
    with_cid = pubchem_data.filter(pubchem_cid__isnull=False).count()
    print(f"有PubChem CID的产品: {with_cid} ({with_cid/total_pubchem*100:.1f}%)")

    # 检查同步失败的产品
    failed = pubchem_data.filter(sync_failed=True).count()
    print(f"同步失败的产品: {failed}")

    # 检查PubChem标签
    pubchem_tags = PubChemTag.objects.count()
    print(f"PubChem标签数量: {pubchem_tags}")

    # 检查产品与PubChem标签的关联
    product_pubchem_tags = ProductPubChemTag.objects.count()
    print(f"产品-PubChem标签关联数量: {product_pubchem_tags}")

    # 检查有PubChem标签的产品
    products_with_pubchem_tags = Product.objects.filter(pubchem_tags__isnull=False).distinct().count()
    print(f"有PubChem标签的产品: {products_with_pubchem_tags}")

    # 显示一些有CID但无标签的产品示例
    print("\n有CID但无PubChem标签的产品示例:")
    products_with_cid_no_tags = Product.objects.filter(
        pubchem_data__pubchem_cid__isnull=False,
        pubchem_tags__isnull=True
    )[:10]
    for product in products_with_cid_no_tags:
        cid = product.pubchem_data.pubchem_cid
        print(f"  产品: {product.product_name}, CID: {cid}")

    # 显示一些有标签的产品示例
    if products_with_pubchem_tags > 0:
        print("\n有PubChem标签的产品示例:")
        products_with_tags = Product.objects.filter(pubchem_tags__isnull=False).distinct()[:5]
        for product in products_with_tags:
            tags = product.pubchem_tags.all()
            print(f"  产品: {product.product_name}, 标签: {[t.tag_name for t in tags]}")

if __name__ == "__main__":
    check_pubchem_status()