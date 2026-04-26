#!/usr/bin/env python
"""
将现有标签系统迁移到统一标签系统的数据迁移脚本
"""
import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from django.db import transaction
from search_engine.models import (
    Tag, ProductTag,
    PubChemTag, ProductPubChemTag,
    UnifiedTag, UnifiedProductTagMapping
)

def migrate_tags():
    """迁移标签数据"""
    print("开始迁移标签数据...")

    # 先迁移PubChem标签（优先保留PubChem标签）
    pubchem_tags_migrated = 0
    pubchem_tags_skipped = 0

    for tag in PubChemTag.objects.all():
        # 检查是否已存在相同名称的标签
        existing = UnifiedTag.objects.filter(tag_name=tag.tag_name).first()

        if existing:
            # 如果已存在，更新为PubChem来源（优先保留PubChem标签）
            existing.source = 'pubchem_api'
            existing.tag_category = existing.tag_category or tag.tag_category
            existing.pubchem_classification = tag.pubchem_classification
            existing.mesh_id = tag.mesh_id
            existing.original_tag_id = tag.tag_id
            existing.original_source_type = 'pubchem_tag'
            existing.save()
            pubchem_tags_skipped += 1
        else:
            # 创建新的统一标签
            UnifiedTag.objects.create(
                tag_name=tag.tag_name,
                tag_category=tag.tag_category,
                source='pubchem_api',
                original_tag_id=tag.tag_id,
                original_source_type='pubchem_tag',
                pubchem_classification=tag.pubchem_classification,
                mesh_id=tag.mesh_id
            )
            pubchem_tags_migrated += 1

    print(f"PubChem标签迁移完成: 新增 {pubchem_tags_migrated} 个, 更新 {pubchem_tags_skipped} 个")

    # 再迁移手工标签
    manual_tags_migrated = 0
    manual_tags_skipped = 0

    for tag in Tag.objects.all():
        # 检查是否已存在相同名称的标签
        existing = UnifiedTag.objects.filter(tag_name=tag.tag_name).first()

        if existing:
            # 如果已存在，检查是否是PubChem标签
            if existing.source == 'pubchem_api':
                # 如果是PubChem标签，只更新原始信息，保持来源不变
                if not existing.original_tag_id:
                    existing.original_tag_id = tag.tag_id
                    existing.original_source_type = 'manual_tag'
                    existing.save()
                manual_tags_skipped += 1
            else:
                # 如果是手工标签，更新原始信息
                existing.original_tag_id = tag.tag_id
                existing.original_source_type = 'manual_tag'
                existing.save()
                manual_tags_skipped += 1
        else:
            # 创建新的统一标签
            UnifiedTag.objects.create(
                tag_name=tag.tag_name,
                tag_category=tag.tag_category,
                source='manual',
                original_tag_id=tag.tag_id,
                original_source_type='manual_tag'
            )
            manual_tags_migrated += 1

    print(f"手工标签迁移完成: 新增 {manual_tags_migrated} 个, 跳过 {manual_tags_skipped} 个")

    total_tags = UnifiedTag.objects.count()
    print(f"统一标签总数: {total_tags}")

    return total_tags

def migrate_product_tag_mappings():
    """迁移产品-标签关联数据"""
    print("\n开始迁移产品-标签关联数据...")

    # 创建标签名称到统一标签ID的映射（大小写不敏感）
    tag_name_to_unified_id = {}
    for unified_tag in UnifiedTag.objects.all():
        # 使用小写作为键，确保大小写不敏感的查找
        key = unified_tag.tag_name.lower()
        # 如果已经有相同小写键的条目，保留第一个（不应该发生，因为tag_name是唯一的）
        if key not in tag_name_to_unified_id:
            tag_name_to_unified_id[key] = unified_tag.id

    # 1. 迁移手工标签关联
    manual_mappings_migrated = 0
    manual_mappings_skipped = 0

    for mapping in ProductTag.objects.all():
        # 获取对应的统一标签ID（大小写不敏感）
        tag_name = mapping.tag.tag_name
        unified_tag_id = tag_name_to_unified_id.get(tag_name.lower())

        if not unified_tag_id:
            print(f"警告: 找不到标签 '{tag_name}' 的统一标签ID，跳过关联")
            manual_mappings_skipped += 1
            continue

        # 检查是否已存在相同的关联
        existing = UnifiedProductTagMapping.objects.filter(
            product_id=mapping.product_id,
            tag_id=unified_tag_id
        ).first()

        if existing:
            # 如果已存在，更新置信度（如果当前是PubChem关联）
            if existing.original_source_type == 'pubchem_mapping':
                # 保持PubChem关联的置信度
                manual_mappings_skipped += 1
            else:
                # 更新为手工关联
                existing.confidence_score = 1.0
                existing.original_mapping_id = mapping.id
                existing.original_source_type = 'manual_mapping'
                existing.save()
                manual_mappings_skipped += 1
        else:
            # 创建新的关联
            UnifiedProductTagMapping.objects.create(
                product_id=mapping.product_id,
                tag_id=unified_tag_id,
                confidence_score=1.0,
                original_mapping_id=mapping.id,
                original_source_type='manual_mapping'
            )
            manual_mappings_migrated += 1

    print(f"手工标签关联迁移完成: 新增 {manual_mappings_migrated} 个, 跳过 {manual_mappings_skipped} 个")

    # 2. 迁移PubChem标签关联
    pubchem_mappings_migrated = 0
    pubchem_mappings_skipped = 0

    for mapping in ProductPubChemTag.objects.all():
        # 获取对应的统一标签ID（大小写不敏感）
        tag_name = mapping.pubchem_tag.tag_name
        unified_tag_id = tag_name_to_unified_id.get(tag_name.lower())

        if not unified_tag_id:
            print(f"警告: 找不到PubChem标签 '{tag_name}' 的统一标签ID，跳过关联")
            pubchem_mappings_skipped += 1
            continue

        # 检查是否已存在相同的关联
        existing = UnifiedProductTagMapping.objects.filter(
            product_id=mapping.product_id,
            tag_id=unified_tag_id
        ).first()

        if existing:
            # 如果已存在，优先使用PubChem关联（保留置信度和来源）
            existing.confidence_score = mapping.confidence_score
            existing.original_mapping_id = mapping.id
            existing.original_source_type = 'pubchem_mapping'
            existing.save()
            pubchem_mappings_skipped += 1
        else:
            # 创建新的关联
            UnifiedProductTagMapping.objects.create(
                product_id=mapping.product_id,
                tag_id=unified_tag_id,
                confidence_score=mapping.confidence_score,
                original_mapping_id=mapping.id,
                original_source_type='pubchem_mapping'
            )
            pubchem_mappings_migrated += 1

    print(f"PubChem标签关联迁移完成: 新增 {pubchem_mappings_migrated} 个, 更新 {pubchem_mappings_skipped} 个")

    total_mappings = UnifiedProductTagMapping.objects.count()
    print(f"统一产品-标签关联总数: {total_mappings}")

    return total_mappings

def validate_migration():
    """验证迁移数据的完整性"""
    print("\n开始验证迁移数据完整性...")

    # 1. 验证标签数量
    manual_tag_count = Tag.objects.count()
    pubchem_tag_count = PubChemTag.objects.count()
    unified_tag_count = UnifiedTag.objects.count()

    print(f"原始手工标签数: {manual_tag_count}")
    print(f"原始PubChem标签数: {pubchem_tag_count}")
    print(f"统一标签数: {unified_tag_count}")

    # 2. 验证关联数量
    manual_mapping_count = ProductTag.objects.count()
    pubchem_mapping_count = ProductPubChemTag.objects.count()
    unified_mapping_count = UnifiedProductTagMapping.objects.count()

    print(f"原始手工关联数: {manual_mapping_count}")
    print(f"原始PubChem关联数: {pubchem_mapping_count}")
    print(f"统一关联数: {unified_mapping_count}")

    # 3. 检查重复标签
    from django.db.models import Count
    duplicate_tags = UnifiedTag.objects.values('tag_name').annotate(
        count=Count('id')
    ).filter(count__gt=1)

    if duplicate_tags.exists():
        print(f"警告: 发现 {duplicate_tags.count()} 个重复标签名称")
        for dup in duplicate_tags[:5]:
            print(f"  - {dup['tag_name']}: {dup['count']} 次")
    else:
        print("[OK] 无重复标签名称")

    # 4. 检查重复关联
    duplicate_mappings = UnifiedProductTagMapping.objects.values(
        'product_id', 'tag_id'
    ).annotate(
        count=Count('id')
    ).filter(count__gt=1)

    if duplicate_mappings.exists():
        print(f"错误: 发现 {duplicate_mappings.count()} 个重复产品-标签关联")
        return False
    else:
        print("[OK] 无重复产品-标签关联")

    # 5. 检查标签名称一致性
    manual_tags_without_unified = Tag.objects.exclude(
        tag_name__in=UnifiedTag.objects.values_list('tag_name', flat=True)
    ).count()

    pubchem_tags_without_unified = PubChemTag.objects.exclude(
        tag_name__in=UnifiedTag.objects.values_list('tag_name', flat=True)
    ).count()

    if manual_tags_without_unified > 0:
        print(f"警告: {manual_tags_without_unified} 个手工标签未迁移到统一标签")

    if pubchem_tags_without_unified > 0:
        print(f"警告: {pubchem_tags_without_unified} 个PubChem标签未迁移到统一标签")

    print("[OK] 迁移验证完成")
    return True

def main():
    """主函数"""
    print("统一标签系统数据迁移工具")
    print("=" * 50)

    try:
        with transaction.atomic():
            # 执行迁移
            migrate_tags()
            migrate_product_tag_mappings()

            # 验证迁移
            if validate_migration():
                print("\n[SUCCESS] 数据迁移成功完成!")
            else:
                print("\n[ERROR] 数据迁移验证失败，请检查错误")
                sys.exit(1)

    except Exception as e:
        print(f"\n[ERROR] 迁移过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()