#!/usr/bin/env python
"""
验证统一标签系统数据完整性的脚本
"""
import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from django.db.models import Count
from search_engine.models import (
    Tag, ProductTag,
    PubChemTag, ProductPubChemTag,
    UnifiedTag, UnifiedProductTagMapping, Product
)

def validate_data_integrity():
    """验证数据完整性"""
    print("统一标签系统数据完整性验证")
    print("=" * 50)

    all_valid = True

    # 1. 验证标签迁移完整性
    print("\n1. 标签迁移完整性验证:")

    # 检查所有手工标签是否都有对应的统一标签
    manual_tags = Tag.objects.all()
    for tag in manual_tags:
        unified_tag = UnifiedTag.objects.filter(tag_name=tag.tag_name).first()

        if not unified_tag:
            print(f"  [ERROR] 手工标签 '{tag.tag_name}' (ID: {tag.tag_id}) 未找到对应的统一标签")
            all_valid = False

    # 检查所有PubChem标签是否都有对应的统一标签
    pubchem_tags = PubChemTag.objects.all()
    for tag in pubchem_tags:
        unified_tag = UnifiedTag.objects.filter(tag_name=tag.tag_name).first()

        if not unified_tag:
            print(f"  [ERROR] PubChem标签 '{tag.tag_name}' (ID: {tag.tag_id}) 未找到对应的统一标签")
            all_valid = False

    if all_valid:
        print("  [OK] 所有标签都已正确迁移")

    # 2. 验证关联迁移完整性
    print("\n2. 关联迁移完整性验证:")

    # 检查手工标签关联
    manual_mappings = ProductTag.objects.select_related('tag').all()
    for mapping in manual_mappings:
        unified_tag = UnifiedTag.objects.filter(tag_name=mapping.tag.tag_name).first()
        if unified_tag:
            unified_mapping = UnifiedProductTagMapping.objects.filter(
                product_id=mapping.product_id,
                tag_id=unified_tag.id
            ).first()

            if not unified_mapping:
                print(f"  [ERROR] 手工关联 产品:{mapping.product_id}->标签:{mapping.tag.tag_name} 未迁移")
                all_valid = False

    # 检查PubChem标签关联
    pubchem_mappings = ProductPubChemTag.objects.select_related('pubchem_tag').all()
    for mapping in pubchem_mappings:
        unified_tag = UnifiedTag.objects.filter(tag_name=mapping.pubchem_tag.tag_name).first()
        if unified_tag:
            unified_mapping = UnifiedProductTagMapping.objects.filter(
                product_id=mapping.product_id,
                tag_id=unified_tag.id
            ).first()

            if not unified_mapping:
                print(f"  [ERROR] PubChem关联 产品:{mapping.product_id}->标签:{mapping.pubchem_tag.tag_name} 未迁移")
                all_valid = False

    if all_valid:
        print("  [OK] 所有关联都已正确迁移")

    # 3. 验证数据一致性
    print("\n3. 数据一致性验证:")

    # 检查重复标签
    duplicate_tags = UnifiedTag.objects.values('tag_name').annotate(
        count=Count('id')
    ).filter(count__gt=1)

    if duplicate_tags.exists():
        print(f"  [ERROR] 发现 {duplicate_tags.count()} 个重复标签名称")
        for dup in duplicate_tags:
            tags = UnifiedTag.objects.filter(tag_name=dup['tag_name'])
            print(f"    标签 '{dup['tag_name']}' 有 {dup['count']} 个实例:")
            for tag in tags:
                print(f"      ID:{tag.id}, 来源:{tag.source}, 原始类型:{tag.original_source_type}")
        all_valid = False
    else:
        print("  [OK] 无重复标签名称")

    # 检查重复关联
    duplicate_mappings = UnifiedProductTagMapping.objects.values(
        'product_id', 'tag_id'
    ).annotate(
        count=Count('id')
    ).filter(count__gt=1)

    if duplicate_mappings.exists():
        print(f"  [ERROR] 发现 {duplicate_mappings.count()} 个重复产品-标签关联")
        all_valid = False
    else:
        print("  [OK] 无重复产品-标签关联")

    # 4. 验证外键约束
    print("\n4. 外键约束验证:")

    # 检查所有关联都有有效的产品和标签
    invalid_product_refs = UnifiedProductTagMapping.objects.filter(
        product__isnull=True
    ).count()

    invalid_tag_refs = UnifiedProductTagMapping.objects.filter(
        tag__isnull=True
    ).count()

    if invalid_product_refs > 0:
        print(f"  [ERROR] 发现 {invalid_product_refs} 个无效的产品引用")
        all_valid = False
    else:
        print("  [OK] 所有产品引用有效")

    if invalid_tag_refs > 0:
        print(f"  [ERROR] 发现 {invalid_tag_refs} 个无效的标签引用")
        all_valid = False
    else:
        print("  [OK] 所有标签引用有效")

    # 5. 统计信息
    print("\n5. 统计信息:")
    print(f"  统一标签总数: {UnifiedTag.objects.count()}")
    print(f"  统一关联总数: {UnifiedProductTagMapping.objects.count()}")

    # 按来源统计
    source_stats = UnifiedTag.objects.values('source').annotate(
        count=Count('id')
    ).order_by('-count')

    print("  标签来源分布:")
    for stat in source_stats:
        print(f"    {stat['source']}: {stat['count']}")

    # 按置信度分布统计
    confidence_stats = UnifiedProductTagMapping.objects.values(
        'confidence_score'
    ).annotate(
        count=Count('id')
    ).order_by('confidence_score')

    print("  置信度分布:")
    for stat in confidence_stats:
        print(f"    {stat['confidence_score']}: {stat['count']}")

    return all_valid

def test_unified_queries():
    """测试统一标签系统的查询功能"""
    print("\n6. 查询功能测试:")

    # 测试1: 按标签名称查询
    test_tag_name = "antioxidant"
    unified_tags = UnifiedTag.objects.filter(tag_name__icontains=test_tag_name)
    print(f"  测试1 - 查询包含 '{test_tag_name}' 的标签:")
    for tag in unified_tags[:3]:  # 只显示前3个
        print(f"    {tag.tag_name} (来源: {tag.source})")

    # 测试2: 按产品查询标签
    test_product_id = 1
    product_mappings = UnifiedProductTagMapping.objects.filter(
        product_id=test_product_id
    ).select_related('tag')

    print(f"\n  测试2 - 查询产品ID {test_product_id} 的标签:")
    for mapping in product_mappings[:5]:  # 只显示前5个
        print(f"    {mapping.tag.tag_name} (置信度: {mapping.confidence_score})")

    # 测试3: 按置信度筛选
    high_confidence_mappings = UnifiedProductTagMapping.objects.filter(
        confidence_score__gte=0.8
    ).count()

    print(f"\n  测试3 - 高置信度(≥0.8)关联数: {high_confidence_mappings}")

    print("  [OK] 查询功能测试完成")

def main():
    """主函数"""
    print("统一标签系统数据验证工具")
    print("=" * 50)

    try:
        # 执行完整性验证
        if validate_data_integrity():
            print("\n[SUCCESS] 所有验证通过!")
        else:
            print("\n[ERROR] 验证失败，请修复上述问题")

        # 执行查询测试
        test_unified_queries()

    except Exception as e:
        print(f"\n[ERROR] 验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()