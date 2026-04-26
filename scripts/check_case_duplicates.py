#!/usr/bin/env python
"""
检查统一标签表中大小写不同的重复标签
"""
import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import UnifiedTag
from collections import defaultdict

def check_case_insensitive_duplicates():
    """检查大小写不敏感的重复标签"""
    print("检查大小写不敏感的重复标签")
    print("=" * 50)

    # 收集所有标签的小写名称
    lowercase_names = defaultdict(list)

    for tag in UnifiedTag.objects.all():
        lowercase_names[tag.tag_name.lower()].append(tag)

    # 找出有多个不同大小写变体的标签
    duplicates = {k: v for k, v in lowercase_names.items() if len(v) > 1}

    print(f"发现 {len(duplicates)} 个大小写不同的重复标签:")

    for lowercase_name, tags in list(duplicates.items())[:10]:
        print(f"\n小写名称: '{lowercase_name}' (共{len(tags)}个变体)")
        for tag in tags:
            print(f"  ID={tag.id}, 名称='{tag.tag_name}', 来源={tag.source}, 原始类型={tag.original_source_type}")

    # 检查这对迁移字典的影响
    print("\n\n对迁移字典的影响分析:")
    print(f"字典大小: {len(lowercase_names)}")
    print(f"统一标签总数: {UnifiedTag.objects.count()}")

    if len(lowercase_names) < UnifiedTag.objects.count():
        print(f"警告: 字典丢失了 {UnifiedTag.objects.count() - len(lowercase_names)} 个条目")
        print("这意味着有标签因为大小写不同被字典覆盖了")
    else:
        print("[OK] 字典没有丢失条目")

    # 检查是否有标签名称完全相同的重复（应该由唯一约束防止）
    exact_duplicates = defaultdict(list)
    for tag in UnifiedTag.objects.all():
        exact_duplicates[tag.tag_name].append(tag)

    exact_dup_count = sum(1 for v in exact_duplicates.values() if len(v) > 1)
    print(f"\n完全相同的重复标签名称: {exact_dup_count}")

if __name__ == "__main__":
    check_case_insensitive_duplicates()