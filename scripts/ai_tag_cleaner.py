#!/usr/bin/env python
"""
AI智能标签清洗器

功能：
1. 标签语义分析：使用火山引擎AI分析标签含义和上下文
2. 标签分类系统：基于AI分析为标签自动分配类别
3. 标签层次构建：构建标签的父子层次结构
"""
import os
import sys
import django
import time
import json
import requests
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict, Counter
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import Tag, ProductTag, Product

# ==============================================================================
# 配置区域 (火山引擎)
# ==============================================================================
LLM_API_KEY = "156c8a37-20bf-4060-8bdc-d9991fc03eef"
LLM_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
LLM_MODEL_NAME = "ep-20251211173243-qklb7"
LLM_API_URL = f"{LLM_API_BASE}/chat/completions"

class TagSemanticAnalyzer:
    """标签语义分析器"""

    def __init__(self, delay: float = 0.3, max_retries: int = 3):
        """
        初始化分析器

        Args:
            delay: API调用之间的延迟(秒)
            max_retries: 最大重试次数
        """
        self.delay = delay
        self.max_retries = max_retries
        self.headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json"
        }

    def call_ai_api_with_retry(self, prompt: str, temperature: float = 0.1) -> Optional[str]:
        """
        带重试机制的AI API调用

        Args:
            prompt: 提示词
            temperature: 温度参数

        Returns:
            API响应内容，失败时返回None
        """
        payload = {
            "model": LLM_MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        }

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(LLM_API_URL, headers=self.headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    return resp.json()['choices'][0]['message']['content'].strip()
                else:
                    print(f"API调用失败 (尝试 {attempt+1}/{self.max_retries}): {resp.status_code}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.delay * (2 ** attempt))
            except Exception as e:
                print(f"API调用异常 (尝试 {attempt+1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.delay * (2 ** attempt))

        return None

    def analyze_tag_meaning(self, tag_name: str, context: str = "") -> Dict[str, Any]:
        """
        分析标签含义

        Args:
            tag_name: 标签名称
            context: 上下文信息（可选）

        Returns:
            语义分析结果
        """
        prompt = f"""
        请分析以下生物技术/化学标签的含义：

        标签: "{tag_name}"
        {f"上下文: {context}" if context else ""}

        请提供以下分析：
        1. 核心含义：用1-2句话解释这个标签在生物技术/化学领域的含义
        2. 领域：选择主要领域（分子生物学、细胞生物学、生物化学、遗传学、药理学、化学合成、分析技术、其他）
        3. 具体类别：更具体的分类（如：基因操作、蛋白表达、细胞培养、分析方法、化合物类型、反应类型等）
        4. 常见同义词：列出常见的同义词或变体
        5. 相关标签：列出相关的其他标签

        请以JSON格式返回，结构如下：
        {{
            "core_meaning": "解释文本",
            "domain": "主要领域",
            "specific_category": "具体类别",
            "synonyms": ["同义词1", "同义词2", ...],
            "related_tags": ["相关标签1", "相关标签2", ...],
            "confidence": 0.95
        }}

        只返回JSON，不要其他文本。
        """

        result = self.call_ai_api_with_retry(prompt)
        if not result:
            return self._get_default_analysis(tag_name)

        return self._parse_ai_response(result, tag_name)

    def analyze_tag_relationship(self, tag1: str, tag2: str) -> Dict[str, Any]:
        """
        分析两个标签之间的关系

        Args:
            tag1: 第一个标签
            tag2: 第二个标签

        Returns:
            关系分析结果
        """
        prompt = f"""
        请分析以下两个生物技术标签之间的关系：

        标签1: "{tag1}"
        标签2: "{tag2}"

        请判断它们之间的关系类型：
        1. 父子关系（一个包含另一个）
        2. 兄弟关系（同一父级下的同级概念）
        3. 同义词关系（含义相同或高度相似）
        4. 相关关系（有逻辑关联但不是层级关系）
        5. 无关系

        请以JSON格式返回，结构如下：
        {{
            "relationship_type": "父子|兄弟|同义词|相关|无关系",
            "description": "关系描述",
            "direction": "父->子 或 子->父（如果是父子关系）",
            "confidence": 0.95
        }}

        只返回JSON，不要其他文本。
        """

        result = self.call_ai_api_with_retry(prompt)
        if not result:
            return {
                "relationship_type": "无关系",
                "description": f"无法分析 {tag1} 和 {tag2} 的关系",
                "direction": "",
                "confidence": 0.5
            }

        try:
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return json.loads(result)
        except:
            return {
                "relationship_type": "无关系",
                "description": f"无法解析 {tag1} 和 {tag2} 的关系分析",
                "direction": "",
                "confidence": 0.5
            }

    def batch_analyze_tags(self, tags: List[str], batch_size: int = 10) -> List[Dict[str, Any]]:
        """
        批量分析标签

        Args:
            tags: 标签名称列表
            batch_size: 每批大小

        Returns:
            分析结果列表
        """
        if not tags:
            return []

        results = []

        for i in range(0, len(tags), batch_size):
            batch = tags[i:i + batch_size]
            batch_str = "\n".join([f"- {tag}" for tag in batch])

            prompt = f"""
            请批量分析以下生物技术标签：

            {batch_str}

            对于每个标签，请提供：
            1. 领域分类（分子生物学、细胞生物学、生物化学、遗传学、药理学、化学合成、分析技术、其他）
            2. 具体用途/含义
            3. 推荐的标准分类标签（从以下选择：实验方法、化合物类型、生物过程、细胞组件、分子功能、疾病相关、其他）

            请以JSON格式返回，结构如下：
            {{
                "analyzed_tags": [
                    {{
                        "tag_name": "标签名",
                        "domain": "领域",
                        "purpose": "用途描述",
                        "recommended_category": "推荐分类",
                        "confidence": 0.95
                    }},
                    ...
                ]
            }}

            只返回JSON，不要其他文本。
            """

            result = self.call_ai_api_with_retry(prompt, temperature=0.2)
            if not result:
                # 降级为逐个分析
                for tag in batch:
                    analysis = self.analyze_tag_meaning(tag)
                    results.append({
                        "tag_name": tag,
                        "domain": analysis.get("domain", "其他"),
                        "purpose": analysis.get("core_meaning", ""),
                        "recommended_category": analysis.get("specific_category", "其他"),
                        "confidence": analysis.get("confidence", 0.5)
                    })
                    time.sleep(self.delay)
            else:
                try:
                    import re
                    json_match = re.search(r'\{.*\}', result, re.DOTALL)
                    if json_match:
                        batch_result = json.loads(json_match.group())
                    else:
                        batch_result = json.loads(result)

                    for item in batch_result.get("analyzed_tags", []):
                        results.append(item)
                except:
                    # 降级为逐个分析
                    for tag in batch:
                        analysis = self.analyze_tag_meaning(tag)
                        results.append({
                            "tag_name": tag,
                            "domain": analysis.get("domain", "其他"),
                            "purpose": analysis.get("core_meaning", ""),
                            "recommended_category": analysis.get("specific_category", "其他"),
                            "confidence": analysis.get("confidence", 0.5)
                        })
                        time.sleep(self.delay)

            # 批次延迟
            if i + batch_size < len(tags):
                time.sleep(self.delay * batch_size)

        return results

    def _get_default_analysis(self, tag_name: str) -> Dict[str, Any]:
        """获取默认分析结果"""
        # 简单规则匹配
        tag_lower = tag_name.lower()

        domain = "其他"
        category = "其他"

        # 领域检测
        domain_keywords = {
            "分子生物学": ["gene", "dna", "rna", "pcr", "sequencing", "克隆", "表达"],
            "细胞生物学": ["cell", "culture", "培养基", "培养", "转染", "凋亡"],
            "生物化学": ["enzyme", "protein", "代谢", "pathway", "kinase", "磷酸"],
            "化学合成": ["synthesis", "合成", "reaction", "反应", "catalyst", "催化"],
            "分析技术": ["hplc", "lc-ms", "色谱", "质谱", "spectrum", "分析"]
        }

        for dom, keywords in domain_keywords.items():
            if any(keyword in tag_lower for keyword in keywords):
                domain = dom
                break

        # 分类检测
        category_keywords = {
            "实验方法": ["assay", "检测", "method", "protocol", "技术", "方案"],
            "化合物类型": ["acid", "acid", "base", "碱", "salt", "盐", "compound", "化合物"],
            "生物过程": ["metabolism", "代谢", "signaling", "信号", "regulation", "调控"],
            "分子功能": ["binding", "结合", "activity", "活性", "inhibition", "抑制"]
        }

        for cat, keywords in category_keywords.items():
            if any(keyword in tag_lower for keyword in keywords):
                category = cat
                break

        return {
            "core_meaning": f"Biotechnology concept: {tag_name}",
            "domain": domain,
            "specific_category": category,
            "synonyms": [],
            "related_tags": [],
            "confidence": 0.6
        }

    def _parse_ai_response(self, response: str, tag_name: str) -> Dict[str, Any]:
        """解析AI响应"""
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return json.loads(response)
        except json.JSONDecodeError:
            print(f"无法解析AI响应为JSON: {response[:200]}")
            return self._get_default_analysis(tag_name)

class TagCategorizationSystem:
    """标签分类系统"""

    # 预定义分类体系
    CATEGORY_HIERARCHY = {
        "实验技术": {
            "分子生物学技术": ["PCR", "测序", "克隆", "基因编辑", "蛋白质印迹"],
            "细胞生物学技术": ["细胞培养", "转染", "流式细胞术", "免疫荧光"],
            "分析检测技术": ["HPLC", "质谱", "色谱", "光谱分析", "电泳"]
        },
        "化合物类别": {
            "有机化合物": ["氨基酸", "核苷酸", "糖类", "脂质"],
            "无机化合物": ["盐类", "酸", "碱", "金属离子"],
            "生物大分子": ["蛋白质", "核酸", "多糖", "脂质复合物"]
        },
        "生物过程": {
            "代谢过程": ["糖代谢", "脂代谢", "氨基酸代谢", "能量代谢"],
            "细胞过程": ["细胞分裂", "细胞凋亡", "细胞信号", "细胞迁移"],
            "遗传过程": ["DNA复制", "转录", "翻译", "基因表达调控"]
        },
        "疾病相关": {
            "癌症相关": ["肿瘤", "癌细胞", "抗癌", "肿瘤抑制"],
            "神经疾病": ["阿尔茨海默", "帕金森", "抑郁症", "自闭症"],
            "代谢疾病": ["糖尿病", "肥胖症", "高血压", "高血脂"]
        },
        "应用领域": {
            "药物研发": ["药物发现", "药效评价", "毒性测试", "临床试验"],
            "农业生物": ["转基因作物", "农药", "肥料", "植物育种"],
            "环境科学": ["生物修复", "污染物检测", "环境监测", "生态保护"]
        }
    }

    def __init__(self, analyzer: TagSemanticAnalyzer):
        self.analyzer = analyzer
        self.category_cache = {}  # 标签->分类缓存

    def categorize_tag(self, tag_name: str, analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        为标签分配分类

        Args:
            tag_name: 标签名称
            analysis: 语义分析结果（可选）

        Returns:
            分类结果
        """
        if tag_name in self.category_cache:
            return self.category_cache[tag_name]

        if not analysis:
            analysis = self.analyzer.analyze_tag_meaning(tag_name)

        # 基于AI分析推荐分类
        recommended_category = analysis.get("recommended_category", "") if "recommended_category" in analysis else analysis.get("specific_category", "")

        # 匹配预定义分类
        matched_category = self._match_predefined_category(tag_name, analysis, recommended_category)

        # 如果没匹配到，使用AI推荐或默认
        if not matched_category:
            if recommended_category:
                # 将AI推荐映射到我们的分类体系
                matched_category = self._map_ai_category(recommended_category)
            else:
                matched_category = {
                    "main_category": "其他",
                    "sub_category": "未分类",
                    "confidence": 0.5,
                    "reason": "未找到匹配分类"
                }

        self.category_cache[tag_name] = matched_category
        return matched_category

    def _match_predefined_category(self, tag_name: str, analysis: Dict[str, Any], recommended: str) -> Optional[Dict[str, Any]]:
        """匹配预定义分类"""
        tag_lower = tag_name.lower()
        domain = analysis.get("domain", "").lower()
        purpose = analysis.get("core_meaning", "").lower()

        best_match = None
        best_score = 0

        # 遍历分类体系寻找匹配
        for main_cat, sub_cats in self.CATEGORY_HIERARCHY.items():
            # 检查主分类关键词
            main_score = self._calculate_category_score(tag_lower, domain, purpose, main_cat.lower())

            for sub_cat, examples in sub_cats.items():
                # 检查子分类关键词和例子
                sub_score = self._calculate_category_score(tag_lower, domain, purpose, sub_cat.lower())

                # 检查例子
                example_score = 0
                for example in examples:
                    if example.lower() in tag_lower:
                        example_score = 0.8
                        break

                total_score = max(main_score, sub_score, example_score)

                if total_score > best_score:
                    best_score = total_score
                    best_match = {
                        "main_category": main_cat,
                        "sub_category": sub_cat,
                        "confidence": total_score,
                        "reason": f"匹配到'{main_cat} > {sub_cat}'分类"
                    }

        # 如果匹配分数足够高，返回结果
        if best_match and best_score >= 0.3:
            return best_match

        return None

    def _calculate_category_score(self, tag: str, domain: str, purpose: str, category: str) -> float:
        """计算分类匹配分数"""
        score = 0

        # 标签直接包含分类关键词
        if category in tag:
            score += 0.5

        # 领域包含分类关键词
        if category in domain:
            score += 0.3

        # 用途包含分类关键词
        if category in purpose:
            score += 0.2

        return min(score, 1.0)

    def _map_ai_category(self, ai_category: str) -> Dict[str, Any]:
        """将AI推荐分类映射到我们的体系"""
        ai_lower = ai_category.lower()

        mapping = {
            "实验方法": ("实验技术", "分子生物学技术"),
            "化合物类型": ("化合物类别", "有机化合物"),
            "生物过程": ("生物过程", "代谢过程"),
            "分子功能": ("生物过程", "细胞过程"),
            "疾病相关": ("疾病相关", "癌症相关")
        }

        for ai_key, (main_cat, sub_cat) in mapping.items():
            if ai_key.lower() in ai_lower:
                return {
                    "main_category": main_cat,
                    "sub_category": sub_cat,
                    "confidence": 0.7,
                    "reason": f"AI推荐分类'{ai_category}'映射到'{main_cat} > {sub_cat}'"
                }

        # 默认映射
        return {
            "main_category": "其他",
            "sub_category": ai_category if ai_category else "未分类",
            "confidence": 0.5,
            "reason": "AI推荐分类无法映射到现有体系"
        }

class TagHierarchyBuilder:
    """标签层次构建器"""

    def __init__(self, analyzer: TagSemanticAnalyzer):
        self.analyzer = analyzer
        self.parent_child_map = defaultdict(list)
        self.child_parent_map = {}

    def build_hierarchy(self, tags: List[str]) -> Dict[str, Any]:
        """
        构建标签层次结构

        Args:
            tags: 标签列表

        Returns:
            层次结构
        """
        if len(tags) < 2:
            return {"hierarchy": [], "orphan_tags": tags}

        print(f"开始构建 {len(tags)} 个标签的层次结构...")

        # 分析标签之间的关系
        self._analyze_relationships(tags)

        # 识别根节点（没有父级的标签）
        root_tags = [tag for tag in tags if tag not in self.child_parent_map]

        # 构建树结构
        hierarchy = []
        for root in root_tags[:20]:  # 限制根节点数量
            tree = self._build_tree(root)
            if tree:
                hierarchy.append(tree)

        # 孤立标签（没有在层次中的标签）
        all_in_hierarchy = set()
        for tree in hierarchy:
            self._collect_tags(tree, all_in_hierarchy)

        orphan_tags = [tag for tag in tags if tag not in all_in_hierarchy]

        return {
            "hierarchy": hierarchy,
            "orphan_tags": orphan_tags,
            "relationship_count": len(self.parent_child_map)
        }

    def _analyze_relationships(self, tags: List[str]):
        """分析标签之间的关系"""
        # 采样分析，避免组合爆炸
        sample_size = min(50, len(tags))
        sample_tags = tags[:sample_size]

        print(f"采样分析 {sample_size} 个标签之间的关系...")

        for i in range(sample_size):
            for j in range(i + 1, sample_size):
                tag1, tag2 = sample_tags[i], sample_tags[j]

                # 分析关系
                relation = self.analyzer.analyze_tag_relationship(tag1, tag2)

                if relation["confidence"] > 0.7:
                    rel_type = relation["relationship_type"]

                    if rel_type == "父子":
                        direction = relation.get("direction", "")
                        if "父->子" in direction:
                            parent, child = tag1, tag2
                        elif "子->父" in direction:
                            parent, child = tag2, tag1
                        else:
                            # 尝试推断方向
                            if len(tag1) < len(tag2):  # 简化的启发式规则
                                parent, child = tag1, tag2
                            else:
                                parent, child = tag2, tag1

                        # 添加关系
                        self.parent_child_map[parent].append(child)
                        self.child_parent_map[child] = parent

    def _build_tree(self, root_tag: str) -> Dict[str, Any]:
        """构建以root_tag为根的树"""
        tree = {
            "tag": root_tag,
            "children": []
        }

        if root_tag in self.parent_child_map:
            for child in self.parent_child_map[root_tag]:
                child_tree = self._build_tree(child)
                if child_tree:
                    tree["children"].append(child_tree)

        return tree

    def _collect_tags(self, tree: Dict[str, Any], tag_set: Set[str]):
        """收集树中的所有标签"""
        tag_set.add(tree["tag"])
        for child in tree["children"]:
            self._collect_tags(child, tag_set)

class TagCleaner:
    """标签清洗器（主类）"""

    def __init__(self, batch_size: int = 50, delay: float = 0.5):
        self.batch_size = batch_size
        self.delay = delay
        self.analyzer = TagSemanticAnalyzer(delay=delay)
        self.categorizer = TagCategorizationSystem(self.analyzer)
        self.hierarchy_builder = TagHierarchyBuilder(self.analyzer)

        # 统计信息
        self.stats = {
            "total_tags": 0,
            "processed_tags": 0,
            "categorized_tags": 0,
            "failed_tags": 0,
            "start_time": None,
            "end_time": None
        }

    def clean_all_tags(self, limit: int = None) -> Dict[str, Any]:
        """
        清洗所有标签

        Args:
            limit: 限制处理数量

        Returns:
            清洗结果
        """
        self.stats["start_time"] = time.time()

        # 获取所有标签
        tags = Tag.objects.all()
        total = tags.count()

        if limit:
            tags = tags[:limit]
            total = min(total, limit)

        self.stats["total_tags"] = total

        print(f"开始清洗 {total} 个标签...")

        success_count = 0
        fail_count = 0

        # 分批处理
        for i in range(0, total, self.batch_size):
            batch = tags[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (total + self.batch_size - 1) // self.batch_size

            print(f"\n处理批次 {batch_num}/{total_batches} ({len(batch)} 个标签)")

            # 获取标签名称列表用于批量分析
            tag_names = [tag.tag_name for tag in batch]

            # 批量分析
            print(f"  批量分析语义...")
            analyses = self.analyzer.batch_analyze_tags(tag_names, batch_size=10)

            # 处理每个标签
            for j, tag in enumerate(batch):
                if j < len(analyses):
                    analysis = analyses[j]
                    if self._clean_single_tag(tag, analysis):
                        success_count += 1
                    else:
                        fail_count += 1
                else:
                    print(f"  警告: 没有分析结果 for {tag.tag_name}")
                    fail_count += 1

            # 批次延迟
            if i + self.batch_size < total:
                time.sleep(self.delay * self.batch_size)

        self.stats["processed_tags"] = success_count + fail_count
        self.stats["failed_tags"] = fail_count
        self.stats["end_time"] = time.time()

        # 构建层次结构
        print("\n构建标签层次结构...")
        all_tag_names = list(Tag.objects.values_list('tag_name', flat=True))
        hierarchy_result = self.hierarchy_builder.build_hierarchy(all_tag_names[:100])  # 限制数量

        return {
            "stats": self.stats,
            "hierarchy": hierarchy_result,
            "success_count": success_count,
            "fail_count": fail_count,
            "success_rate": success_count / total if total > 0 else 0
        }

    def _clean_single_tag(self, tag: Tag, analysis: Dict[str, Any]) -> bool:
        """
        清洗单个标签

        Args:
            tag: Tag实例
            analysis: 语义分析结果

        Returns:
            是否成功
        """
        try:
            # 1. 分类标签
            categorization = self.categorizer.categorize_tag(tag.tag_name, analysis)

            # 2. 更新标签信息
            old_category = tag.tag_category
            new_category = f"{categorization['main_category']}::{categorization['sub_category']}"

            if old_category != new_category:
                tag.tag_category = new_category
                print(f"  更新分类: {tag.tag_name} -> {new_category} (置信度: {categorization['confidence']:.2f})")

            # 3. 保存额外信息（如果有相应字段）
            if hasattr(tag, 'semantic_data'):
                tag.semantic_data = json.dumps({
                    "analysis": analysis,
                    "categorization": categorization,
                    "cleaned_at": time.strftime("%Y-%m-%d %H:%M:%S")
                })

            # 4. 保存标签
            tag.save()
            self.stats["categorized_tags"] += 1

            return True

        except Exception as e:
            print(f"  清洗失败 {tag.tag_name}: {e}")
            return False

    def detect_and_merge_duplicates(self) -> Dict[str, Any]:
        """
        检测并合并重复标签

        Returns:
            合并结果
        """
        print("检测重复标签...")

        # 获取所有标签
        tags = Tag.objects.all()
        tag_names = [tag.tag_name for tag in tags]

        # 简单的重复检测（精确匹配）
        name_counter = Counter(tag_names)
        duplicate_names = [name for name, count in name_counter.items() if count > 1]

        print(f"找到 {len(duplicate_names)} 个重复标签名称")

        merged_count = 0

        for name in duplicate_names:
            duplicate_tags = Tag.objects.filter(tag_name=name)

            if duplicate_tags.count() < 2:
                continue

            print(f"\n处理重复: {name} ({duplicate_tags.count()} 个实例)")

            # 选择保留的标签（选择有分类的，或者第一个）
            keep_tag = None
            for tag in duplicate_tags:
                if tag.tag_category:
                    keep_tag = tag
                    break

            if not keep_tag:
                keep_tag = duplicate_tags.first()

            merge_tags = duplicate_tags.exclude(tag_id=keep_tag.tag_id)

            print(f"  保留: {keep_tag.tag_id}, 合并: {merge_tags.count()} 个标签")

            # 转移关联关系
            for merge_tag in merge_tags:
                product_relations = ProductTag.objects.filter(tag=merge_tag)

                for relation in product_relations:
                    # 检查是否已有关联
                    existing = ProductTag.objects.filter(
                        product=relation.product,
                        tag=keep_tag
                    ).exists()

                    if not existing:
                        ProductTag.objects.create(
                            product=relation.product,
                            tag=keep_tag
                        )

                # 删除旧标签
                merge_tag.delete()
                merged_count += 1

        return {
            "duplicate_names": duplicate_names,
            "merged_count": merged_count
        }

    def generate_report(self) -> Dict[str, Any]:
        """
        生成清洗报告

        Returns:
            报告数据
        """
        # 分类统计
        tags = Tag.objects.all()
        category_stats = {}

        for tag in tags:
            if tag.tag_category:
                main_cat = tag.tag_category.split("::")[0] if "::" in tag.tag_category else tag.tag_category
                category_stats[main_cat] = category_stats.get(main_cat, 0) + 1

        # 计算处理时间
        duration = 0
        if self.stats["start_time"] and self.stats["end_time"]:
            duration = self.stats["end_time"] - self.stats["start_time"]

        return {
            "summary": {
                "total_tags": tags.count(),
                "categorized_tags": sum(category_stats.values()),
                "uncategorized_tags": tags.count() - sum(category_stats.values()),
                "category_distribution": category_stats,
                "processing_time_seconds": duration,
                "tags_per_second": self.stats["processed_tags"] / duration if duration > 0 else 0
            },
            "stats": self.stats
        }

def main():
    """主函数"""
    print("AI智能标签清洗器")
    print("=" * 50)

    # 检查当前状态
    total_tags = Tag.objects.count()
    categorized_tags = Tag.objects.filter(tag_category__isnull=False).count()
    uncategorized_tags = total_tags - categorized_tags

    print(f"标签总数: {total_tags}")
    print(f"已分类标签: {categorized_tags}")
    print(f"未分类标签: {uncategorized_tags}")

    if uncategorized_tags == 0:
        print("\n所有标签已分类，无需清洗。")
        return

    cleaner = TagCleaner(batch_size=30, delay=0.4)

    print("\n选项:")
    print("1. 清洗所有未分类标签")
    print("2. 清洗指定数量的标签")
    print("3. 检测并合并重复标签")
    print("4. 生成当前状态报告")
    print("5. 完整清洗流程（1→3→4）")

    choice = input("\n请选择 (1-5): ").strip()

    if choice == '1':
        # 清洗所有标签
        confirm = input(f"确认清洗所有 {uncategorized_tags} 个未分类标签? (y/n): ").lower() == 'y'
        if confirm:
            result = cleaner.clean_all_tags()
            print("\n清洗完成!")
            print(f"处理总数: {result['stats']['processed_tags']}")
            print(f"成功: {result['success_count']}")
            print(f"失败: {result['fail_count']}")
            print(f"成功率: {result['success_rate']:.2%}")

            # 保存层次结构到文件
            save_hierarchy = input("\n是否保存层次结构到JSON文件? (y/n): ").lower() == 'y'
            if save_hierarchy:
                import json
                filename = f"tag_hierarchy_{int(time.time())}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(result['hierarchy'], f, indent=2, ensure_ascii=False)
                print(f"层次结构已保存到 {filename}")
        else:
            print("取消清洗")

    elif choice == '2':
        # 清洗指定数量
        limit_input = input("处理数量限制: ").strip()
        try:
            limit = int(limit_input)
            result = cleaner.clean_all_tags(limit=limit)
            print("\n清洗完成!")
            print(f"处理总数: {result['stats']['processed_tags']}")
            print(f"成功: {result['success_count']}")
            print(f"失败: {result['fail_count']}")
            print(f"成功率: {result['success_rate']:.2%}")
        except ValueError:
            print("无效的数量")

    elif choice == '3':
        # 检测合并重复
        result = cleaner.detect_and_merge_duplicates()
        print("\n重复检测完成:")
        print(f"重复标签名称: {len(result['duplicate_names'])} 个")
        print(f"合并标签数: {result['merged_count']}")

    elif choice == '4':
        # 生成报告
        report = cleaner.generate_report()
        print("\n当前状态报告:")
        print(f"标签总数: {report['summary']['total_tags']}")
        print(f"已分类: {report['summary']['categorized_tags']}")
        print(f"未分类: {report['summary']['uncategorized_tags']}")
        print("\n分类分布:")
        for category, count in report['summary']['category_distribution'].items():
            print(f"  {category}: {count}")

    elif choice == '5':
        # 完整流程
        print("开始完整清洗流程...")

        print("\n=== 步骤1: 清洗所有标签 ===")
        result1 = cleaner.clean_all_tags()

        print("\n=== 步骤2: 检测合并重复 ===")
        result2 = cleaner.detect_and_merge_duplicates()

        print("\n=== 步骤3: 生成最终报告 ===")
        report = cleaner.generate_report()

        print("\n完整清洗完成!")
        print(f"清洗标签: {result1['success_count']}/{result1['stats']['processed_tags']}")
        print(f"合并重复: {result2['merged_count']} 个标签")
        print(f"最终已分类标签: {report['summary']['categorized_tags']}/{report['summary']['total_tags']}")

        # 保存完整报告
        save_report = input("\n是否保存完整报告到JSON文件? (y/n): ").lower() == 'y'
        if save_report:
            import json
            full_report = {
                "cleaning_results": result1,
                "duplicate_results": result2,
                "final_report": report
            }
            filename = f"tag_cleaning_report_{int(time.time())}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(full_report, f, indent=2, ensure_ascii=False)
            print(f"完整报告已保存到 {filename}")

    else:
        print("无效选择")

if __name__ == "__main__":
    main()