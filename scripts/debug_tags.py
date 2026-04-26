#!/usr/bin/env python
"""
调试标签迁移问题的脚本
"""
import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import (
    Tag, ProductTag,
    PubChemTag, ProductPubChemTag,
    UnifiedTag, UnifiedProductTagMapping
)

def analyze_tags():
    """分析标签数据"""
    print("标签数据分析")
    print("=" * 50)

    # 1. 统计标签数量
    manual_tags = Tag.objects.all()
    pubchem_tags = PubChemTag.objects.all()
    unified_tags = UnifiedTag.objects.all()

    print(f"手工标签数量: {manual_tags.count()}")
    print(f"PubChem标签数量: {pubchem_tags.count()}")
    print(f"统一标签数量: {unified_tags.count()}")

    # 2. 查找重复标签名称
    print("\n查找重复标签名称:")

    # 手工标签中的重复名称
    manual_tag_names = {}
    for tag in manual_tags:
        if tag.tag_name in manual_tag_names:
            manual_tag_names[tag.tag_name].append(tag.tag_id)
        else:
            manual_tag_names[tag.tag_name] = [tag.tag_id]

    manual_duplicates = {k: v for k, v in manual_tag_names.items() if len(v) > 1}
    print(f"手工标签中的重复名称: {len(manual_duplicates)}")
    for name, ids in list(manual_duplicates.items())[:5]:
        print(f"  {name}: {ids}")

    # PubChem标签中的重复名称
    pubchem_tag_names = {}
    for tag in pubchem_tags:
        if tag.tag_name in pubchem_tag_names:
            pubchem_tag_names[tag.tag_name].append(tag.tag_id)
        else:
            pubchem_tag_names[tag.tag_name] = [tag.tag_id]

    pubchem_duplicates = {k: v for k, v in pubchem_tag_names.items() if len(v) > 1}
    print(f"PubChem标签中的重复名称: {len(pubchem_duplicates)}")
    for name, ids in list(pubchem_duplicates.items())[:5]:
        print(f"  {name}: {ids}")

    # 统一标签中的重复名称
    unified_tag_names = {}
    for tag in unified_tags:
        if tag.tag_name in unified_tag_names:
            unified_tag_names[tag.tag_name].append(tag.id)
        else:
            unified_tag_names[tag.tag_name] = [tag.id]

    unified_duplicates = {k: v for k, v in unified_tag_names.items() if len(v) > 1}
    print(f"统一标签中的重复名称: {len(unified_duplicates)}")
    for name, ids in list(unified_duplicates.items())[:5]:
        print(f"  {name}: {ids}")

    # 3. 检查哪些手工标签没有对应的统一标签
    print("\n手工标签未找到统一标签的情况:")
    missing_manual = 0
    for tag in manual_tags[:20]:  # 只检查前20个
        unified_tag = UnifiedTag.objects.filter(tag_name=tag.tag_name).first()
        if not unified_tag:
            print(f"  '{tag.tag_name}' (ID: {tag.tag_id})")
            missing_manual += 1

    if missing_manual > 20:
        print(f"  还有 {missing_manual - 20} 个未显示...")

    # 4. 检查哪些PubChem标签没有对应的统一标签
    print("\nPubChem标签未找到统一标签的情况:")
    missing_pubchem = 0
    for tag in pubchem_tags:
        unified_tag = UnifiedTag.objects.filter(tag_name=tag.tag_name).first()
        if not unified_tag:
            print(f"  '{tag.tag_name}' (ID: {tag.tag_id})")
            missing_pubchem += 1

    # 5. 检查统一标签的来源分布
    print("\n统一标签来源分布:")
    from django.db.models import Count
    source_stats = UnifiedTag.objects.values('source').annotate(
        count=Count('id')
    ).order_by('-count')

    for stat in source_stats:
        print(f"  {stat['source']}: {stat['count']}")

    # 6. 示例查看几个具体的标签
    print("\n示例标签详情:")
    sample_tags = ['Dyes', 'Pharmaceuticals', 'monoterpenoid', 'antioxidant']
    for tag_name in sample_tags:
        print(f"\n标签名称: '{tag_name}'")

        # 查找手工标签
        manual_tag = Tag.objects.filter(tag_name=tag_name).first()
        if manual_tag:
            print(f"  手工标签: ID={manual_tag.tag_id}, 类别={manual_tag.tag_category}")

        # 查找PubChem标签
        pubchem_tag = PubChemTag.objects.filter(tag_name=tag_name).first()
        if pubchem_tag:
            print(f"  PubChem标签: ID={pubchem_tag.tag_id}, 类别={pubchem_tag.tag_category}")

        # 查找统一标签
        unified_tag = UnifiedTag.objects.filter(tag_name=tag_name).first()
        if unified_tag:
            print(f"  统一标签: ID={unified_tag.id}, 来源={unified_tag.source}, 原始ID={unified_tag.original_tag_id}, 原始类型={unified_tag.original_source_type}")
        else:
            print(f"  统一标签: 未找到")

def test_migration_logic():
    """测试迁移逻辑"""
    print("\n\n迁移逻辑测试")
    print("=" * 50)

    # 测试情况1: 手工标签，无重复
    tag_name = "test_unique_manual_tag"
    print(f"\n测试情况1: 标签 '{tag_name}' (仅手工)")

    # 模拟迁移逻辑
    manual_tag = Tag.objects.filter(tag_name=tag_name).first()
    if manual_tag:
        existing = UnifiedTag.objects.filter(tag_name=tag_name).first()
        if existing:
            if existing.source != 'pubchem_api':
                print(f"  逻辑: 更新现有标签的原始信息")
                # 这里应该更新 original_tag_id 和 original_source_type
            else:
                print(f"  逻辑: 已存在PubChem来源的标签，跳过更新")
        else:
            print(f"  逻辑: 创建新的统一标签 (source='manual')")

    # 测试情况2: PubChem标签，无重复
    tag_name = "test_unique_pubchem_tag"
    print(f"\n测试情况2: 标签 '{tag_name}' (仅PubChem)")

    pubchem_tag = PubChemTag.objects.filter(tag_name=tag_name).first()
    if pubchem_tag:
        existing = UnifiedTag.objects.filter(tag_name=tag_name).first()
        if existing:
            print(f"  逻辑: 更新为PubChem来源")
            # 这里应该更新为 pubchem_api 来源
        else:
            print(f"  逻辑: 创建新的统一标签 (source='pubchem_api')")

    # 测试情况3: 两者都有（重复）
    tag_name = "test_duplicate_tag"
    print(f"\n测试情况3: 标签 '{tag_name}' (手工和PubChem都有)")

    manual_tag = Tag.objects.filter(tag_name=tag_name).first()
    pubchem_tag = PubChemTag.objects.filter(tag_name=tag_name).first()

    if manual_tag and pubchem_tag:
        existing = UnifiedTag.objects.filter(tag_name=tag_name).first()
        if existing:
            print(f"  逻辑: 优先保留PubChem标签")
            # 来源应该保持为 pubchem_api
        else:
            print(f"  逻辑: 创建PubChem来源的统一标签")
            # 应该创建 pubchem_api 来源的标签

if __name__ == "__main__":
    analyze_tags()
    test_migration_logic()