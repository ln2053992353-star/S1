#!/usr/bin/env python
"""
自动迁移标签层次结构系统
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")

import django
django.setup()

from django.core.management import call_command

def main():
    print("开始自动迁移标签层次结构系统...")

    try:
        # 生成迁移文件
        print("1. 生成迁移文件...")
        call_command('makemigrations', 'search_engine', interactive=False)
        print("   成功生成迁移文件")

        # 运行迁移
        print("\n2. 运行迁移...")
        call_command('migrate', 'search_engine', interactive=False)
        print("   成功运行迁移")

        # 验证新表
        print("\n3. 验证新表...")
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]

            new_tables = [t for t in tables if 'tag_hierarchy' in t or 'tag_category' in t]

            if new_tables:
                print(f"   找到新表: {', '.join(new_tables)}")
            else:
                print("   警告: 未找到预期的新表")

        print("\n" + "="*60)
        print("标签层次结构系统迁移完成!")
        print("="*60)

        return True

    except Exception as e:
        print(f"\n迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)