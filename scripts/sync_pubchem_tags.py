#!/usr/bin/env python
"""
为已有PubChem CID的产品创建PubChem标签
这个脚本会尝试为所有有CID但还没有PubChem标签的产品创建标签
"""
import os
import sys
import django
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import Product, YeastPubChemData, PubChemTag, ProductPubChemTag
from search_engine.management.commands.sync_pubchem import Command as SyncPubChemCommand

class PubChemTagSyncer:
    def __init__(self, use_proxy=None, delay=0.5, max_retries=3):
        self.sync_cmd = SyncPubChemCommand()
        self.use_proxy = use_proxy
        self.delay = delay
        self.max_retries = max_retries

    def get_products_needing_tags(self):
        """获取需要PubChem标签的产品"""
        # 获取有PubChem CID但没有PubChem标签的产品
        products = Product.objects.filter(
            pubchem_data__pubchem_cid__isnull=False,
            pubchem_data__sync_failed=False  # 只处理同步成功的
        ).exclude(
            pubchem_tags__isnull=False  # 排除已有标签的
        ).select_related('pubchem_data')

        return products

    def process_product(self, product, attempt=1):
        """为单个产品处理PubChem标签"""
        print(f"处理产品: {product.product_name} (CID: {product.pubchem_data.pubchem_cid})")

        try:
            # 尝试获取分类数据
            cid = product.pubchem_data.pubchem_cid
            classification_data = self.sync_cmd.get_pubchem_classification_data(cid)

            if classification_data:
                # 解析分类数据
                classifications, mesh_terms = self.sync_cmd.parse_classification_response(classification_data)

                if classifications or mesh_terms:
                    # 创建模拟化合物数据（因为我们已经有CID）
                    compound_data = {
                        'cid': cid,
                        'iupac_name': product.pubchem_data.iupac_name,
                        'description': product.pubchem_data.functional_description,
                        'classifications': classifications,
                        'mesh_terms': mesh_terms
                    }

                    # 更新标签
                    self.sync_cmd.update_pubchem_tags(product, compound_data)

                    print(f"  成功创建标签:")
                    if classifications:
                        print(f"    分类: {[c['name'] for c in classifications[:3]]}{'...' if len(classifications) > 3 else ''}")
                    if mesh_terms:
                        print(f"    MeSH: {[m['name'] for m in mesh_terms[:3]]}{'...' if len(mesh_terms) > 3 else ''}")

                    return True
                else:
                    print(f"  警告: 获取到分类数据但未解析出标签")
                    return False
            else:
                print(f"  警告: 无法获取分类数据")
                return False

        except Exception as e:
            print(f"  错误: {str(e)[:100]}")

            # 如果需要重试
            if attempt < self.max_retries:
                wait_time = self.delay * (2 ** (attempt - 1))
                print(f"  等待{wait_time:.1f}秒后重试 (尝试 {attempt}/{self.max_retries})")
                time.sleep(wait_time)
                return self.process_product(product, attempt + 1)
            else:
                # 标记为同步失败
                pubchem_data = product.pubchem_data
                pubchem_data.sync_failed = True
                pubchem_data.sync_failed_reason = f"标签创建失败: {str(e)[:200]}"
                pubchem_data.save()
                return False

    def run(self, limit=None, batch_size=50):
        """运行标签同步"""
        products = self.get_products_needing_tags()
        total = products.count()

        print(f"找到 {total} 个需要PubChem标签的产品")

        if limit:
            products = products[:limit]
            print(f"限制处理前 {limit} 个产品")

        success_count = 0
        fail_count = 0

        for i, product in enumerate(products):
            print(f"\n[{i+1}/{len(products)}] ", end="")

            if self.process_product(product):
                success_count += 1
            else:
                fail_count += 1

            # 批次延迟
            if i < len(products) - 1:
                time.sleep(self.delay)

            # 每batch_size个产品输出一次进度
            if (i + 1) % batch_size == 0:
                print(f"\n进度: {i+1}/{len(products)}，成功: {success_count}，失败: {fail_count}")

        print(f"\n{'='*50}")
        print(f"同步完成!")
        print(f"总处理: {len(products)}")
        print(f"成功: {success_count}")
        print(f"失败: {fail_count}")

        # 统计标签创建结果
        if success_count > 0:
            total_pubchem_tags = PubChemTag.objects.count()
            total_relations = ProductPubChemTag.objects.count()
            print(f"创建的PubChem标签总数: {total_pubchem_tags}")
            print(f"创建的产品-标签关联总数: {total_relations}")

def test_with_mock_data():
    """使用模拟数据测试标签创建"""
    print("=== 使用模拟数据测试标签创建 ===")

    # 获取一个测试产品
    test_product = Product.objects.filter(
        pubchem_data__pubchem_cid__isnull=False
    ).first()

    if not test_product:
        print("没有找到有CID的测试产品")
        return

    print(f"测试产品: {test_product.product_name}")
    print(f"CID: {test_product.pubchem_data.pubchem_cid}")

    # 创建模拟分类数据
    mock_classifications = [
        {'name': 'Organic compounds', 'category': 'superclass', 'type': 'chemical', 'confidence': 1.0},
        {'name': 'Benzenoids', 'category': 'class', 'type': 'chemical', 'confidence': 1.0}
    ]

    mock_mesh_terms = [
        {'name': 'Phenols', 'id': 'D010636', 'category': 'mesh'},
        {'name': 'Antioxidants', 'id': 'D059808', 'category': 'mesh'}
    ]

    # 创建模拟化合物数据
    mock_compound_data = {
        'cid': test_product.pubchem_data.pubchem_cid,
        'iupac_name': test_product.pubchem_data.iupac_name or 'Mock IUPAC',
        'description': test_product.pubchem_data.functional_description or 'Mock description',
        'classifications': mock_classifications,
        'mesh_terms': mock_mesh_terms
    }

    # 导入sync_pubchem命令
    from search_engine.management.commands.sync_pubchem import Command as SyncPubChemCommand
    sync_cmd = SyncPubChemCommand()

    try:
        # 调用update_pubchem_tags
        print("正在创建模拟标签...")
        sync_cmd.update_pubchem_tags(test_product, mock_compound_data)
        print("模拟标签创建成功!")

        # 检查结果
        tags = test_product.pubchem_tags.all()
        print(f"创建的标签数量: {tags.count()}")
        for tag in tags:
            print(f"  - {tag.tag_name} (类别: {tag.tag_category})")

        # 清理测试数据（可选）
        clean_test = input("\n是否清理测试数据? (y/n): ").lower() == 'y'
        if clean_test:
            test_product.pubchem_tags.clear()
            # 删除创建的标签
            PubChemTag.objects.filter(tag_name__in=['Organic compounds', 'Benzenoids', 'Phenols', 'Antioxidants']).delete()
            print("测试数据已清理")

    except Exception as e:
        print(f"模拟标签创建失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主函数"""
    print("PubChem标签同步工具")
    print("=" * 50)

    # 检查当前状态
    products_with_cid = Product.objects.filter(pubchem_data__pubchem_cid__isnull=False).count()
    products_with_tags = Product.objects.filter(pubchem_tags__isnull=False).distinct().count()
    total_pubchem_tags = PubChemTag.objects.count()

    print(f"有CID的产品: {products_with_cid}")
    print(f"有PubChem标签的产品: {products_with_tags}")
    print(f"PubChem标签总数: {total_pubchem_tags}")

    print("\n选项:")
    print("1. 运行实际同步（需要网络连接）")
    print("2. 使用模拟数据测试")
    print("3. 检查状态")

    choice = input("\n请选择 (1/2/3): ").strip()

    if choice == '1':
        # 运行实际同步
        proxy = input("代理地址 (留空为无代理): ").strip() or None
        limit_input = input("处理数量限制 (留空为全部): ").strip()
        limit = int(limit_input) if limit_input else None

        syncer = PubChemTagSyncer(use_proxy=proxy)
        syncer.run(limit=limit)

    elif choice == '2':
        # 模拟数据测试
        test_with_mock_data()

    elif choice == '3':
        # 检查状态
        print("\n当前状态:")

        # 详细统计
        from django.db.models import Count
        products_with_cid_details = Product.objects.filter(
            pubchem_data__pubchem_cid__isnull=False
        ).annotate(
            tag_count=Count('pubchem_tags')
        )

        no_tags = products_with_cid_details.filter(tag_count=0).count()
        has_tags = products_with_cid_details.filter(tag_count__gt=0).count()

        print(f"有CID的产品总数: {products_with_cid}")
        print(f"  - 有标签: {has_tags}")
        print(f"  - 无标签: {no_tags}")

        if no_tags > 0:
            print(f"\n前10个无标签的产品:")
            for product in products_with_cid_details.filter(tag_count=0)[:10]:
                print(f"  - {product.product_name} (CID: {product.pubchem_data.pubchem_cid})")

    else:
        print("无效选择")

if __name__ == "__main__":
    main()