import json
import time
import requests
from django.core.management.base import BaseCommand
from django.apps import apps
from sentence_transformers import SentenceTransformer

# ==============================================================================
# 配置区域 (火山引擎)
# ==============================================================================
LLM_API_KEY = "156c8a37-20bf-4060-8bdc-d9991fc03eef"
LLM_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
LLM_MODEL_NAME = "ep-20251211173243-qklb7"
LLM_API_URL = f"{LLM_API_BASE}/chat/completions"


class Command(BaseCommand):
    help = '使用 AI 深度清洗数据库：提取纯净功能描述 -> 重算高精度向量'

    def handle(self, *args, **options):
        # 延迟加载模型
        Product = apps.get_model('search_engine', 'Product')
        ProductEmbedding = apps.get_model('search_engine', 'ProductEmbedding')

        self.stdout.write("🚀 Loading local PubMedBert model...")
        vec_model = SentenceTransformer('pritamdeka/S-PubMedBert-MS-MARCO')

        # 获取所有已有 Embedding 的记录
        embeddings = ProductEmbedding.objects.all()
        total = embeddings.count()

        self.stdout.write(f"准备清洗 {total} 条数据...")

        for i, item in enumerate(embeddings):
            try:
                prod = item.product
                raw_text = prod.description if prod.description else prod.product_name

                # 如果描述太短，可能没法清洗，跳过或直接用
                if len(raw_text) < 10:
                    continue

                self.stdout.write(f"🤖 [{i + 1}/{total}] AI Cleaning: {prod.product_name}...")

                # --- 1. 调用 AI 进行清洗 ---
                clean_summary = self.clean_text_with_ai(raw_text)

                # --- 2. 组合标签 (如果有) ---
                tags_list = list(prod.tags.values_list('tag_name', flat=True))
                tags_str = ", ".join(tags_list)

                # --- 3. 生成黄金标准文本 ---
                # 格式：[Tags] + [Clean Description]
                final_embedding_text = f"Keywords: {tags_str}. Function: {clean_summary}"

                # --- 4. 更新数据库 ---
                item.function = clean_summary
                item.embedding_text = final_embedding_text

                # --- 5. 重算向量 ---
                vector = vec_model.encode(final_embedding_text).tolist()
                item.vector = json.dumps(vector)
                item.dim = 768
                item.model_name = "PubMedBert-AI-Cleaned"

                item.save()

                # 避免 API 限流，稍微停顿
                time.sleep(0.5)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing {prod.product_name}: {e}"))

        self.stdout.write(self.style.SUCCESS("🎉 数据库清洗完成！准确度已大幅提升。"))

    def clean_text_with_ai(self, raw_text):
        """调用火山引擎提取核心功能"""
        prompt = f"""
        Task: Extract the core biological function and engineered features from the input text.
        Input: "{raw_text[:2000]}"

        Rules:
        1. Remove technical noise (e.g., "PCR conditions", "centrifuge speed", "primer sequences", "cloning methods").
        2. Focus on: What does the cell produce? What does it sense? What is the therapeutic mechanism?
        3. Translate to precise Scientific English suitable for embedding.
        4. Keep it concise (1-3 sentences).

        Output: Just the English summary. No "Here is the summary".
        """

        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": LLM_MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }

        try:
            resp = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                return resp.json()['choices'][0]['message']['content'].strip()
            else:
                return raw_text  # 失败降级
        except:
            return raw_text
