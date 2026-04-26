#!/usr/bin/env python
"""
检查缺失的标签问题
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

def check_missing_tags():
    """检查缺失的标签"""
    print("检查缺失的标签问题")
    print("=" * 50)

    # 1. 查找所有引用的标签名称
    all_referenced_tags = set()

    # 从手工关联中收集
    for mapping in ProductTag.objects.select_related('tag').all():
        all_referenced_tags.add(mapping.tag.tag_name)

    # 从PubChem关联中收集
    for mapping in ProductPubChemTag.objects.select_related('pubchem_tag').all():
        all_referenced_tags.add(mapping.pubchem_tag.tag_name)

    print(f"总共引用的标签名称数量: {len(all_referenced_tags)}")

    # 2. 检查哪些标签名称在统一标签表中不存在
    missing_in_unified = []
    for tag_name in all_referenced_tags:
        if not UnifiedTag.objects.filter(tag_name=tag_name).exists():
            missing_in_unified.append(tag_name)

    print(f"在统一标签表中缺失的标签名称: {len(missing_in_unified)}")
    for tag_name in missing_in_unified[:20]:
        print(f"  '{tag_name}'")

    # 3. 检查这些缺失的标签在原始表中是否存在
    print("\n检查缺失标签在原始表中的情况:")
    for tag_name in missing_in_unified[:10]:
        print(f"\n标签名称: '{tag_name}'")

        # 检查手工标签表
        manual_tag = Tag.objects.filter(tag_name=tag_name).first()
        if manual_tag:
            print(f"  存在于手工标签表: ID={manual_tag.tag_id}, 类别={manual_tag.tag_category}")
        else:
            print(f"  不在手工标签表中")

        # 检查PubChem标签表
        pubchem_tags = PubChemTag.objects.filter(tag_name__icontains=tag_name)
        if pubchem_tags.exists():
            print(f"  在PubChem标签表中找到相关标签: {pubchem_tags.count()} 个")
            for tag in pubchem_tags[:2]:
                print(f"    ID={tag.tag_id}, 名称(前100字符): {tag.tag_name[:100]}...")
        else:
            # 尝试不区分大小写搜索
            pubchem_tags_icontains = PubChemTag.objects.filter(tag_name__icontains=tag_name.lower())
            if pubchem_tags_icontains.exists():
                print(f"  不区分大小写找到相关标签: {pubchem_tags_icontains.count()} 个")

    # 4. 检查具体的'pharmaceuticals'和'dyes'
    print("\n\n检查特定的问题标签:")
    for tag_name in ['pharmaceuticals', 'dyes', 'Pharmaceuticals', 'Dyes']:
        print(f"\n标签名称: '{tag_name}'")

        # 统一标签表
        unified_tag = UnifiedTag.objects.filter(tag_name=tag_name).first()
        if unified_tag:
            print(f"  统一标签: ID={unified_tag.id}, 来源={unified_tag.source}")
        else:
            print(f"  统一标签: 不存在")

        # 手工标签表
        manual_tag = Tag.objects.filter(tag_name=tag_name).first()
        if manual_tag:
            print(f"  手工标签: ID={manual_tag.tag_id}, 类别={manual_tag.tag_category}")
        else:
            # 尝试不区分大小写
            manual_tags_icontains = Tag.objects.filter(tag_name__icontains=tag_name.lower())
            if manual_tags_icontains.exists():
                print(f"  手工标签(不区分大小写): {manual_tags_icontains.count()} 个匹配")

        # PubChem标签表
        pubchem_tags = PubChemTag.objects.filter(tag_name__icontains=tag_name)
        if pubchem_tags.exists():
            print(f"  PubChem标签: {pubchem_tags.count()} 个匹配")
            for tag in pubchem_tags[:2]:
                print(f"    ID={tag.tag_id}, 名称(前100字符): {tag.tag_name[:100]}...")

    # 5. 统计受影响的关联数量
    print("\n\n受影响的关联统计:")
    problematic_mappings = []
    for mapping in ProductTag.objects.select_related('tag').all():
        tag_name = mapping.tag.tag_name
        if not UnifiedTag.objects.filter(tag_name=tag_name).exists():
            problematic_mappings.append((mapping.id, mapping.product_id, tag_name))

    print(f"有问题的手工关联数量: {len(problematic_mappings)}")
    for mapping_id, product_id, tag_name in problematic_mappings[:10]:
        print(f"  关联ID={mapping_id}, 产品ID={product_id}, 标签='{tag_name}'")

    # 分组统计
    from collections import Counter
    tag_name_counter = Counter(tag_name for _, _, tag_name in problematic_mappings)
    print(f"\n问题标签名称分布:")
    for tag_name, count in tag_name_counter.most_common():
        print(f"  '{tag_name}': {count} 个关联")

if __name__ == "__main__":
    check_missing_tags()