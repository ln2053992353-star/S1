import pymysql
from pymysql.cursors import DictCursor

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',
    'db': 'demo1',
    'charset': 'utf8mb4',
    'cursorclass': DictCursor
}


def main():
    print("🧹 Starting Final Cleanup (Removing products without DOI)...")

    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            # 1. 统计清洗前的数量
            cursor.execute("SELECT COUNT(*) as cnt FROM products")
            total_before = cursor.fetchone()['cnt']

            # 2. 找出没有 DOI 的“垃圾数据”
            cursor.execute(
                "SELECT product_id, product_name FROM products WHERE source_doi IS NULL OR source_doi = 'N/A' OR source_doi = ''")
            bad_apples = cursor.fetchall()

            print(f"📊 Total Products: {total_before}")
            print(f"🗑️  Found {len(bad_apples)} items to delete (No DOI).")

            if len(bad_apples) == 0:
                print("✅ Your database is already clean!")
                return

            confirm = input(f"⚠️  Are you sure you want to delete {len(bad_apples)} records? (y/n): ")
            if confirm.lower() != 'y':
                print("❌ Aborted.")
                return

            deleted_count = 0
            for item in bad_apples:
                p_id = item['product_id']

                # A. 先删关联表 (防止外键报错)
                cursor.execute("DELETE FROM product_embeddings WHERE product_id = %s", (p_id,))
                cursor.execute("DELETE FROM product_vectors WHERE product_id = %s", (p_id,))
                cursor.execute("DELETE FROM product_tags WHERE product_id = %s", (p_id,))

                # B. 再删主表
                cursor.execute("DELETE FROM products WHERE product_id = %s", (p_id,))
                deleted_count += 1

                if deleted_count % 50 == 0:
                    print(f"   Processed {deleted_count}...")

            conn.commit()

            # 3. 统计清洗后的数量
            cursor.execute("SELECT COUNT(*) as cnt FROM products")
            total_after = cursor.fetchone()['cnt']

            print("-" * 50)
            print(f"✅ Cleanup Complete!")
            print(f"   - Before: {total_before}")
            print(f"   - Deleted: {deleted_count}")
            print(f"   - Final Count: {total_after}")
            print("\n👉 Now your database is 100% DOI-verified. You can run export_excel.py for the final report.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()