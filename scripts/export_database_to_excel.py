#!/usr/bin/env python
"""
将数据库所有表导出到Excel文件
每个表一个工作表
"""
import os
import sys
import django
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import (
    Product, Tag, ProductTag,
    ProductEmbedding, ProductSource, YeastPubChemData,
    PubChemTag, ProductPubChemTag, TagHierarchy, TagCategorySystem,
    UnifiedTag, UnifiedProductTagMapping
)

def get_model_data(model_class, fields=None):
    """获取模型数据并转换为DataFrame"""
    try:
        queryset = model_class.objects.all()

        # 如果未指定字段，使用所有字段
        if fields is None:
            # 排除关系字段和复杂字段
            exclude_fields = []
            data = []
            for obj in queryset:
                row = {}
                for field in obj._meta.fields:
                    field_name = field.name
                    if field_name in exclude_fields:
                        continue
                    try:
                        value = getattr(obj, field_name)
                        # 处理外键显示
                        if hasattr(field, 'remote_field') and field.remote_field:
                            if value:
                                if hasattr(value, '__str__'):
                                    row[f"{field_name}_display"] = str(value)
                                else:
                                    row[f"{field_name}_display"] = str(value.pk)
                            else:
                                row[f"{field_name}_display"] = None
                            row[f"{field_name}_id"] = value.pk if value else None
                        else:
                            row[field_name] = value
                    except Exception as e:
                        row[field_name] = f"Error: {e}"
                data.append(row)

            df = pd.DataFrame(data)
        else:
            # 使用指定字段
            data = queryset.values(*fields)
            df = pd.DataFrame(data)

        return df

    except Exception as e:
        print(f"  错误: 无法导出 {model_class.__name__}: {e}")
        return pd.DataFrame()

def clean_dataframe(df):
    """清理DataFrame中的时区敏感datetime列"""
    if df.empty:
        return df

    for col in df.columns:
        # 检查列是否为datetime类型且有时区信息
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            try:
                # 去除时区信息
                df[col] = df[col].dt.tz_localize(None)
            except:
                # 如果已经无时区或出错，跳过
                pass

    return df

def export_to_excel(output_path):
    """导出所有模型数据到Excel"""
    print("开始导出数据库到Excel...")

    # 定义要导出的模型和字段
    model_configs = [
        (Product, ['product_id', 'product_name', 'description', 'source_filename', 'source_doi']),
        (Tag, ['tag_id', 'tag_name', 'tag_category']),
        (ProductTag, ['id', 'product_id', 'tag_id']),
        (ProductEmbedding, ['id', 'product_id', 'embedding_text', 'function',
                           'pubchem_description', 'tags_text', 'grna', 'iupac_name',
                           'source_database', 'model_name', 'dim', 'created_at', 'updated_at']),
        (ProductSource, ['id', 'product_id', 'doi', 'filename']),
        (YeastPubChemData, ['product_id', 'pubchem_cid', 'iupac_name',
                           'functional_description', 'sync_failed', 'sync_failed_reason',
                           'last_sync_attempt', 'last_sync_success']),
        (PubChemTag, ['tag_id', 'tag_name', 'tag_category', 'pubchem_classification', 'mesh_id']),
        (ProductPubChemTag, ['id', 'product_id', 'pubchem_tag_id', 'confidence_score', 'source']),
        (TagHierarchy, ['id', 'parent_content_type_id', 'parent_object_id',
                       'child_content_type_id', 'child_object_id', 'relationship_type',
                       'confidence', 'source', 'level', 'created_at', 'updated_at']),
        (TagCategorySystem, ['id', 'category_path', 'display_name', 'level',
                            'parent_path', 'description', 'tag_type', 'example_tags',
                            'usage_count', 'created_at', 'updated_at']),
        (UnifiedTag, ['id', 'tag_name', 'tag_category', 'source', 'original_tag_id',
                     'original_source_type', 'pubchem_classification', 'mesh_id',
                     'created_at', 'updated_at']),
        (UnifiedProductTagMapping, ['id', 'product_id', 'tag_id', 'confidence_score',
                                   'original_mapping_id', 'original_source_type',
                                   'created_at', 'updated_at']),
    ]

    # 创建Excel写入器
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for model_class, fields in model_configs:
            try:
                print(f"  导出 {model_class.__name__}...")
                df = get_model_data(model_class, fields)

                if not df.empty:
                    # 清理时区信息
                    df = clean_dataframe(df)
                    # 写入Excel，工作表名称为模型名称
                    sheet_name = model_class.__name__[:31]  # Excel工作表名最大31字符
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    print(f"    [OK] 成功: {len(df)} 行")
                else:
                    print(f"    [WARN] 空表")

            except Exception as e:
                print(f"    [ERROR] 失败: {e}")

    print(f"\n导出完成: {output_path}")

    # 显示统计信息
    print("\n数据统计:")
    for model_class, fields in model_configs:
        count = model_class.objects.count()
        print(f"  {model_class.__name__}: {count} 条记录")

def main():
    """主函数"""
    # 生成输出文件名，包含时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"database_export_{timestamp}.xlsx"
    output_path = os.path.join(BASE_DIR, output_filename)

    print("数据库导出工具")
    print("=" * 50)

    try:
        # 导出数据
        export_to_excel(output_path)

        # 检查文件大小
        file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
        print(f"\n文件大小: {file_size:.2f} MB")
        print(f"文件位置: {output_path}")
        print("\n[SUCCESS] 导出成功!")

    except Exception as e:
        print(f"\n[ERROR] 导出失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()