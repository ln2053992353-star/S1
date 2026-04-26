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
    print("👻 Starting Ghost Merger Protocol (V2.0 - For V6 Data)...")
    print("   Target: Extract DOI from V6 data and merge into V5 original data\n")

    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            # 1. 找到所有有 DOI 的“新产物” (V6 跑出来的)
            cursor.execute(
                "SELECT product_id, product_name, source_doi, source_filename FROM products WHERE source_doi IS NOT NULL AND source_doi != 'N/A'")
            donors = cursor.fetchall()
            print(f"📊 Found {len(donors)} potential DOI donors (from V6 run).")

            merged_count = 0

            for donor in donors:
                donor_id = donor['product_id']
                donor_name = donor['product_name']
                doi = donor['source_doi']
                filename = donor['source_filename']

                # 2. 去找它的“老版本” (没有 DOI 的 V5 数据)
                # 逻辑：查找名字相似（包含关系）且 ID 不同、且没有 DOI 的产物
                cursor.execute("""
                    SELECT product_id, product_name 
                    FROM products 
                    WHERE product_id != %s 
                      AND (source_doi IS NULL OR source_doi = 'N/A')
                      AND (
                           %s LIKE CONCAT('%%', product_name, '%%')
                           OR product_name LIKE CONCAT('%%', %s, '%%')
                      )
                """, (donor_id, donor_name, donor_name))

                receivers = cursor.fetchall()

                for receiver in receivers:
                    receiver_id = receiver['product_id']
                    receiver_name = receiver['product_name']

                    print(f"🔗 Merging: [V6 New: {donor_name}] >>> [V5 Old: {receiver_name}]")

                    # 3. 执行合并操作
                    # A. 只把 DOI 和 Filename 给旧产物 (保护旧数据的描述和Tag不被覆盖)
                    cursor.execute("""
                        UPDATE products 
                        SET source_doi = %s, source_filename = %s 
                        WHERE product_id = %s
                    """, (doi, filename, receiver_id))

                    # B. (!!!) 核心修复：先删除所有关联的子表数据 (解决报错) (!!!)
                    try:
                        # 删除可能存在的向量表关联
                        cursor.execute("DELETE FROM product_embeddings WHERE product_id = %s", (donor_id,))
                    except Exception:
                        pass

                    try:
                        cursor.execute("DELETE FROM product_vectors WHERE product_id = %s", (donor_id,))
                    except Exception:
                        pass

                    try:
                        # 删除标签关联
                        cursor.execute("DELETE FROM product_tags WHERE product_id = %s", (donor_id,))
                    except Exception:
                        pass

                    # C. 现在可以安全删除 V6 的新产物了
                    cursor.execute("DELETE FROM products WHERE product_id = %s", (donor_id,))

                    print(f"   ✅ Success! DOI transferred to ID {receiver_id}. V6 ID {donor_id} deleted.")
                    merged_count += 1
                    break  # 一个 donor 只合并一次

            conn.commit()
            print(f"\n🎉 Total merged pairs: {merged_count}")
            print("   Now run 'export_excel.py' again to see your filled DOIs!")

    except Exception as e:
        print(f"❌ Critical Error: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()