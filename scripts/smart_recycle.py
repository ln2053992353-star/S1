import os
import shutil
import pymysql
from pymysql.cursors import DictCursor

# ================= 配置区域 =================
PROCESSED_FOLDER = r'D:\code\processed_pdfs'
SOURCE_FOLDER = r'D:\code\pdfs_to_process'

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',
    'db': 'demo1',
    'charset': 'utf8mb4',
    'cursorclass': DictCursor
}


# ===========================================

def main():
    print("♻️  Starting SMART Recycle Protocol...")
    print("   Target: Move ALL files that are NOT successfully linked in DB back to source.\n")

    # 1. 获取所有“成功者”名单
    # 只有在数据库里有记录，且有 DOI 的文件，才算“成功者”
    successful_files = set()

    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT DISTINCT source_filename FROM products WHERE source_doi IS NOT NULL AND source_doi != 'N/A'")
            rows = cursor.fetchall()
            for r in rows:
                if r['source_filename']:
                    successful_files.add(r['source_filename'])
    finally:
        conn.close()

    print(f"📊 Database knows {len(successful_files)} successful files.")

    # 2. 遍历已处理文件夹，找出“漏网之鱼”
    if not os.path.exists(PROCESSED_FOLDER):
        print(f"❌ Processed folder not found: {PROCESSED_FOLDER}")
        return

    files_in_processed = os.listdir(PROCESSED_FOLDER)
    print(f"📂 Found {len(files_in_processed)} files in '{PROCESSED_FOLDER}'.")

    moved_count = 0
    skipped_count = 0

    for filename in files_in_processed:
        if not filename.endswith('.pdf'):
            continue

        # 核心判断：如果这个文件不在“成功者名单”里，就把它挪回去
        if filename not in successful_files:
            src = os.path.join(PROCESSED_FOLDER, filename)
            dst = os.path.join(SOURCE_FOLDER, filename)

            try:
                shutil.move(src, dst)
                # print(f"   ↩️  Recycled: {filename}") # 太多了就不打印了，刷屏
                moved_count += 1
            except Exception as e:
                print(f"   ⚠️ Failed to move {filename}: {e}")
        else:
            skipped_count += 1

    print("-" * 50)
    print(f"✅ RECYCLE COMPLETE!")
    print(f"   - Moved back to source: {moved_count} files (Failed/Empty runs)")
    print(f"   - Stayed in processed:  {skipped_count} files (Already Successful)")
    print(f"\n👉 Now, please run your V7.0 script again. It should process {moved_count} files.")


if __name__ == "__main__":
    main()