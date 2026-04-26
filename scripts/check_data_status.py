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
    print("🔍 Starting Deep Data Diagnosis...\n")

    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            # 1. 检查总数变化
            cursor.execute("SELECT COUNT(*) as total FROM products")
            total = cursor.fetchone()['total']

            cursor.execute(
                "SELECT COUNT(*) as with_doi FROM products WHERE source_doi IS NOT NULL AND source_doi != 'N/A'")
            with_doi = cursor.fetchone()['with_doi']

            print(f"📊 Current Status:")
            print(f"   - Total Products: {total} (Previously around 850?)")
            print(f"   - Products with DOI: {with_doi}")
            print(f"   - Products WITHOUT DOI: {total - with_doi}\n")

            # 2. 核心：抓“双胞胎” (检查是否有名字很像但没合并的产物)
            print("🕵️‍♂️ Detecting 'Duplicate' Ghosts (Names that look similar)...")
            print("-" * 60)
            print(f"{'ID':<6} | {'Product Name':<30} | {'DOI Status'}")
            print("-" * 60)

            # 查找名字相似的产物（例如 'Taxol' 和 'taxol' 或 'Taxol production'）
            # 这里我们简单取前 50 个没 DOI 的产物，看看数据库里有没有跟它很像的
            cursor.execute("SELECT product_id, product_name FROM products WHERE source_doi IS NULL LIMIT 50")
            orphans = cursor.fetchall()

            suspicious_count = 0
            for orphan in orphans:
                name = orphan['product_name']
                # 模糊搜索：比如 name 是 "Ethanol"，搜 "%Ethanol%"
                cursor.execute(
                    "SELECT product_id, product_name, source_doi FROM products WHERE product_name LIKE %s AND product_id != %s",
                    (f"%{name}%", orphan['product_id'])
                )
                twins = cursor.fetchall()

                if twins:
                    suspicious_count += 1
                    if suspicious_count <= 10:  # 只打印前 10 个例子
                        print(f"🔴 Orphan (No DOI): [{orphan['product_id']}] {name}")
                        for twin in twins:
                            doi_status = "✅ Has DOI" if twin['source_doi'] else "❌ No DOI"
                            print(
                                f"   └── Possible Match: [{twin['product_id']}] {twin['product_name']} ({doi_status})")
                        print("-" * 30)

            if suspicious_count == 0:
                print("✅ No obvious duplicates found based on simple name matching.")
            else:
                print(f"\n⚠️ Found {suspicious_count} potential duplicate groups in sample size!")
                print(
                    "   Conclusion: AI extracted names slightly differently, creating new rows instead of updating old ones.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()