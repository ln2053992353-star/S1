#!/usr/bin/env python
"""
直接运行标签层次结构迁移（非交互式）
"""
import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")

# 设置Django
django.setup()

from django.core.management import call_command

def run_direct_migration():
    """直接运行迁移"""
    print("开始创建标签层次结构迁移...")

    try:
        # 1. 生成迁移文件
        print("1. 生成迁移文件...")
        call_command('makemigrations', 'search_engine', interactive=False)
        print("   迁移文件生成成功")

        # 2. 运行迁移
        print("\n2. 运行迁移...")
        call_command('migrate', 'search_engine', interactive=False)
        print("   迁移完成")

        # 3. 检查新表
        print("\n3. 检查新表...")
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE '%tag_%'")
            tables = cursor.fetchall()
            print(f"   找到 {len(tables)} 个标签相关表:")
            for table in tables:
                print(f"   - {table[0]}")

        return True

    except Exception as e:
        print(f"迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_model_definitions():
    """检查模型定义"""
    print("检查模型定义...")

    try:
        from search_engine.models import TagHierarchy, TagCategorySystem

        print("TagHierarchy 模型字段:")
        for field in TagHierarchy._meta.fields:
            print(f"  - {field.name}: {field.get_internal_type()}")

        print("\nTagCategorySystem 模型字段:")
        for field in TagCategorySystem._meta.fields:
            print(f"  - {field.name}: {field.get_internal_type()}")

        return True

    except Exception as e:
        print(f"检查模型定义失败: {e}")
        return False

def main():
    """主函数"""
    print("标签层次结构直接迁移工具")
    print("=" * 50)

    # 检查模型定义
    if not check_model_definitions():
        print("模型定义检查失败，停止迁移")
        return

    # 确认执行
    print("\n将执行以下操作:")
    print("1. 创建迁移文件 (makemigrations)")
    print("2. 应用迁移 (migrate)")
    print("3. 创建新表: tag_hierarchies, tag_category_system")

    proceed = input("\n确认执行? (y/n): ").strip().lower()

    if proceed != 'y':
        print("取消迁移")
        return

    # 执行迁移
    success = run_direct_migration()

    if success:
        print("\n" + "=" * 50)
        print("迁移成功完成!")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("迁移失败!")
        print("=" * 50)

if __name__ == "__main__":
    main()