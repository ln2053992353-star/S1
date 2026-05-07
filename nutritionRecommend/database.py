import os, time
import shutil
import pandas as pd
import chromadb
import uuid
import torch
from sentence_transformers import SentenceTransformer
from pathlib import Path

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"当前使用的设备是: {device}")


def create_unique_dir(base_path):
    target_path = Path(base_path)

    # 真正的重命名逻辑：如果旧的在那，把它移走
    if target_path.exists():
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = target_path.parent / f"{target_path.name}_{timestamp}"

        # 执行重命名操作 (mv)
        target_path.rename(backup_path)


# 1. 环境配置与极致缓存清理
# 设置镜像站，确保在中国大陆境内下载顺畅
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 解决 Windows 下 Jina 模型可能残留的受损加载脚本（AttributeError 的根源）
jina_cache_path = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "modules", "transformers_modules",
                               "jinaai")
if os.path.exists(jina_cache_path):
    print(f"清理旧版模型脚本缓存: {jina_cache_path}")
    shutil.rmtree(jina_cache_path, ignore_errors=True)

# 2. 模型初始化
# 根据报错提示，Jina-v5 支持的任务为: ['retrieval', 'text-matching', 'clustering', 'classification']
model_id = "jinaai/jina-embeddings-v5-text-small"

print("正在初始化 Jina-v5 模型...")
model = SentenceTransformer(
    model_id,
    device=device,
    trust_remote_code=True,
    model_kwargs={"trust_remote_code": True}
)

# 3. 初始化数据库
# 使用 PersistentClient 确保数据持久化存储
db_path = "../database/embeddingDB"
create_unique_dir(db_path)
client = chromadb.PersistentClient(path=db_path)

# 根据文献建议，语义检索任务使用余弦相似度 (cosine) 效果最佳
collection = client.get_or_create_collection(
    name="yeast_products_v5_expert",
    metadata={"hnsw:space": "cosine"}
)

# 4. 读取并处理数据
file_path = "../database/product_export_20260403_005815.xlsx"
df = pd.read_excel(file_path)

documents = []
metadatas = []
ids = []

# 数据清洗与准备
for index, row in df.iterrows():
    documents.append(str(row["embedding_text"]))
    # documents.append(str(row["pubchem_description"]))
    metadatas.append({
        "source_doi": str(row.get('source_doi', 'N/A')),
        "iupac_name": str(row.get('iupac_name', 'N/A')),
        "tags": str(row.get('tags', 'N/A')),
        "product_name": str(row.get('product_name', 'N/A'))
    })
    ids.append(str(uuid.uuid4()))

# 分批向量化并入库
batch_size = 64  # 减小 batch size 以确保显存安全
print(f"开始入库，共 {len(documents)} 条数据...")

for i in range(0, len(documents), batch_size):
    # for i in range(0, 2, batch_size):
    # print(time.time())
    batch_docs = documents[i:i + batch_size]

    # 【修正点】：将 task 设置为 "retrieval"
    # Jina-v5 使用 LoRA 适配器来优化特定任务
    batch_embeddings = model.encode(
        batch_docs,
        task="retrieval",
        convert_to_numpy=True
    ).tolist()

    collection.add(
        ids=ids[i:i + batch_size],
        documents=batch_docs,
        embeddings=batch_embeddings,  # 显式传入由 Jina 适配器生成的向量
        metadatas=metadatas[i:i + batch_size]
    )
    print(f"进度: {i + len(batch_docs)}/{len(documents)}")
    # print(time.time())


# 5. 智能任务重定向查询
def smart_query(text):
    """
    针对 Jina-v5 的检索优化查询
    """
    # 【修正点】：查询端同样使用 "retrieval" 适配器
    # 这样模型会激活针对搜索优化过的 LoRA 层
    query_vec = model.encode(
        [text],
        task="retrieval",
        convert_to_numpy=True
    ).tolist()

    results = collection.query(
        query_embeddings=query_vec,
        n_results=3
    )

    print(f"\n🚀 Jina-v5 推荐结果 (查询词: {text})")
    for i in range(len(results['documents'][0])):
        meta = results['metadatas'][0][i]
        # 计算相似度得分 (1 - 距离)
        score = 1 - results['distances'][0][i]
        print(f"【TOP {i + 1}】 {meta['iupac_name']}")
        print(f"语义匹配度: {score:.2%}")
        print(f"详细描述: {results['documents'][0][i][:100]}...")
        print("-" * 40)


# 执行搜索测试
if __name__ == "__main__":
    # smart_query("葡萄糖")
    pass
