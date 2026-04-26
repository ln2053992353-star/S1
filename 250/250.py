import os
import sys
import json
import re
import ast  # 单引号字典解析神器
import pymysql
from pymysql.cursors import DictCursor
import fitz  # PyMuPDF
from openai import OpenAI

# ==============================================================================
# 1. 基础配置
# ==============================================================================
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ['CURL_CA_BUNDLE'] = ''
import ssl

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

from sentence_transformers import SentenceTransformer

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',
    'db': 'demo1',
    'charset': 'utf8mb4',
    'cursorclass': DictCursor
}

# 路径配置 (请确认路径正确)
SOURCE_FOLDER_PATH = r'D:\code\pdfs_to_process'
PROCESSED_FOLDER_PATH = r'D:\code\processed_pdfs'

# AI API 配置
ARK_API_KEY = "fdcade54-f3e0-4c3a-b232-f0c17b292b7b"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
ARK_MODEL_ID = "ep-20251211174454-h85sf"

client = OpenAI(base_url=ARK_BASE_URL, api_key=ARK_API_KEY)

print("  > [System] Loading Embedding Model...")
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
except:
    print("  > [Warning] Model load failed. Vectors will be skipped.")
    embedding_model = None


# ==============================================================================
# 2. 核心增强功能 (Regex & Repair)
# ==============================================================================

def find_doi_with_regex(text):
    """
    不依赖 AI，直接用正则暴力提取 DOI
    匹配常见的 10.xxxx/xxxxx 格式
    """
    # 常见的 DOI 匹配模式
    doi_pattern = r'\b(10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)\b'
    matches = re.findall(doi_pattern, text)

    if matches:
        # 通常第一个就是该文的 DOI，但也可能是参考文献的
        # 我们优先取出现在前 2000 个字符里的 DOI (通常在页眉)
        for match in matches:
            if text.find(match) < 3000:
                return match
        return matches[0]  # 如果前面没找到，就返回第一个找到的
    return None


def clean_text_for_ai(text):
    """ 清洗文本，去除导致 JSON 报错的控制字符 """
    # 替换掉非打印字符，保留换行和制表符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text


def parse_loose_json(content):
    """ 强力 JSON 解析器：兼容单引号、Markdown、不规范格式 """
    # 1. 清洗 Markdown
    content = re.sub(r'^```(json|python)?', '', content, flags=re.MULTILINE)
    content = re.sub(r'```$', '', content, flags=re.MULTILINE).strip()

    # 2. 尝试标准解析
    try:
        return json.loads(content, strict=False)
    except:
        pass

    # 3. 尝试 Python eval 解析 (处理单引号)
    try:
        return ast.literal_eval(content)
    except:
        pass

    # 4. 尝试提取大括号内容再次解析
    match = re.search(r'(\{.*\})', content, re.DOTALL)
    if match:
        inner = match.group(1)
        try:
            return json.loads(inner, strict=False)
        except:
            try:
                return ast.literal_eval(inner)
            except:
                pass

    return None


def extract_data_v8(paper_text, filename):
    print(f"  > [AI] analyzing text from '{filename}'...")

    # 步骤 A: 先用正则找 DOI (双保险)
    regex_doi = find_doi_with_regex(paper_text)
    if regex_doi:
        print(f"    > [Regex] Found DOI locally: {regex_doi}")

    # 步骤 B: 准备 AI 输入
    clean_text = clean_text_for_ai(paper_text[:80000])  # 增加阅读量

    system_prompt = (
        "You are an expert researcher in Synthetic Biology. "
        "Extract industrial products produced by engineered cells from the text.\n"
        "OUTPUT FORMAT (JSON ONLY):\n"
        "{\n"
        "  \"doi\": \"string (If you found one)\",\n"
        "  \"products\": [\n"
        "    {\n"
        "      \"product_name\": \"string (Standard chemical name)\",\n"
        "      \"grna_map\": \"string (or N/A)\",\n"
        "      \"description\": \"string (Brief summary)\",\n"
        "      \"tags\": [\"tag1\", \"tag2\"]\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "IMPORTANT: Use DOUBLE QUOTES for JSON keys/values."
    )

    try:
        completion = client.chat.completions.create(
            model=ARK_MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Paper Text:\n{clean_text}"}
            ],
            temperature=0.1
        )
        content = completion.choices[0].message.content
        data = parse_loose_json(content)

        if data:
            # 融合逻辑：如果 AI 没找到 DOI，但正则找到了，强制覆盖
            ai_doi = data.get('doi', 'N/A')
            if (not ai_doi or ai_doi == 'N/A') and regex_doi:
                data['doi'] = regex_doi
                print("    > [Fix] Applied Regex DOI to AI result.")

            return data
        else:
            print("    > [Error] AI output parsing failed.")
            return None

    except Exception as e:
        print(f"    > [API Error] {e}")
        return None


# ==============================================================================
# 3. 主流程
# ==============================================================================

def main():
    print("🚀 Starting V8.0 ARMORED Pipeline...")

    if not os.path.exists(SOURCE_FOLDER_PATH): os.makedirs(SOURCE_FOLDER_PATH)
    if not os.path.exists(PROCESSED_FOLDER_PATH): os.makedirs(PROCESSED_FOLDER_PATH)

    files = [f for f in os.listdir(SOURCE_FOLDER_PATH) if f.lower().endswith('.pdf')]
    print(f"📂 Found {len(files)} files to process.")

    conn = pymysql.connect(**DB_CONFIG)

    processed_count = 0
    success_count = 0

    try:
        for filename in files:
            filepath = os.path.join(SOURCE_FOLDER_PATH, filename)
            processed_path = os.path.join(PROCESSED_FOLDER_PATH, filename)

            print(f"\nProcessing [{processed_count + 1}/{len(files)}]: {filename}")

            # 1. 读文件
            try:
                text = ""
                with fitz.open(filepath) as doc:
                    for page in doc: text += page.get_text() + "\n"
            except Exception as e:
                print(f"  > [Bad File] Cannot read PDF: {e}")
                # 坏文件也移走，免得卡住
                if os.path.exists(processed_path): os.remove(processed_path)
                os.rename(filepath, processed_path)
                continue

            if len(text) < 100:
                print("  > [Skip] Text too short/scanned PDF.")
                if os.path.exists(processed_path): os.remove(processed_path)
                os.rename(filepath, processed_path)
                continue

            # 2. 提取数据
            result = extract_data_v8(text, filename)

            if not result or not result.get('products'):
                print("  > [Skip] No products found by AI.")
                # 即使没产物，如果我们要算它“处理过”，也得移走
                # 但根据您的 Recycle 逻辑，只有入库了才算成功。
                # 所以这里如果真的失败了，建议也移走，否则下次还会死循环。
                # 策略：移走。如果想重试，以后再手动搬回来。
                if os.path.exists(processed_path): os.remove(processed_path)
                os.rename(filepath, processed_path)
                continue

            doi = result.get('doi', 'N/A')
            products = result.get('products', [])

            print(f"  > Saving {len(products)} products (DOI: {doi})...")

            # 3. 存入数据库
            with conn.cursor() as cursor:
                for prod in products:
                    p_name = prod.get('product_name')
                    if not p_name: continue

                    p_grna = prod.get('grna_map', 'N/A')
                    p_desc = prod.get('description', '')
                    p_tags = prod.get('tags', [])

                    # 插入或更新
                    sql = """
                        INSERT INTO products (product_name, grna_map, description, source_filename, source_doi)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE 
                            source_filename = VALUES(source_filename),
                            source_doi = VALUES(source_doi)
                    """
                    cursor.execute(sql, (p_name, p_grna, p_desc, filename, doi))

                    # 补 Tag
                    cursor.execute("SELECT product_id FROM products WHERE product_name=%s", (p_name,))
                    pid = cursor.fetchone()['product_id']

                    for tag in p_tags:
                        cursor.execute("INSERT IGNORE INTO tags (tag_name) VALUES (%s)", (tag,))
                        cursor.execute("SELECT tag_id FROM tags WHERE tag_name=%s", (tag,))
                        tid = cursor.fetchone()['tag_id']
                        cursor.execute("INSERT IGNORE INTO product_tags (product_id, tag_id) VALUES (%s, %s)",
                                       (pid, tid))

            conn.commit()
            success_count += 1

            # 4. 移动文件
            if os.path.exists(processed_path): os.remove(processed_path)
            os.rename(filepath, processed_path)

            processed_count += 1

    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")
    finally:
        conn.close()
        print(f"\n✅ Batch finished. Processed {processed_count} files.")


if __name__ == "__main__":
    main()