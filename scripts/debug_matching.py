#!/usr/bin/env python
"""
调试标签名称匹配问题
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

def debug_pharmaceuticals():
    """调试'pharmaceuticals'标签匹配问题"""
    print("调试'pharmaceuticals'标签匹配")
    print("=" * 50)

    # 1. 查找所有'pharmaceuticals'标签
    tag_name = 'pharmaceuticals'

    print(f"查找标签名称: '{tag_name}'")

    # 在手工标签表中
    manual_tags = Tag.objects.filter(tag_name=tag_name)
    print(f"手工标签表中: {manual_tags.count()} 个")
    for tag in manual_tags:
        print(f"  ID={tag.tag_id}, 名称='{tag.tag_name}', 类别={tag.tag_category}")

    # 在统一标签表中
    unified_tags = UnifiedTag.objects.filter(tag_name=tag_name)
    print(f"统一标签表中: {unified_tags.count()} 个")
    for tag in unified_tags:
        print(f"  ID={tag.id}, 名称='{tag.tag_name}', 来源={tag.source}, 原始ID={tag.original_tag_id}, 原始类型={tag.original_source_type}")

    # 2. 检查关联
    print(f"\n检查产品ID 24 的关联:")

    # 原始手工关联
    manual_mappings = ProductTag.objects.filter(product_id=24, tag__tag_name=tag_name)
    print(f"原始手工关联: {manual_mappings.count()} 个")
    for mapping in manual_mappings:
        print(f"  关联ID={mapping.id}, 产品ID={mapping.product_id}, 标签ID={mapping.tag_id}")

    # 统一关联
    unified_tag = unified_tags.first()
    if unified_tag:
        unified_mappings = UnifiedProductTagMapping.objects.filter(
            product_id=24,
            tag_id=unified_tag.id
        )
        print(f"统一关联: {unified_mappings.count()} 个")
        for mapping in unified_mappings:
            print(f"  关联ID={mapping.id}, 产品ID={mapping.product_id}, 标签ID={mapping.tag_id}, 原始类型={mapping.original_source_type}")

    # 3. 模拟迁移脚本中的字典查找
    print(f"\n模拟迁移脚本中的字典查找:")

    # 构建字典
    tag_name_to_unified_id = {}
    for unified_tag in UnifiedTag.objects.all():
        tag_name_to_unified_id[unified_tag.tag_name] = unified_tag.id

    print(f"字典大小: {len(tag_name_to_unified_id)}")

    # 查找'pharmaceuticals'
    unified_id = tag_name_to_unified_id.get(tag_name)
    if unified_id:
        print(f"在字典中找到 '{tag_name}': ID={unified_id}")
    else:
        print(f"在字典中未找到 '{tag_name}'")
        # 检查是否有相似的键
        similar_keys = [k for k in tag_name_to_unified_id.keys() if tag_name.lower() in k.lower()]
        print(f"相似的键 ({len(similar_keys)} 个):")
        for key in similar_keys[:5]:
            print(f"  '{key}' -> ID={tag_name_to_unified_id[key]}")

    # 4. 检查字符串表示
    print(f"\n字符串表示检查:")
    unified_tag = unified_tags.first()
    if unified_tag:
        print(f"统一标签名称: '{unified_tag.tag_name}'")
        print(f"统一标签名称长度: {len(unified_tag.tag_name)}")
        print(f"统一标签名称repr: {repr(unified_tag.tag_name)}")

        # 检查是否有不可见字符
        for i, char in enumerate(unified_tag.tag_name):
            if ord(char) < 32 or ord(char) > 126:
                print(f"  位置 {i}: 字符 '{char}' (ord={ord(char)})")

def check_all_problematic():
    """检查所有有问题的关联"""
    print("\n\n检查所有有问题的关联")
    print("=" * 50)

    # 从验证输出中获取有问题的关联
    problematic = [
        (24, 'pharmaceuticals'),
        (797, 'pharmaceuticals'),
        (913, 'pharmaceuticals'),
        (1030, 'pharmaceuticals'),
        (1560, 'pharmaceuticals'),
        (1586, 'pharmaceuticals'),
        (1956, 'pharmaceuticals'),
        (1994, 'pharmaceuticals'),
        (1994, 'dyes'),
        (2049, 'pharmaceuticals'),
        (4007, 'pharmaceuticals'),
        (6255, 'pharmaceuticals'),
    ]

    for product_id, tag_name in problematic:
        print(f"\n产品ID: {product_id}, 标签名称: '{tag_name}'")

        # 查找统一标签
        unified_tag = UnifiedTag.objects.filter(tag_name=tag_name).first()
        if unified_tag:
            print(f"  统一标签: ID={unified_tag.id}")

            # 检查是否有统一关联
            unified_mapping = UnifiedProductTagMapping.objects.filter(
                product_id=product_id,
                tag_id=unified_tag.id
            ).first()

            if unified_mapping:
                print(f"  统一关联: 存在 (ID={unified_mapping.id})")
            else:
                print(f"  统一关联: 不存在")
        else:
            print(f"  统一标签: 未找到")

if __name__ == "__main__":
    debug_pharmaceuticals()
    check_all_problematic()