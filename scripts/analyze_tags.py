#!/usr/bin/env python
import os
import sys
import django
import re
from collections import Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import Tag

def analyze_tags():
    print("分析标签数据质量问题...")

    tags = Tag.objects.all()
    total = tags.count()
    print(f"总标签数: {total}")

    # 1. 检查标签类别为空的情况
    no_category = tags.filter(tag_category__isnull=True).count()
    print(f"1. 无类别的标签: {no_category} ({no_category/total*100:.1f}%)")

    # 2. 检查重复标签（忽略大小写）
    name_counter = Counter()
    for tag in tags:
        name_counter[tag.tag_name.lower()] += 1

    duplicates = {name: count for name, count in name_counter.items() if count > 1}
    print(f"2. 重复标签（忽略大小写）: {len(duplicates)} 组")
    if duplicates:
        for name, count in list(duplicates.items())[:10]:
            print(f"   '{name}': {count} 次")

    # 3. 检查大小写不一致
    case_variations = {}
    for tag in tags:
        lower = tag.tag_name.lower()
        if lower not in case_variations:
            case_variations[lower] = set()
        case_variations[lower].add(tag.tag_name)

    inconsistent_case = {k: v for k, v in case_variations.items() if len(v) > 1}
    print(f"3. 大小写不一致的标签: {len(inconsistent_case)} 组")
    if inconsistent_case:
        for lower, variations in list(inconsistent_case.items())[:10]:
            print(f"   '{lower}': {variations}")

    # 4. 检查包含特殊字符的标签
    special_char_tags = []
    special_pattern = re.compile(r'[^a-zA-Z0-9\s\-_]')
    for tag in tags:
        if special_pattern.search(tag.tag_name):
            special_char_tags.append(tag.tag_name)

    print(f"4. 包含特殊字符的标签: {len(special_char_tags)} 个")
    if special_char_tags:
        for name in special_char_tags[:20]:
            print(f"   '{name}'")

    # 5. 检查前导/尾随空格
    whitespace_tags = []
    for tag in tags:
        if tag.tag_name != tag.tag_name.strip():
            whitespace_tags.append(tag.tag_name)

    print(f"5. 有前导/尾随空格的标签: {len(whitespace_tags)} 个")
    if whitespace_tags:
        for name in whitespace_tags[:10]:
            print(f"   '{name}'")

    # 6. 检查标签长度分布
    lengths = [len(tag.tag_name) for tag in tags]
    if lengths:
        avg_len = sum(lengths) / len(lengths)
        max_len = max(lengths)
        min_len = min(lengths)
        print(f"6. 标签长度 - 平均: {avg_len:.1f}, 最小: {min_len}, 最大: {max_len}")

    # 7. 检查常见问题模式
    print("\n7. 常见问题模式检查:")
    # 检查括号是否匹配
    bracket_tags = []
    for tag in tags:
        name = tag.tag_name
        if ('(' in name and ')' not in name) or (')' in name and '(' not in name):
            bracket_tags.append(name)

    print(f"   括号不匹配: {len(bracket_tags)} 个")
    if bracket_tags:
        for name in bracket_tags[:10]:
            print(f"      '{name}'")

    # 8. 抽样显示一些标签示例
    print("\n8. 随机标签示例:")
    import random
    sample_tags = random.sample(list(tags), min(20, total))
    for tag in sample_tags:
        print(f"   '{tag.tag_name}' (类别: {tag.tag_category})")

if __name__ == "__main__":
    analyze_tags()