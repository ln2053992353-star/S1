#!/usr/bin/env python
"""
AI增强的PubChem标签分析器

功能：
1. 对PubChem获取的原始标签进行AI语义分析
2. 识别标签之间的层次关系（父子、兄弟关系）
3. 去重和合并相似的PubChem标签
4. 为标签分配优化后的分类信息
"""
import os
import sys
import django
import time
import json
import requests
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import PubChemTag, ProductPubChemTag, Product

# ==============================================================================
# 配置区域 (火山引擎)
# ==============================================================================
LLM_API_KEY = "156c8a37-20bf-4060-8bdc-d9991fc03eef"
LLM_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
LLM_MODEL_NAME = "ep-20251211173243-qklb7"
LLM_API_URL = f"{LLM_API_BASE}/chat/completions"

class PubChemTagAnalyzer:
    """PubChem标签AI分析器"""

    def __init__(self, batch_size: int = 50, delay: float = 0.5):
        """
        初始化分析器

        Args:
            batch_size: 每批处理的标签数量
            delay: API调用之间的延迟(秒)
        """
        self.batch_size = batch_size
        self.delay = delay
        self.headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json"
        }

    def call_ai_api(self, prompt: str, temperature: float = 0.1) -> Optional[str]:
        """
        调用火山引擎AI API

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

        try:
            resp = requests.post(LLM_API_URL, headers=self.headers, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.json()['choices'][0]['message']['content'].strip()
            else:
                print(f"API调用失败: {resp.status_code} - {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"API调用异常: {e}")
            return None

    def analyze_tag_semantics(self, tag_name: str, tag_category: str = None) -> Dict[str, Any]:
        """
        分析单个标签的语义

        Args:
            tag_name: 标签名称
            tag_category: 标签原始类别（可选）

        Returns:
            语义分析结果
        """
        prompt = f"""
        请分析以下生物化学标签的语义信息：

        标签: "{tag_name}"
        {f"原始类别: {tag_category}" if tag_category else ""}

        请提供以下信息：
        1. 核心含义：用一句话解释这个标签的含义
        2. 语义类型：选择最合适的分类（化学结构、生物功能、有机化合物类别、MeSH术语、生物通路、疾病关联、其他）
        3. 父级标签：列出可能的上位概念标签（例如："Benzenoids" 的父级可能是 "Organic compounds"）
        4. 同级标签：列出相关的兄弟概念标签
        5. 置信度：对分析结果的信心程度（0.0-1.0）

        请以JSON格式返回，结构如下：
        {{
            "core_meaning": "解释文本",
            "semantic_type": "类型名称",
            "parent_tags": ["标签1", "标签2", ...],
            "sibling_tags": ["标签1", "标签2", ...],
            "confidence": 0.95
        }}

        只返回JSON，不要其他文本。
        """

        result = self.call_ai_api(prompt)
        if not result:
            # 返回默认结构
            return {
                "core_meaning": f"Chemical or biological concept: {tag_name}",
                "semantic_type": "chemical" if not tag_category else tag_category.lower(),
                "parent_tags": [],
                "sibling_tags": [],
                "confidence": 0.5
            }

        try:
            # 提取JSON（AI可能返回包含JSON的文本）
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # 尝试直接解析
                return json.loads(result)
        except json.JSONDecodeError:
            print(f"无法解析AI响应为JSON: {result[:200]}")
            return {
                "core_meaning": f"Chemical or biological concept: {tag_name}",
                "semantic_type": "chemical" if not tag_category else tag_category.lower(),
                "parent_tags": [],
                "sibling_tags": [],
                "confidence": 0.5
            }

    def find_similar_tags(self, tag_name: str, all_tags: List[str]) -> List[str]:
        """
        查找相似的标签

        Args:
            tag_name: 目标标签
            all_tags: 所有标签列表

        Returns:
            相似标签列表
        """
        if len(all_tags) <= 1:
            return []

        prompt = f"""
        请从以下标签列表中找出与"{tag_name}"最相似的标签：

        标签列表: {', '.join(all_tags[:50])}  # 限制数量避免过长

        相似性判断标准：
        1. 语义相似（例如："Cancer" 和 "Tumor"）
        2. 层级关系（例如："Organic compounds" 和 "Benzenoids"）
        3. 同义词或变体（例如："anti-tumor" 和 "antitumor"）

        请返回最相似的前5个标签（不包括自身），以JSON数组格式：
        ["标签1", "标签2", "标签3", ...]

        只返回JSON数组，不要其他文本。
        """

        result = self.call_ai_api(prompt)
        if not result:
            return []

        try:
            import re
            json_match = re.search(r'\[.*\]', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return json.loads(result)
        except:
            return []

    def optimize_tag_category(self, tag_name: str, current_category: str = None) -> Dict[str, Any]:
        """
        优化标签分类信息

        Args:
            tag_name: 标签名称
            current_category: 当前分类（可选）

        Returns:
            优化后的分类信息
        """
        prompt = f"""
        请为以下生物化学标签分配最合适的分类信息：

        标签: "{tag_name}"
        {f"当前分类: {current_category}" if current_category else "无当前分类"}

        请考虑以下分类体系：
        1. chemical_class - 化学类别（如：Organic compounds, Benzenoids, Lipids）
        2. biological_function - 生物功能（如：Antioxidant, Enzyme inhibitor, Receptor agonist）
        3. mesh_term - MeSH医学术语（如：Phenols, Neoplasms, Inflammation）
        4. pathway - 生物通路（如：Metabolic pathway, Signaling pathway）
        5. disease_related - 疾病相关（如：Cancer, Diabetes, Alzheimer's）
        6. structural_feature - 结构特征（如：Carboxylic acid, Amine, Heterocyclic compound）

        请以JSON格式返回，结构如下：
        {{
            "optimized_category": "最合适的分类名称",
            "category_type": "分类类型（chemical_class等）",
            "hierarchy_level": "层级（1-5，1最高级）",
            "confidence": 0.95,
            "alternative_categories": ["备选分类1", "备选分类2"]
        }}

        只返回JSON，不要其他文本。
        """

        result = self.call_ai_api(prompt)
        if not result:
            return {
                "optimized_category": current_category or "chemical_class",
                "category_type": "chemical_class",
                "hierarchy_level": 3,
                "confidence": 0.5,
                "alternative_categories": []
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
                "optimized_category": current_category or "chemical_class",
                "category_type": "chemical_class",
                "hierarchy_level": 3,
                "confidence": 0.5,
                "alternative_categories": []
            }

    def analyze_tag_batch(self, tags: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量分析标签（更高效）

        Args:
            tags: 标签列表，每个元素为{"tag_name": "...", "tag_category": "..."}

        Returns:
            批量分析结果
        """
        tag_names = [tag["tag_name"] for tag in tags]
        tag_list_str = "\n".join([f"- {tag['tag_name']} ({tag.get('tag_category', '未分类')})" for tag in tags])

        prompt = f"""
        请批量分析以下生物化学标签：

        {tag_list_str}

        请为每个标签提供：
        1. 语义类型（chemical_class, biological_function, mesh_term, pathway, disease_related, structural_feature）
        2. 推荐的层级（1-5，1最高级）
        3. 可能的父级标签（从列表中选或建议新的）

        请以JSON格式返回，结构如下：
        {{
            "analyzed_tags": [
                {{
                    "tag_name": "标签名",
                    "semantic_type": "类型",
                    "hierarchy_level": 层级,
                    "suggested_parents": ["父级1", "父级2"],
                    "confidence": 0.95
                }},
                ...
            ]
        }}

        只返回JSON，不要其他文本。
        """

        result = self.call_ai_api(prompt, temperature=0.2)
        if not result:
            # 降级为逐个分析
            print("批量分析失败，降级为逐个分析...")
            analyzed_tags = []
            for tag in tags:
                analysis = self.analyze_tag_semantics(tag["tag_name"], tag.get("tag_category"))
                analyzed_tags.append({
                    "tag_name": tag["tag_name"],
                    "semantic_type": analysis.get("semantic_type", "chemical_class"),
                    "hierarchy_level": 3,
                    "suggested_parents": analysis.get("parent_tags", []),
                    "confidence": analysis.get("confidence", 0.5)
                })
                time.sleep(self.delay)

            return {"analyzed_tags": analyzed_tags}

        try:
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return json.loads(result)
        except:
            # 降级为逐个分析
            analyzed_tags = []
            for tag in tags:
                analysis = self.analyze_tag_semantics(tag["tag_name"], tag.get("tag_category"))
                analyzed_tags.append({
                    "tag_name": tag["tag_name"],
                    "semantic_type": analysis.get("semantic_type", "chemical_class"),
                    "hierarchy_level": 3,
                    "suggested_parents": analysis.get("parent_tags", []),
                    "confidence": analysis.get("confidence", 0.5)
                })
                time.sleep(self.delay)

            return {"analyzed_tags": analyzed_tags}

    def detect_duplicate_tags(self, tags: List[Dict[str, Any]]) -> List[List[str]]:
        """
        检测重复或相似的标签

        Args:
            tags: 标签列表

        Returns:
            相似标签分组列表
        """
        if len(tags) < 2:
            return []

        tag_names = [tag["tag_name"] for tag in tags]
        tag_names_str = ', '.join(tag_names[:30])  # 限制数量

        prompt = f"""
        请分析以下标签列表，识别重复或高度相似的标签：

        标签: {tag_names_str}

        请将相似的标签分组，每组包含2个或更多标签。
        相似性标准：
        1. 同义词（如："Cancer" 和 "Tumor"）
        2. 拼写变体（如："anti-tumor" 和 "antitumor"）
        3. 缩写和全称（如："DNA" 和 "Deoxyribonucleic acid"）
        4. 包含关系（如："Organic compounds" 包含 "Benzenoids"）

        请以JSON格式返回，结构如下：
        {{
            "duplicate_groups": [
                ["标签1", "标签2"],
                ["标签3", "标签4", "标签5"],
                ...
            ]
        }}

        只返回JSON，不要其他文本。
        """

        result = self.call_ai_api(prompt)
        if not result:
            return []

        try:
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("duplicate_groups", [])
            else:
                data = json.loads(result)
                return data.get("duplicate_groups", [])
        except:
            return []

    def build_tag_hierarchy(self, tags: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        构建标签层次结构

        Args:
            tags: 标签列表

        Returns:
            层次结构
        """
        tag_names = [tag["tag_name"] for tag in tags]
        tag_names_str = '\n'.join([f"- {name}" for name in tag_names[:50]])  # 限制数量

        prompt = f"""
        请为以下生物化学标签构建层次结构：

        {tag_names_str}

        考虑以下原则：
        1. 广义标签在上，狭义标签在下
        2. 化学结构分类：Organic compounds → Benzenoids → Phenols
        3. 生物功能分类：Biological processes → Metabolic processes → Glycolysis
        4. 疾病分类：Diseases → Neoplasms → Carcinoma

        请以JSON格式返回层次结构，结构如下：
        {{
            "hierarchy": [
                {{
                    "tag_name": "顶级标签",
                    "level": 1,
                    "children": [
                        {{
                            "tag_name": "二级标签",
                            "level": 2,
                            "children": [...]
                        }},
                        ...
                    ]
                }},
                ...
            ],
            "orphan_tags": ["没有父级的标签1", "标签2", ...]
        }}

        只返回JSON，不要其他文本。
        """

        result = self.call_ai_api(prompt)
        if not result:
            return {"hierarchy": [], "orphan_tags": tag_names}

        try:
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return json.loads(result)
        except:
            return {"hierarchy": [], "orphan_tags": tag_names}

class PubChemTagOptimizer:
    """PubChem标签优化器（应用分析结果到数据库）"""

    def __init__(self):
        self.analyzer = PubChemTagAnalyzer()

    def get_all_pubchem_tags(self) -> List[Dict[str, Any]]:
        """获取所有PubChem标签"""
        tags = PubChemTag.objects.all().values('tag_id', 'tag_name', 'tag_category')
        return list(tags)

    def optimize_single_tag(self, tag: PubChemTag) -> bool:
        """
        优化单个标签

        Args:
            tag: PubChemTag实例

        Returns:
            是否成功优化
        """
        print(f"优化标签: {tag.tag_name}")

        # 分析语义
        semantic_analysis = self.analyzer.analyze_tag_semantics(tag.tag_name, tag.tag_category)

        # 优化分类
        category_optimization = self.analyzer.optimize_tag_category(tag.tag_name, tag.tag_category)

        # 更新标签
        try:
            # 保存语义分析结果到额外字段（如果有）
            if hasattr(tag, 'semantic_data'):
                tag.semantic_data = json.dumps(semantic_analysis)

            # 更新分类信息
            optimized_category = category_optimization.get('optimized_category')
            category_type = category_optimization.get('category_type')

            if optimized_category and optimized_category != tag.tag_category:
                print(f"  更新分类: {tag.tag_category} -> {optimized_category}")
                tag.tag_category = optimized_category

            # 保存层级信息
            if hasattr(tag, 'hierarchy_level'):
                tag.hierarchy_level = category_optimization.get('hierarchy_level', 3)

            tag.save()

            print(f"  完成优化 (置信度: {category_optimization.get('confidence', 0.5):.2f})")
            return True

        except Exception as e:
            print(f"  优化失败: {e}")
            return False

    def batch_optimize_tags(self, limit: int = None, batch_size: int = 20) -> Dict[str, Any]:
        """
        批量优化标签

        Args:
            limit: 限制处理数量
            batch_size: 每批大小

        Returns:
            优化结果统计
        """
        tags = PubChemTag.objects.all()
        total = tags.count()

        if limit:
            tags = tags[:limit]
            total = min(total, limit)

        print(f"开始批量优化 {total} 个PubChem标签...")

        success_count = 0
        fail_count = 0

        for i in range(0, total, batch_size):
            batch = tags[i:i + batch_size]
            batch_tags_list = [
                {"tag_name": tag.tag_name, "tag_category": tag.tag_category}
                for tag in batch
            ]

            print(f"\n处理批次 {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}")

            # 批量分析
            batch_result = self.analyzer.analyze_tag_batch(batch_tags_list)

            # 应用分析结果
            for j, tag in enumerate(batch):
                if j < len(batch_result.get('analyzed_tags', [])):
                    analysis = batch_result['analyzed_tags'][j]

                    try:
                        # 更新标签
                        if analysis['tag_name'] == tag.tag_name:
                            # 更新分类信息
                            semantic_type = analysis.get('semantic_type')
                            if semantic_type and semantic_type != tag.tag_category:
                                tag.tag_category = semantic_type

                            # 保存额外信息
                            if hasattr(tag, 'hierarchy_level'):
                                tag.hierarchy_level = analysis.get('hierarchy_level', 3)

                            tag.save()
                            success_count += 1
                        else:
                            print(f"  警告: 标签名称不匹配 {tag.tag_name} != {analysis['tag_name']}")
                            fail_count += 1
                    except Exception as e:
                        print(f"  更新失败 {tag.tag_name}: {e}")
                        fail_count += 1
                else:
                    print(f"  警告: 没有分析结果 for {tag.tag_name}")
                    fail_count += 1

            # 延迟
            if i + batch_size < total:
                time.sleep(self.analyzer.delay * batch_size)

        return {
            "total_processed": total,
            "success_count": success_count,
            "fail_count": fail_count,
            "success_rate": success_count / total if total > 0 else 0
        }

    def detect_and_merge_duplicates(self) -> Dict[str, Any]:
        """
        检测并合并重复标签

        Returns:
            合并结果统计
        """
        print("检测重复标签...")

        tags = self.get_all_pubchem_tags()
        if len(tags) < 2:
            return {"duplicate_groups": [], "merged_count": 0}

        # 检测重复组
        duplicate_groups = self.analyzer.detect_duplicate_tags(tags)

        print(f"找到 {len(duplicate_groups)} 个重复组")

        merged_count = 0

        for group in duplicate_groups:
            if len(group) < 2:
                continue

            print(f"\n处理重复组: {group}")

            # 找出所有匹配的标签
            matched_tags = PubChemTag.objects.filter(tag_name__in=group)

            if matched_tags.count() < 2:
                print(f"  数据库中只找到 {matched_tags.count()} 个标签，跳过")
                continue

            # 选择保留的标签（第一个）
            keep_tag = matched_tags.first()
            merge_tags = matched_tags.exclude(tag_id=keep_tag.tag_id)

            print(f"  保留: {keep_tag.tag_name}, 合并: {merge_tags.count()} 个标签")

            # 转移关联关系到保留的标签
            for merge_tag in merge_tags:
                # 获取所有产品关联
                product_relations = ProductPubChemTag.objects.filter(pubchem_tag=merge_tag)

                for relation in product_relations:
                    # 检查是否已有关联
                    existing = ProductPubChemTag.objects.filter(
                        product=relation.product,
                        pubchem_tag=keep_tag
                    ).exists()

                    if not existing:
                        # 创建新关联
                        ProductPubChemTag.objects.create(
                            product=relation.product,
                            pubchem_tag=keep_tag
                        )

                # 删除旧标签
                merge_tag.delete()
                merged_count += 1

            print(f"  合并完成")

        return {
            "duplicate_groups": duplicate_groups,
            "merged_count": merged_count
        }

    def build_full_hierarchy(self) -> Dict[str, Any]:
        """
        构建完整的标签层次结构

        Returns:
            层次结构结果
        """
        print("构建标签层次结构...")

        tags = self.get_all_pubchem_tags()

        if not tags:
            print("没有标签可构建层次结构")
            return {"hierarchy": [], "orphan_tags": []}

        # 构建层次
        hierarchy_result = self.analyzer.build_tag_hierarchy(tags)

        print(f"构建完成: {len(hierarchy_result.get('hierarchy', []))} 个层次树")
        print(f"孤立标签: {len(hierarchy_result.get('orphan_tags', []))} 个")

        # TODO: 将层次结构保存到数据库（需要扩展模型）

        return hierarchy_result

def main():
    """主函数"""
    print("PubChem标签AI分析器")
    print("=" * 50)

    # 检查当前状态
    total_tags = PubChemTag.objects.count()
    total_products = Product.objects.count()
    products_with_tags = Product.objects.filter(pubchem_tags__isnull=False).distinct().count()

    print(f"PubChem标签总数: {total_tags}")
    print(f"产品总数: {total_products}")
    print(f"有PubChem标签的产品数: {products_with_tags}")

    optimizer = PubChemTagOptimizer()

    print("\n选项:")
    print("1. 批量优化所有PubChem标签")
    print("2. 检测并合并重复标签")
    print("3. 构建标签层次结构")
    print("4. 完整优化流程（1→2→3）")
    print("5. 测试AI分析功能（不修改数据库）")

    choice = input("\n请选择 (1-5): ").strip()

    if choice == '1':
        # 批量优化
        limit_input = input("处理数量限制 (留空为全部): ").strip()
        limit = int(limit_input) if limit_input else None

        result = optimizer.batch_optimize_tags(limit=limit)

        print("\n优化完成:")
        print(f"处理总数: {result['total_processed']}")
        print(f"成功: {result['success_count']}")
        print(f"失败: {result['fail_count']}")
        print(f"成功率: {result['success_rate']:.2%}")

    elif choice == '2':
        # 检测合并重复
        result = optimizer.detect_and_merge_duplicates()

        print("\n重复检测完成:")
        print(f"重复组数: {len(result['duplicate_groups'])}")
        print(f"合并标签数: {result['merged_count']}")

    elif choice == '3':
        # 构建层次结构
        result = optimizer.build_full_hierarchy()

        print("\n层次结构构建完成")
        # 可以保存结果到文件
        save_file = input("是否保存结果到JSON文件? (y/n): ").lower() == 'y'
        if save_file:
            import json
            filename = f"tag_hierarchy_{int(time.time())}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"结果已保存到 {filename}")

    elif choice == '4':
        # 完整流程
        print("开始完整优化流程...")

        print("\n=== 步骤1: 批量优化标签 ===")
        result1 = optimizer.batch_optimize_tags()

        print("\n=== 步骤2: 检测合并重复 ===")
        result2 = optimizer.detect_and_merge_duplicates()

        print("\n=== 步骤3: 构建层次结构 ===")
        result3 = optimizer.build_full_hierarchy()

        print("\n完整优化完成!")
        print(f"优化标签: {result1['success_count']}/{result1['total_processed']}")
        print(f"合并重复: {result2['merged_count']} 个标签")
        print(f"层次树: {len(result3.get('hierarchy', []))} 个")

    elif choice == '5':
        # 测试分析功能
        print("测试AI分析功能...")

        test_tags = [
            {"tag_name": "Organic compounds", "tag_category": "superclass"},
            {"tag_name": "Benzenoids", "tag_category": "class"},
            {"tag_name": "Phenols", "tag_category": "mesh"},
            {"tag_name": "Antioxidants", "tag_category": "mesh"}
        ]

        analyzer = PubChemTagAnalyzer()

        print("\n测试批量分析:")
        batch_result = analyzer.analyze_tag_batch(test_tags)
        print(f"分析结果: {json.dumps(batch_result, indent=2, ensure_ascii=False)}")

        print("\n测试重复检测:")
        dup_result = analyzer.detect_duplicate_tags(test_tags)
        print(f"重复组: {dup_result}")

        print("\n测试层次构建:")
        hierarchy_result = analyzer.build_tag_hierarchy(test_tags)
        print(f"层次结构: {json.dumps(hierarchy_result, indent=2, ensure_ascii=False)}")

    else:
        print("无效选择")

if __name__ == "__main__":
    main()