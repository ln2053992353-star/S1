import json
import numpy as np
import requests
import logging
from django.conf import settings
from .vector_index import search_similar_vectors, initialize_index

# 主动清理环境变量中的代理设置，确保LLM API调用绝对不受影响
import os
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)

# 配置日志
logger = logging.getLogger(__name__)

# ==============================================================================
# 1. API 配置 (火山引擎 / DeepSeek) - 从Django settings获取
# ==============================================================================
# 从Django settings获取配置
try:
    LLM_API_KEY = settings.LLM_API_KEY
    LLM_API_BASE = settings.LLM_API_BASE
    LLM_MODEL_NAME = settings.LLM_MODEL_NAME
    # 拼接完整的 Chat 接口地址
    LLM_API_URL = f"{LLM_API_BASE}/chat/completions"

    # 向量模型配置
    EMBEDDING_MODEL_NAME = settings.EMBEDDING_MODEL_NAME

    # 搜索阈值配置
    VECTOR_INITIAL_THRESHOLD = settings.VECTOR_INITIAL_THRESHOLD
    VECTOR_FINAL_THRESHOLD = settings.VECTOR_FINAL_THRESHOLD
    MIN_RESULTS_THRESHOLD = settings.MIN_RESULTS_THRESHOLD
except AttributeError as e:
    logger.error(f"❌ [Config Error] Django settings缺少配置项: {e}")
    # 提供默认值（仅用于开发和测试）
    LLM_API_KEY = "156c8a37-20bf-4060-8bdc-d9991fc03eef"
    LLM_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
    LLM_MODEL_NAME = "ep-20251211173243-qklb7"
    LLM_API_URL = f"{LLM_API_BASE}/chat/completions"
    EMBEDDING_MODEL_NAME = "pritamdeka/S-PubMedBert-MS-MARCO"
    VECTOR_INITIAL_THRESHOLD = 0.1
    VECTOR_FINAL_THRESHOLD = 0.2
    MIN_RESULTS_THRESHOLD = 5

# 本地向量模型 (懒加载，防止启动报错)
LOCAL_EMBED_MODEL = None
# ==============================================================================
# 3. 安全相似度分数计算函数
# ==============================================================================
def safe_similarity_score(similarity: float) -> float:
    """确保相似度分数在0-100范围内，添加溢出警告"""
    # 记录超出理论范围的相似度（用于调试）
    if similarity < -0.01 or similarity > 1.01:  # 留出0.01的浮点误差容忍度
        logger.warning(f"⚠️ [Similarity Warning] 相似度超出理论范围: {similarity}")

    # 确保相似度在[0, 1]范围内
    similarity = max(0.0, min(1.0, similarity))
    # 转换为百分比，保留2位小数
    score = round(similarity * 100, 2)
    # 双重确保在[0, 100]范围内
    score = max(0.0, min(100.0, score))

    # 记录截断操作（仅当实际需要截断时）
    if similarity < 0 or similarity > 1:
        logger.info(f"🔧 [Similarity Fix] 相似度已从 {similarity} 修正为 {score}%")

    return score
# ==============================================================================
# 4. 阈值动态调整函数
# ==============================================================================
def get_dynamic_thresholds(query: str, candidate_count: int) -> dict:
    """
    根据查询和候选集动态调整阈值

    Args:
        query: 用户查询字符串
        candidate_count: 候选产品数量

    Returns:
        dict: 包含动态阈值的字典
    """
    # 基础阈值
    thresholds = {
        'initial_threshold': VECTOR_INITIAL_THRESHOLD,
        'final_threshold': VECTOR_FINAL_THRESHOLD,
        'min_results': MIN_RESULTS_THRESHOLD
    }

    # 根据查询长度调整阈值（长查询通常更具体）
    query_length = len(query.strip())
    if query_length > 20:
        # 长查询，降低阈值以获得更多相关结果
        thresholds['initial_threshold'] = max(0.05, thresholds['initial_threshold'] - 0.02)
        thresholds['final_threshold'] = max(0.15, thresholds['final_threshold'] - 0.02)
    elif query_length < 5:
        # 短查询，提高阈值以避免不相关结果
        thresholds['initial_threshold'] = min(0.15, thresholds['initial_threshold'] + 0.02)
        thresholds['final_threshold'] = min(0.25, thresholds['final_threshold'] + 0.02)

    # 根据候选集大小调整阈值
    if candidate_count > 100:
        # 候选集大，提高阈值以过滤噪声
        thresholds['initial_threshold'] = min(0.15, thresholds['initial_threshold'] + 0.03)
        thresholds['final_threshold'] = min(0.25, thresholds['final_threshold'] + 0.03)
    elif candidate_count < 10:
        # 候选集小，降低阈值以保证有结果
        thresholds['initial_threshold'] = max(0.05, thresholds['initial_threshold'] - 0.03)
        thresholds['final_threshold'] = max(0.15, thresholds['final_threshold'] - 0.03)

    # 根据查询是否包含中文调整（中文查询可能需要更宽松的阈值）
    # 简单检查是否包含中文字符
    has_chinese = any('\u4e00' <= char <= '\u9fff' for char in query)
    if has_chinese:
        thresholds['initial_threshold'] = max(0.05, thresholds['initial_threshold'] - 0.01)
        thresholds['final_threshold'] = max(0.15, thresholds['final_threshold'] - 0.01)

    # 确保阈值在合理范围内
    thresholds['initial_threshold'] = max(0.01, min(0.3, thresholds['initial_threshold']))
    thresholds['final_threshold'] = max(0.05, min(0.5, thresholds['final_threshold']))

    return thresholds
def get_model():
    """懒加载本地向量模型"""
    global LOCAL_EMBED_MODEL
    if LOCAL_EMBED_MODEL is None:
        try:
            logger.info(f"🚀 [System] Waking up local embedding model: {EMBEDDING_MODEL_NAME}...")
            from sentence_transformers import SentenceTransformer
            # 使用配置中的模型名称
            LOCAL_EMBED_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME)
        except Exception as e:
            logger.error(f"❌ [Error] Local Model load failed: {e}")
            return None
    return LOCAL_EMBED_MODEL
# ==============================================================================
# 2. 核心混合搜索逻辑 (Hybrid Search)
# ==============================================================================

def hybrid_search(user_query, top_k=20):
    # 延迟导入，防止循环引用
    from .models import Product, Tag

    # --- Step 1: 准备“标签白名单” ---
    # 获取数据库里所有可用的标签，告诉 AI：“只能从这里面选”
    all_tag_names = list(Tag.objects.values_list('tag_name', flat=True))

    # --- Step 2: AI 意图识别 (火山引擎) ---
    logger.info(f"🤖 [AI Thinking] 正在分析用户意图: '{user_query}' ...")
    ai_result = _analyze_intent_with_llm(user_query, all_tag_names)

    filter_tags = ai_result.get('filter_tags', [])
    english_query = ai_result.get('english_query', user_query)

    logger.info(f"🧠 [AI Result] 匹配标签: {filter_tags} | 专业转译: {english_query}")

    # --- Step 3: 数据库筛选 (Filter) ---
    # 先拿到所有有向量的数据
    candidates = Product.objects.filter(embedding__isnull=False).select_related('embedding')

    # 计算动态阈值
    candidate_count = candidates.count()
    thresholds = get_dynamic_thresholds(user_query, candidate_count)

    logger.debug(f"📊 [Thresholds] 动态阈值: 初始={thresholds['initial_threshold']:.3f}, "
                 f"最终={thresholds['final_threshold']:.3f}, 最小结果={thresholds['min_results']}")

    if filter_tags:
        # 获取标签ID列表，使用精确匹配避免误匹配
        tag_ids = _get_tag_ids_from_names(filter_tags)

        if tag_ids:
            # 使用标签ID进行精确过滤
            filtered_candidates = candidates.filter(tags__tag_id__in=tag_ids).distinct()

            # 只有在真的搜到东西时才生效，防止 AI 幻觉导致 0 结果
            if filtered_candidates.exists():
                candidates = filtered_candidates
                logger.info(f"🛡️ [Filter] 标签过滤生效，匹配标签ID: {tag_ids}，剩余 {candidates.count()} 条")
            else:
                logger.warning(f"⚠️ [Warning] 标签ID '{tag_ids}' 无对应数据，自动降级为全库搜索")
        else:
            logger.warning(f"⚠️ [Warning] 标签名称 '{filter_tags}' 在数据库中不存在，自动降级为全库搜索")

    # --- Step 4: 向量搜索 (Vector Search) ---
    # 使用 AI 翻译好的“专业英语”去匹配数据库里的 embedding_text 向量
    query_vector = _get_local_embedding(english_query)

    # 如果向量生成失败，降级返回刚才过滤的结果
    if not query_vector:
        return list(candidates)[:top_k], ai_result

    # 创建候选产品ID映射，用于快速查找
    candidate_id_map = {prod.product_id: prod for prod in candidates}

    # 使用FAISS向量索引进行高效搜索
    vector_results = search_similar_vectors(
        query_vector=query_vector,
        top_k=top_k * 3,  # 获取更多结果用于后续过滤
        threshold=thresholds['initial_threshold'],    # 使用动态初始阈值
        use_fallback=True
    )

    scored_results = []
    for product_id, similarity in vector_results:
        # 检查产品是否在候选列表中（经过标签过滤）
        if product_id in candidate_id_map:
            prod = candidate_id_map[product_id]
            # 应用最终相似度阈值（可动态调整）
            if similarity > thresholds['final_threshold']:  # 使用动态最终阈值
                prod.match_score = safe_similarity_score(similarity)
                scored_results.append(prod)

    # 如果向量搜索结果太少，补充一些过滤后的结果
    if len(scored_results) < min(thresholds['min_results'], top_k):
        logger.warning(f"⚠️ [Warning] 向量搜索结果不足({len(scored_results)})，补充过滤结果")
        backup_count = min(top_k - len(scored_results), len(candidates))
        for prod in list(candidates)[:backup_count]:
            if prod not in scored_results:
                prod.match_score = 10.0  # 赋予较低的基础分数
                scored_results.append(prod)

    scored_results.sort(key=lambda x: x.match_score, reverse=True)
    return scored_results[:top_k], ai_result
# ==============================================================================
# 3. LLM 接口 (火山引擎)
# ==============================================================================

def _analyze_intent_with_llm(query, available_tags):
    """
    通过火山引擎大模型实现：口语 -> 专业标签映射 + 学术翻译
    """
    # AI调试模式开关
    debug_mode = os.environ.get('DEBUG_AI_FILTERS', 'false').lower() == 'true'

    if debug_mode:
        logger.info(f"🧠 [AI Debug] 候选标签池大小: {len(available_tags)}")
        logger.info(f"🧠 [AI Debug] 前20个候选标签: {list(available_tags)[:20]}")
        # 记录系统Prompt摘要（过滤敏感信息如API密钥）
        # 注意：prompt_preview将在后面定义后记录

    system_prompt = f"""
    You are an expert Synthetic Biology Search Assistant specialized in molecular biology, genetic engineering, and bioinformatics.

    [CONTEXT]
    User Query: "{query}"
    Available Database Tags: {json.dumps(available_tags, ensure_ascii=False)}

    [QUERY CLASSIFICATION GUIDANCE]
    First, classify the query type to determine the best approach:
    1. **Conceptual Query**: Searching for biological concepts, mechanisms, or processes
       - Examples: "cell division", "gene expression regulation", "protein synthesis"
    2. **Product/Component Query**: Searching for specific biological components or products
       - Examples: "CRISPR-Cas9", "GFP protein", "plasmid vector"
    3. **Application Query**: Searching for applications or use cases
       - Examples: "gene therapy", "biosensors", "metabolic engineering"
    4. **Combination Query**: Multiple concepts or specific requirements
       - Examples: "CRISPR for cancer therapy", "fluorescent reporters for cell imaging"

    [TAG MAPPING TASK]
    Map the user's intent to the most relevant database tags using these guidelines:

    1. **Precision Guidelines**:
       - Prefer specific tags over general ones when appropriate
       - Use 1-3 tags maximum to avoid over-filtering
       - Only use tags from the provided list
       - Return empty list [] if no relevant tags found

    2. **Chinese Query Support**:
       - Recognize common Chinese biological terminology
       - Map Chinese colloquial expressions to scientific terms

    [SCIENTIFIC TRANSLATION TASK]
    Rewrite the query into a precise, scientific English description for PubMedBert embeddings:

    1. **Translation Principles**:
       - Use formal, academic language
       - Include key biological concepts and mechanisms
       - Focus on molecular and cellular processes
       - Use standard biological terminology

    2. **Examples**:
       - "饿死了" → "Cellular response to nutrient starvation and metabolic stress"
       - "细胞分裂" → "Molecular mechanisms of cell division and mitosis"
       - "基因编辑技术" → "CRISPR-Cas9 genome editing technology and applications"
       - "癌症治疗" → "Molecular targeted therapies for cancer treatment"
       - "荧光蛋白成像" → "Fluorescent protein imaging in live cells"

    3. **Query Enhancement**:
       - For conceptual queries: add "molecular mechanisms of" or "cellular processes in"
       - For product queries: include technical specifications if mentioned
       - For application queries: emphasize practical implementations

    [OUTPUT FORMAT]
    Return STRICTLY this JSON format, no additional text:
    {{
        "filter_tags": ["Tag1", "Tag2", "Tag3"],  # Array of tag names or empty array []
        "english_query": "Precise scientific English description for vector search"
    }}

    [QUALITY CHECKS]
    1. Tags must be EXACTLY from the available tags list
    2. English query must be in proper scientific English
    3. No markdown formatting in the JSON
    4. Keep translations concise but comprehensive
    """

    if debug_mode:
        # 记录系统Prompt摘要（过滤敏感信息如API密钥）
        prompt_preview = system_prompt[:500].replace(LLM_API_KEY, "***REDACTED***") + "..."
        logger.info(f"🧠 [AI Debug] 系统Prompt摘要: {prompt_preview}")

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": LLM_MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Output JSON only."},
            {"role": "user", "content": system_prompt}
        ],
        "temperature": 0.1
    }

    try:
        response = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=10)
        response.raise_for_status()

        if debug_mode:
            # 记录API响应（过滤敏感信息）
            response_preview = response.text[:500] + "..." if len(response.text) > 500 else response.text
            response_preview = response_preview.replace(LLM_API_KEY, "***REDACTED***")
            logger.info(f"🧠 [AI Debug] API响应预览: {response_preview}")

        result_json = response.json()

        if debug_mode:
            # 记录API响应元数据（过滤敏感信息）
            result_preview = {
                'model': result_json.get('model'),
                'choices_count': len(result_json.get('choices', [])),
                'finish_reason': result_json.get('choices', [{}])[0].get('finish_reason'),
                'usage': result_json.get('usage', {})
            }
            logger.info(f"🧠 [AI Debug] API响应元数据: {json.dumps(result_preview, ensure_ascii=False)}")

        content = result_json['choices'][0]['message']['content']

        # 清洗可能存在的 Markdown 标记
        if "```" in content:
            content = content.replace("```json", "").replace("```", "")

        # 解析JSON结果
        parsed_result = json.loads(content)

        if debug_mode:
            # 记录完整的AI解析结果
            logger.info(f"🧠 [AI Debug] AI解析的JSON结果: {json.dumps(parsed_result, ensure_ascii=False)}")

            # 分析标签选择逻辑
            selected_tags = parsed_result.get('filter_tags', [])
            if selected_tags:
                logger.info(f"🧠 [AI Debug] AI选择了{len(selected_tags)}个标签: {selected_tags}")
                # 分析哪些标签被拒绝（只记录数量，避免日志风暴）
                rejected_count = len(available_tags) - len(selected_tags)
                if rejected_count > 0:
                    logger.info(f"🧠 [AI Debug] AI拒绝了{rejected_count}个标签（不打印完整列表避免日志风暴）")
                    # 可选：只打印前几个示例
                    if rejected_count > 0 and rejected_count <= 10:
                        rejected_sample = [tag for tag in available_tags if tag not in selected_tags]
                        logger.info(f"🧠 [AI Debug] 拒绝的标签示例（前{min(5, len(rejected_sample))}个）: {rejected_sample[:5]}")
            else:
                logger.info("🧠 [AI Debug] AI未选择任何标签")

        return parsed_result

    except Exception as e:
        logger.error(f"❌ [AI Error] Volcengine Call failed: {e}")
        # 降级：如果 AI 挂了，直接用原词搜
        return {"filter_tags": [], "english_query": query}
def _get_local_embedding(text):
    model = get_model()
    if model is None: return None
    return model.encode(text).tolist()
def _get_tag_ids_from_names(tag_names):
    """将标签名称列表转换为标签ID列表，支持精确匹配和模糊匹配"""
    if not tag_names:
        return []

    try:
        from .models import Tag

        tag_ids = []

        # 首先尝试精确匹配
        exact_matches = Tag.objects.filter(tag_name__in=tag_names)
        for tag in exact_matches:
            tag_ids.append(tag.tag_id)

        # 查找已匹配的标签名称
        matched_names = set(tag.tag_name for tag in exact_matches)

        # 对于未精确匹配的标签，尝试模糊匹配
        for tag_name in tag_names:
            if tag_name in matched_names:
                continue

            # 尝试模糊匹配：忽略大小写，检查是否包含
            fuzzy_match = Tag.objects.filter(tag_name__icontains=tag_name).first()
            if fuzzy_match:
                logger.debug(f"  🔍 [Tag Match] 模糊匹配: '{tag_name}' -> '{fuzzy_match.tag_name}' (ID: {fuzzy_match.tag_id})")
                tag_ids.append(fuzzy_match.tag_id)
                matched_names.add(fuzzy_match.tag_name)
            else:
                logger.warning(f"  ⚠️ [Tag Warning] 未找到匹配的标签: '{tag_name}'")

        return list(set(tag_ids))  # 去重

    except Exception as e:
        logger.error(f"❌ [Error] 获取标签ID失败: {e}")
        return []
# ==============================================================================
# 6. 增强标签搜索系统（支持层次结构、分类和语义扩展）
# ==============================================================================

def _get_enhanced_tag_ids(tag_names, expand_hierarchy=True, include_categories=None,
                         include_pubchem=True, similarity_threshold=0.7):
    """
    增强标签搜索：支持层次结构扩展、分类过滤和语义扩展

    Args:
        tag_names: 原始标签名称列表
        expand_hierarchy: 是否扩展标签层次结构（父标签、子标签）
        include_categories: 包含的分类路径列表（如["实验技术::分子生物学技术"]）
        include_pubchem: 是否包含PubChem标签
        similarity_threshold: 语义相似度阈值（0.0-1.0）

    Returns:
        tuple: (普通标签ID列表, PubChem标签ID列表)
    """
    if not tag_names:
        return [], []

    try:
        from .models import Tag, PubChemTag, TagHierarchy, TagCategorySystem
        from django.contrib.contenttypes.models import ContentType

        tag_content_type = ContentType.objects.get_for_model(Tag)
        pubchem_tag_content_type = ContentType.objects.get_for_model(PubChemTag)

        # 基础标签ID收集
        base_tag_ids = set()
        base_pubchem_tag_ids = set()

        # 1. 基本标签匹配（精确+模糊）
        for tag_name in tag_names:
            # 尝试精确匹配普通标签
            exact_tags = Tag.objects.filter(tag_name__iexact=tag_name)
            for tag in exact_tags:
                base_tag_ids.add(tag.tag_id)
                logger.debug(f"  🔍 [Tag Match] 精确匹配: '{tag_name}' -> '{tag.tag_name}' (ID: {tag.tag_id})")

            # 尝试精确匹配PubChem标签
            exact_pubchem_tags = PubChemTag.objects.filter(tag_name__iexact=tag_name)
            for tag in exact_pubchem_tags:
                base_pubchem_tag_ids.add(tag.tag_id)
                logger.debug(f"  🔍 [PubChem Tag Match] 精确匹配: '{tag_name}' -> '{tag.tag_name}' (ID: {tag.tag_id})")

            # 如果没有精确匹配，尝试模糊匹配
            if not exact_tags.exists() and not exact_pubchem_tags.exists():
                fuzzy_tags = Tag.objects.filter(tag_name__icontains=tag_name)
                for tag in fuzzy_tags:
                    base_tag_ids.add(tag.tag_id)
                    logger.debug(f"  🔍 [Tag Match] 模糊匹配: '{tag_name}' -> '{tag.tag_name}' (ID: {tag.tag_id})")

                fuzzy_pubchem_tags = PubChemTag.objects.filter(tag_name__icontains=tag_name)
                for tag in fuzzy_pubchem_tags:
                    base_pubchem_tag_ids.add(tag.tag_id)
                    logger.debug(f"  🔍 [PubChem Tag Match] 模糊匹配: '{tag_name}' -> '{tag.tag_name}' (ID: {tag.tag_id})")

        # 最终结果集合
        final_tag_ids = set(base_tag_ids)
        final_pubchem_tag_ids = set(base_pubchem_tag_ids)

        # 2. 语义相似度扩展（使用similarity_threshold参数）
        if similarity_threshold > 0:
            semantic_tag_ids, semantic_pubchem_tag_ids = _get_semantic_similar_tags(
                tag_names, threshold=similarity_threshold, max_results=10
            )

            if semantic_tag_ids:
                logger.debug(f"  🔤 [Semantic] 语义扩展: 找到 {len(semantic_tag_ids)} 个相似普通标签")
                final_tag_ids.update(semantic_tag_ids)

            if semantic_pubchem_tag_ids:
                logger.debug(f"  🔤 [Semantic] 语义扩展: 找到 {len(semantic_pubchem_tag_ids)} 个相似PubChem标签")
                final_pubchem_tag_ids.update(semantic_pubchem_tag_ids)

        # 3. 层次结构扩展
        if expand_hierarchy and (final_tag_ids or final_pubchem_tag_ids):
            expanded_tag_ids = set()
            expanded_pubchem_tag_ids = set()

            # 扩展普通标签
            for tag_id in list(final_tag_ids):  # 使用列表副本避免修改迭代中的集合
                expanded_ids = _expand_tag_hierarchy(tag_id, tag_content_type)
                expanded_tag_ids.update(expanded_ids)

            # 扩展PubChem标签
            for tag_id in list(final_pubchem_tag_ids):
                expanded_ids = _expand_tag_hierarchy(tag_id, pubchem_tag_content_type)
                expanded_pubchem_tag_ids.update(expanded_ids)

            logger.debug(f"  🌳 [Hierarchy] 层次扩展: 普通标签 {len(final_tag_ids)} -> {len(expanded_tag_ids)}, "
                        f"PubChem标签 {len(final_pubchem_tag_ids)} -> {len(expanded_pubchem_tag_ids)}")

            final_tag_ids.update(expanded_tag_ids)
            final_pubchem_tag_ids.update(expanded_pubchem_tag_ids)

        # 4. 分类过滤或扩展
        if include_categories:
            # 如果提供了分类路径，可以有两种处理方式：
            # 1. 过滤：只保留指定分类的标签
            # 2. 扩展：添加指定分类的所有标签
            # 这里实现过滤功能
            filtered_tag_ids = set()
            filtered_pubchem_tag_ids = set()

            # 过滤普通标签
            for tag_id in final_tag_ids:
                tag = Tag.objects.filter(tag_id=tag_id).first()
                if tag and tag.tag_category:
                    # 检查标签分类是否包含在指定分类中
                    for category_path in include_categories:
                        if tag.tag_category.startswith(category_path):
                            filtered_tag_ids.add(tag_id)
                            break

            # 过滤PubChem标签
            for tag_id in final_pubchem_tag_ids:
                tag = PubChemTag.objects.filter(tag_id=tag_id).first()
                if tag and tag.tag_category:
                    for category_path in include_categories:
                        if tag.tag_category.startswith(category_path):
                            filtered_pubchem_tag_ids.add(tag_id)
                            break

            logger.debug(f"  📂 [Category] 分类过滤: 普通标签 {len(final_tag_ids)} -> {len(filtered_tag_ids)}, "
                        f"PubChem标签 {len(final_pubchem_tag_ids)} -> {len(filtered_pubchem_tag_ids)}")

            final_tag_ids = filtered_tag_ids
            final_pubchem_tag_ids = filtered_pubchem_tag_ids

        # 5. PubChem标签包含/排除
        if not include_pubchem:
            final_pubchem_tag_ids = set()

        return list(final_tag_ids), list(final_pubchem_tag_ids)

    except Exception as e:
        logger.error(f"❌ [Error] 增强标签搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return [], []
def _expand_tag_hierarchy(tag_id, content_type, max_depth=2):
    """
    扩展标签层次结构：获取父标签、子标签和相关标签

    Args:
        tag_id: 标签ID
        content_type: 标签内容类型
        max_depth: 最大扩展深度

    Returns:
        set: 扩展后的标签ID集合（包含原始标签）
    """
    try:
        from .models import TagHierarchy
        from django.contrib.contenttypes.models import ContentType

        expanded_ids = {tag_id}

        # 查找以该标签为父级的子标签（向下扩展）
        child_relations = TagHierarchy.objects.filter(
            parent_content_type=content_type,
            parent_object_id=tag_id,
            relationship_type__in=['parent_child', 'synonym', 'related']
        )[:50]  # 限制数量

        for relation in child_relations:
            expanded_ids.add(relation.child_object_id)

            # 递归扩展子标签
            if max_depth > 1:
                child_expanded = _expand_tag_hierarchy(
                    relation.child_object_id,
                    relation.child_content_type,
                    max_depth - 1
                )
                expanded_ids.update(child_expanded)

        # 查找以该标签为子级的父标签（向上扩展）
        parent_relations = TagHierarchy.objects.filter(
            child_content_type=content_type,
            child_object_id=tag_id,
            relationship_type__in=['parent_child', 'synonym', 'related']
        )[:50]

        for relation in parent_relations:
            expanded_ids.add(relation.parent_object_id)

            # 递归扩展父标签
            if max_depth > 1 and relation.parent_object_id:
                parent_expanded = _expand_tag_hierarchy(
                    relation.parent_object_id,
                    relation.parent_content_type,
                    max_depth - 1
                )
                expanded_ids.update(parent_expanded)

        # 查找兄弟标签（共享父级的标签）
        parent_relations = TagHierarchy.objects.filter(
            child_content_type=content_type,
            child_object_id=tag_id,
            relationship_type='parent_child'
        ).first()

        if parent_relations:
            sibling_relations = TagHierarchy.objects.filter(
                parent_content_type=parent_relations.parent_content_type,
                parent_object_id=parent_relations.parent_object_id,
                relationship_type='parent_child'
            ).exclude(child_object_id=tag_id)[:20]

            for relation in sibling_relations:
                expanded_ids.add(relation.child_object_id)

        return expanded_ids

    except Exception as e:
        logger.error(f"❌ [Error] 扩展标签层次失败: {e}")
        return {tag_id}
def _search_by_category(category_paths, tag_type='both'):
    """
    根据分类路径搜索标签

    Args:
        category_paths: 分类路径列表（支持通配符，如"实验技术::*"）
        tag_type: 标签类型（'general', 'pubchem', 'both'）

    Returns:
        tuple: (普通标签ID列表, PubChem标签ID列表)
    """
    try:
        from .models import Tag, PubChemTag, TagCategorySystem

        tag_ids = set()
        pubchem_tag_ids = set()

        # 获取所有匹配的分类
        matched_categories = []
        for category_path in category_paths:
            if '*' in category_path:
                # 通配符匹配
                pattern = category_path.replace('*', '%')
                categories = TagCategorySystem.objects.filter(category_path__like=pattern)
            else:
                # 精确匹配
                categories = TagCategorySystem.objects.filter(category_path=category_path)

            matched_categories.extend(categories)

        if not matched_categories:
            return [], []

        # 搜索普通标签
        if tag_type in ['general', 'both']:
            for category in matched_categories:
                if category.tag_type in ['general', 'both']:
                    # 查找分类匹配的标签
                    tags = Tag.objects.filter(tag_category__startswith=category.category_path)
                    tag_ids.update(tag.tag_id for tag in tags)

        # 搜索PubChem标签
        if tag_type in ['pubchem', 'both']:
            for category in matched_categories:
                if category.tag_type in ['pubchem', 'both']:
                    tags = PubChemTag.objects.filter(tag_category__startswith=category.category_path)
                    pubchem_tag_ids.update(tag.tag_id for tag in tags)

        logger.debug(f"  📂 [Category Search] 分类搜索: 找到 {len(tag_ids)} 个普通标签, {len(pubchem_tag_ids)} 个PubChem标签")

        return list(tag_ids), list(pubchem_tag_ids)

    except Exception as e:
        logger.error(f"❌ [Error] 分类搜索失败: {e}")
        return [], []
def _get_semantic_similar_tags(tag_names, threshold=0.7, max_results=10):
    """
    获取语义相似的标签（基于AI分析或预定义同义词）

    Args:
        tag_names: 原始标签名称列表
        threshold: 相似度阈值
        max_results: 最大结果数量

    Returns:
        tuple: (相似普通标签ID列表, 相似PubChem标签ID列表)
    """
    # 注：这是一个简化的实现，实际应用中可以使用向量嵌入或同义词表
    # 这里使用简单的字符串相似度和预定义规则

    try:
        from .models import Tag, PubChemTag
        import difflib

        tag_ids = set()
        pubchem_tag_ids = set()

        # 获取所有标签名称
        all_tag_names = list(Tag.objects.values_list('tag_name', flat=True))
        all_pubchem_tag_names = list(PubChemTag.objects.values_list('tag_name', flat=True))

        for tag_name in tag_names:
            # 字符串相似度匹配（普通标签）
            similar_tags = difflib.get_close_matches(
                tag_name, all_tag_names, n=max_results, cutoff=threshold
            )

            for similar_name in similar_tags:
                tag = Tag.objects.filter(tag_name=similar_name).first()
                if tag:
                    tag_ids.add(tag.tag_id)

            # 字符串相似度匹配（PubChem标签）
            similar_pubchem_tags = difflib.get_close_matches(
                tag_name, all_pubchem_tag_names, n=max_results, cutoff=threshold
            )

            for similar_name in similar_pubchem_tags:
                tag = PubChemTag.objects.filter(tag_name=similar_name).first()
                if tag:
                    pubchem_tag_ids.add(tag.tag_id)

        # 预定义同义词扩展
        synonym_map = {
            'PCR': ['Polymerase Chain Reaction', 'PCR assay', 'DNA amplification'],
            'GFP': ['Green Fluorescent Protein', 'fluorescent protein'],
            'HPLC': ['High Performance Liquid Chromatography', 'liquid chromatography'],
            'MS': ['Mass Spectrometry', 'mass spec'],
            'RNA': ['Ribonucleic Acid', 'RNA extraction', 'RNA sequencing'],
        }

        for tag_name in tag_names:
            if tag_name in synonym_map:
                synonyms = synonym_map[tag_name]
                for synonym in synonyms:
                    # 查找普通标签
                    tag = Tag.objects.filter(tag_name__iexact=synonym).first()
                    if tag:
                        tag_ids.add(tag.tag_id)

                    # 查找PubChem标签
                    pubchem_tag = PubChemTag.objects.filter(tag_name__iexact=synonym).first()
                    if pubchem_tag:
                        pubchem_tag_ids.add(pubchem_tag.tag_id)

        logger.debug(f"  🔤 [Semantic] 语义扩展: 找到 {len(tag_ids)} 个相似普通标签, {len(pubchem_tag_ids)} 个相似PubChem标签")

        return list(tag_ids), list(pubchem_tag_ids)

    except Exception as e:
        logger.error(f"❌ [Error] 语义相似标签搜索失败: {e}")
        return [], []
def hybrid_search_enhanced(user_query, top_k=20, use_enhanced_tags=True):
    """
    增强版混合搜索：集成标签层次结构、分类系统和语义扩展

    Args:
        user_query: 用户查询
        top_k: 返回结果数量
        use_enhanced_tags: 是否使用增强标签搜索

    Returns:
        tuple: (搜索结果列表, AI分析结果)
    """
    # 延迟导入，防止循环引用
    from .models import Product, Tag

    # --- Step 1: 准备“标签白名单” ---
    all_tag_names = list(Tag.objects.values_list('tag_name', flat=True))

    # --- Step 2: AI 意图识别 ---
    logger.info(f"🤖 [AI Thinking] 正在分析用户意图: '{user_query}' ...")
    ai_result = _analyze_intent_with_llm(user_query, all_tag_names)

    filter_tags = ai_result.get('filter_tags', [])
    english_query = ai_result.get('english_query', user_query)

    logger.info(f"🧠 [AI Result] 匹配标签: {filter_tags} | 专业转译: {english_query}")

    # --- Step 3: 数据库筛选 (Filter) ---
    candidates = Product.objects.filter(embedding__isnull=False).select_related('embedding')

    # 计算动态阈值
    candidate_count = candidates.count()
    thresholds = get_dynamic_thresholds(user_query, candidate_count)

    logger.debug(f"📊 [Thresholds] 动态阈值: 初始={thresholds['initial_threshold']:.3f}, "
                 f"最终={thresholds['final_threshold']:.3f}, 最小结果={thresholds['min_results']}")

    if filter_tags and use_enhanced_tags:
        # 使用增强标签搜索
        tag_ids, pubchem_tag_ids = _get_enhanced_tag_ids(
            filter_tags,
            expand_hierarchy=True,
            include_categories=None,
            include_pubchem=True,
            similarity_threshold=0.6
        )

        # 合并标签ID
        all_tag_ids = tag_ids.copy()

        # 如果有PubChem标签ID，需要特殊处理
        if pubchem_tag_ids:
            # 同时过滤普通标签和PubChem标签
            from django.db.models import Q

            # 构建查询条件
            tag_query = Q(tags__tag_id__in=all_tag_ids) if all_tag_ids else Q()
            pubchem_query = Q(pubchem_tags__tag_id__in=pubchem_tag_ids) if pubchem_tag_ids else Q()

            # 应用过滤
            filtered_candidates = candidates.filter(tag_query | pubchem_query).distinct()

            if filtered_candidates.exists():
                candidates = filtered_candidates
                logger.info(f"🛡️ [Enhanced Filter] 增强标签过滤生效: "
                          f"普通标签 {len(tag_ids)} 个, PubChem标签 {len(pubchem_tag_ids)} 个, "
                          f"剩余 {candidates.count()} 条结果")
            else:
                logger.warning("⚠️ [Warning] 增强标签过滤无结果，自动降级为全库搜索")
        elif all_tag_ids:
            # 仅普通标签过滤
            filtered_candidates = candidates.filter(tags__tag_id__in=all_tag_ids).distinct()

            if filtered_candidates.exists():
                candidates = filtered_candidates
                logger.info(f"🛡️ [Enhanced Filter] 标签过滤生效，匹配标签ID: {all_tag_ids}，"
                          f"剩余 {candidates.count()} 条")
            else:
                logger.warning("⚠️ [Warning] 标签过滤无结果，自动降级为全库搜索")
    elif filter_tags:
        # 使用原始标签过滤（向后兼容）
        tag_ids = _get_tag_ids_from_names(filter_tags)

        if tag_ids:
            filtered_candidates = candidates.filter(tags__tag_id__in=tag_ids).distinct()

            if filtered_candidates.exists():
                candidates = filtered_candidates
                logger.info(f"🛡️ [Filter] 标签过滤生效，匹配标签ID: {tag_ids}，剩余 {candidates.count()} 条")
            else:
                logger.warning("⚠️ [Warning] 标签ID无对应数据，自动降级为全库搜索")
        else:
            logger.warning("⚠️ [Warning] 标签名称在数据库中不存在，自动降级为全库搜索")

    # --- Step 4: 向量搜索 (Vector Search) ---
    query_vector = _get_local_embedding(english_query)

    if not query_vector:
        return list(candidates)[:top_k], ai_result

    # 创建候选产品ID映射
    candidate_id_map = {prod.product_id: prod for prod in candidates}

    # 使用FAISS向量索引进行高效搜索
    vector_results = search_similar_vectors(
        query_vector=query_vector,
        top_k=top_k * 3,
        threshold=thresholds['initial_threshold'],
        use_fallback=True
    )

    scored_results = []
    for product_id, similarity in vector_results:
        if product_id in candidate_id_map:
            prod = candidate_id_map[product_id]
            if similarity > thresholds['final_threshold']:
                prod.match_score = safe_similarity_score(similarity)
                scored_results.append(prod)

    # 如果向量搜索结果太少，补充一些过滤后的结果
    if len(scored_results) < min(thresholds['min_results'], top_k):
        logger.warning(f"⚠️ [Warning] 向量搜索结果不足({len(scored_results)})，补充过滤结果")
        backup_count = min(top_k - len(scored_results), len(candidates))
        for prod in list(candidates)[:backup_count]:
            if prod not in scored_results:
                prod.match_score = 10.0
                scored_results.append(prod)

    scored_results.sort(key=lambda x: x.match_score, reverse=True)
    return scored_results[:top_k], ai_result