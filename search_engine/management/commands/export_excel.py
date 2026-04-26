import os
import sys

# ==============================================================================
# (!!!) 1. 设置 Hugging Face 国内镜像 (用户要求) (!!!)
# 放在最前面，防止项目其他地方引用模型时报错
# ==============================================================================
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import pandas as pd
from django.core.management.base import BaseCommand
from database.models import Product


class Command(BaseCommand):
    help = 'Export full database content to Excel (No Category, With Mirror Config)'

    def handle(self, *args, **options):
        print("🚀 Starting Data Export...")

        # 1. 预取标签数据
        products = Product.objects.prefetch_related('tags').all().order_by('product_id')

        total = products.count()
        print(f"📊 Found {total} products in database. Processing...")

        data_list = []

        for p in products:
            # --- A. 标签处理 ---
            tags_list = [t.tag_name for t in p.tags.all()]
            tags_str = ", ".join(tags_list) if tags_list else "N/A"

            # --- B. 字段判空处理 ---
            # 确保 DOI 和 文件名 存在
            doi = p.source_doi if (hasattr(p, 'source_doi') and p.source_doi) else "N/A"
            filename = p.source_filename if (hasattr(p, 'source_filename') and p.source_filename) else "N/A"
            grna = p.grna_map if (hasattr(p, 'grna_map') and p.grna_map) else "N/A"
            desc = p.description if p.description else "N/A"

            # --- C. 组装数据行 (已移除 Category) ---
            data_list.append({
                "ID": p.product_id,
                "Product Name": p.product_name,
                "Tags": tags_str,
                "Source DOI": doi,  # 核心溯源
                "Source Filename": filename,  # 核心溯源
                "gRNA Map": grna,
                "Description": desc
            })

        # 2. 生成 DataFrame
        df = pd.DataFrame(data_list)

        # 3. 导出文件
        output_file = "Engineered_Cell_Products_Report.xlsx"

        try:
            # 使用 openpyxl 引擎
            df.to_excel(output_file, index=False, engine='openpyxl')

            print(f"\n✅ Export Successful!")
            print(f"📂 File saved as: {output_file}")
            print(f"   Total Records: {len(df)}")

        except ImportError:
            print("❌ Error: Missing 'openpyxl' or 'pandas' library.")
            print("   Please run: pip install pandas openpyxl")
        except Exception as e:
            print(f"❌ Export Failed: {e}")
            print("   (Please close the Excel file if it is currently open!)")