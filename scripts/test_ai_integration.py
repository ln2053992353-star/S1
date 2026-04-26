#!/usr/bin/env python
"""
测试AI服务集成和提示工程

功能：
1. 测试火山引擎API连接
2. 测试各种提示词设计
3. 验证标签分析效果
4. 性能基准测试
"""
import os
import sys
import django
import time
import json
import requests
from typing import List, Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import Tag, PubChemTag

# ==============================================================================
# 配置区域 (火山引擎)
# ==============================================================================
LLM_API_KEY = "156c8a37-20bf-4060-8bdc-d9991fc03eef"
LLM_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
LLM_MODEL_NAME = "ep-20251211173243-qklb7"
LLM_API_URL = f"{LLM_API_BASE}/chat/completions"

def test_api_connection() -> bool:
    """测试API连接"""
    print("测试火山引擎API连接...")

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": LLM_MODEL_NAME,
        "messages": [{"role": "user", "content": "你好，请回复'API连接正常'。"}],
        "temperature": 0.1,
        "max_tokens": 50
    }

    try:
        start_time = time.time()
        resp = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=30)
        elapsed = time.time() - start_time

        if resp.status_code == 200:
            response_text = resp.json()['choices'][0]['message']['content'].strip()
            print(f"✅ API连接正常")
            print(f"   响应时间: {elapsed:.2f}秒")
            print(f"   响应内容: {response_text}")
            return True
        else:
            print(f"❌ API连接失败: {resp.status_code}")
            print(f"   错误信息: {resp.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ API连接异常: {e}")
        return False

def test_prompt_effectiveness(prompt_type: str, test_input: str) -> Dict[str, Any]:
    """测试提示词效果"""
    print(f"\n测试提示词类型: {prompt_type}")
    print(f"测试输入: {test_input}")

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    # 根据不同提示类型设计提示词
    prompts = {
        "标签语义分析": f"""
        请分析以下生物化学标签的语义信息：

        标签: "{test_input}"

        请以JSON格式返回以下信息：
        1. core_meaning: 核心含义（1-2句话）
        2. domain: 主要领域（分子生物学、细胞生物学、生物化学、遗传学、药理学、其他）
        3. semantic_type: 语义类型（化学结构、生物功能、实验方法、疾病相关、其他）
        4. parent_tags: 可能的父级标签列表
        5. confidence: 置信度（0.0-1.0）

        只返回JSON，不要其他文本。
        """,

        "标签分类": f"""
        请为以下标签分配最合适的分类：

        标签: "{test_input}"

        请考虑以下分类体系：
        - 实验技术：分子生物学技术、细胞生物学技术、分析检测技术
        - 化合物类别：有机化合物、无机化合物、生物大分子
        - 生物过程：代谢过程、细胞过程、遗传过程
        - 疾病相关：癌症相关、神经疾病、代谢疾病
        - 应用领域：药物研发、农业生物、环境科学

        请以JSON格式返回：
        {{
            "recommended_category": "推荐分类",
            "category_type": "分类类型",
            "confidence": 0.95,
            "reason": "分类理由"
        }}

        只返回JSON，不要其他文本。
        """,

        "标签关系分析": f"""
        请分析以下标签之间的关系：

        标签1: "PCR"
        标签2: "{test_input}"

        请判断关系类型：
        1. 父子关系（一个包含另一个）
        2. 兄弟关系（同一父级下的同级概念）
        3. 同义词关系
        4. 相关关系
        5. 无关系

        请以JSON格式返回：
        {{
            "relationship_type": "关系类型",
            "description": "关系描述",
            "confidence": 0.95
        }}

        只返回JSON，不要其他文本。
        """,

        "标签去重判断": f"""
        请判断以下两个标签是否表示相同或高度相似的概念：

        标签A: "Gene expression"
        标签B: "{test_input}"

        请以JSON格式返回：
        {{
            "is_similar": true/false,
            "similarity_score": 0.0-1.0,
            "reason": "判断理由"
        }}

        只返回JSON，不要其他文本。
        """
    }

    prompt = prompts.get(prompt_type, prompts["标签语义分析"])

    payload = {
        "model": LLM_MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1
    }

    try:
        start_time = time.time()
        resp = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=30)
        elapsed = time.time() - start_time

        if resp.status_code == 200:
            response_text = resp.json()['choices'][0]['message']['content'].strip()

            print(f"   响应时间: {elapsed:.2f}秒")
            print(f"   原始响应: {response_text[:200]}...")

            # 尝试解析JSON
            try:
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    print(f"   ✅ 成功解析JSON")
                    return {
                        "success": True,
                        "response_time": elapsed,
                        "parsed_response": parsed,
                        "raw_response": response_text
                    }
                else:
                    print(f"   ⚠️ 响应包含JSON但无法解析")
                    return {
                        "success": False,
                        "response_time": elapsed,
                        "parsed_response": None,
                        "raw_response": response_text,
                        "error": "JSON解析失败"
                    }
            except json.JSONDecodeError:
                print(f"   ❌ 响应不是有效的JSON")
                return {
                    "success": False,
                    "response_time": elapsed,
                    "parsed_response": None,
                    "raw_response": response_text,
                    "error": "JSON解码错误"
                }
        else:
            print(f"   ❌ API请求失败: {resp.status_code}")
            return {
                "success": False,
                "response_time": 0,
                "parsed_response": None,
                "raw_response": "",
                "error": f"HTTP {resp.status_code}"
            }

    except Exception as e:
        print(f"   ❌ 请求异常: {e}")
        return {
            "success": False,
            "response_time": 0,
            "parsed_response": None,
            "raw_response": "",
            "error": str(e)
        }

def test_batch_processing() -> Dict[str, Any]:
    """测试批量处理性能"""
    print("\n测试批量处理性能...")

    # 创建测试标签
    test_tags = [
        "PCR", "DNA sequencing", "Cell culture",
        "Protein expression", "HPLC analysis", "Mass spectrometry",
        "Gene editing", "Western blot", "Flow cytometry"
    ]

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
    请批量分析以下生物技术标签：

    {', '.join(test_tags)}

    对于每个标签，请提供：
    1. 领域分类（分子生物学、细胞生物学、生物化学、分析技术、其他）
    2. 推荐的标准分类（实验技术、化合物类别、生物过程、应用领域）

    请以JSON格式返回，结构如下：
    {{
        "analyzed_tags": [
            {{
                "tag_name": "标签名",
                "domain": "领域",
                "recommended_category": "推荐分类"
            }},
            ...
        ]
    }}

    只返回JSON，不要其他文本。
    """

    payload = {
        "model": LLM_MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1
    }

    try:
        start_time = time.time()
        resp = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=60)
        elapsed = time.time() - start_time

        if resp.status_code == 200:
            response_text = resp.json()['choices'][0]['message']['content'].strip()

            print(f"   批量处理 {len(test_tags)} 个标签")
            print(f"   总耗时: {elapsed:.2f}秒")
            print(f"   平均每个标签: {elapsed/len(test_tags):.2f}秒")

            # 尝试解析
            try:
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    analyzed_count = len(parsed.get('analyzed_tags', []))
                    print(f"   ✅ 成功分析 {analyzed_count}/{len(test_tags)} 个标签")

                    return {
                        "success": True,
                        "total_time": elapsed,
                        "tags_per_second": len(test_tags) / elapsed,
                        "analyzed_count": analyzed_count
                    }
            except:
                pass

        return {
            "success": False,
            "total_time": elapsed,
            "error": f"HTTP {resp.status_code}" if resp.status_code != 200 else "解析失败"
        }

    except Exception as e:
        print(f"   ❌ 批量处理异常: {e}")
        return {
            "success": False,
            "total_time": 0,
            "error": str(e)
        }

def test_real_tag_analysis() -> Dict[str, Any]:
    """测试实际标签分析"""
    print("\n测试实际数据库标签分析...")

    # 从数据库获取一些标签
    tags = Tag.objects.all()[:5]  # 只测试5个
    pubchem_tags = PubChemTag.objects.all()[:5]

    test_cases = []

    # 普通标签
    for tag in tags:
        test_cases.append({
            "type": "普通标签",
            "name": tag.tag_name,
            "category": tag.tag_category or "未分类"
        })

    # PubChem标签
    for tag in pubchem_tags:
        test_cases.append({
            "type": "PubChem标签",
            "name": tag.tag_name,
            "category": tag.tag_category or "未分类"
        })

    if not test_cases:
        test_cases = [
            {"type": "示例标签", "name": "Gene expression", "category": "未分类"},
            {"type": "示例标签", "name": "Antioxidant", "category": "未分类"},
            {"type": "示例标签", "name": "Cell apoptosis", "category": "未分类"}
        ]

    print(f"测试 {len(test_cases)} 个实际标签:")
    for i, case in enumerate(test_cases):
        print(f"  {i+1}. [{case['type']}] {case['name']} ({case['category']})")

    results = []

    for i, case in enumerate(test_cases):
        print(f"\n分析 [{case['type']}] {case['name']}...")

        result = test_prompt_effectiveness("标签语义分析", case["name"])

        results.append({
            "tag": case["name"],
            "type": case["type"],
            "success": result["success"],
            "response_time": result["response_time"],
            "has_parsed": result["parsed_response"] is not None
        })

        # 避免频繁调用
        if i < len(test_cases) - 1:
            time.sleep(1)

    # 统计结果
    success_count = sum(1 for r in results if r["success"])
    parsed_count = sum(1 for r in results if r["has_parsed"])
    avg_time = sum(r["response_time"] for r in results if r["success"]) / success_count if success_count > 0 else 0

    print(f"\n实际标签分析结果:")
    print(f"  总测试数: {len(results)}")
    print(f"  API成功数: {success_count}")
    print(f"  JSON解析成功数: {parsed_count}")
    print(f"  平均响应时间: {avg_time:.2f}秒")

    return {
        "total_tests": len(results),
        "api_success": success_count,
        "parse_success": parsed_count,
        "average_response_time": avg_time,
        "detailed_results": results
    }

def test_prompt_variations() -> List[Dict[str, Any]]:
    """测试不同提示词变体"""
    print("\n测试不同提示词变体...")

    test_tag = "PCR"

    prompt_variations = [
        {
            "name": "简洁版",
            "prompt": f"分析'{test_tag}'标签的类别。"
        },
        {
            "name": "标准版",
            "prompt": f"请分析生物技术标签'{test_tag}'的语义信息和分类。"
        },
        {
            "name": "详细版",
            "prompt": f"""
            作为生物信息学专家，请分析标签'{test_tag}'：
            1. 核心含义和用途
            2. 所属技术领域
            3. 相关实验方法
            4. 推荐分类标签
            """
        },
        {
            "name": "结构化版",
            "prompt": f"""
            标签: "{test_tag}"

            请提供结构化分析：
            - 含义:
            - 领域:
            - 分类:
            - 相关技术:
            """
        },
        {
            "name": "JSON版",
            "prompt": f"""
            请分析标签"{test_tag}"并以JSON格式返回：
            {{
                "meaning": "核心含义",
                "domain": "技术领域",
                "category": "推荐分类",
                "confidence": 0.95
            }}
            """
        }
    ]

    results = []

    for variation in prompt_variations:
        print(f"\n测试提示词变体: {variation['name']}")

        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": LLM_MODEL_NAME,
            "messages": [{"role": "user", "content": variation["prompt"]}],
            "temperature": 0.1
        }

        try:
            start_time = time.time()
            resp = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=30)
            elapsed = time.time() - start_time

            if resp.status_code == 200:
                response_text = resp.json()['choices'][0]['message']['content'].strip()

                # 评估响应质量
                quality_score = self_evaluate_response(response_text)

                results.append({
                    "variation": variation["name"],
                    "response_time": elapsed,
                    "response_length": len(response_text),
                    "quality_score": quality_score,
                    "response_preview": response_text[:100] + "..." if len(response_text) > 100 else response_text
                })

                print(f"   耗时: {elapsed:.2f}秒, 长度: {len(response_text)}字符, 质量分: {quality_score:.2f}")

            else:
                print(f"   失败: HTTP {resp.status_code}")
                results.append({
                    "variation": variation["name"],
                    "response_time": 0,
                    "response_length": 0,
                    "quality_score": 0,
                    "error": f"HTTP {resp.status_code}"
                })

            time.sleep(0.5)

        except Exception as e:
            print(f"   异常: {e}")
            results.append({
                "variation": variation["name"],
                "response_time": 0,
                "response_length": 0,
                "quality_score": 0,
                "error": str(e)
            })

    # 找出最佳变体
    valid_results = [r for r in results if "error" not in r]
    if valid_results:
        best = max(valid_results, key=lambda x: x["quality_score"])
        print(f"\n最佳提示词变体: {best['variation']} (质量分: {best['quality_score']:.2f})")

    return results

def self_evaluate_response(response: str) -> float:
    """自我评估响应质量"""
    # 简单启发式评估
    score = 0.5  # 基础分

    # 长度适中加分
    if 50 <= len(response) <= 500:
        score += 0.1

    # 包含关键词加分
    keywords = ["PCR", "聚合酶链", "扩增", "DNA", "基因", "技术", "方法", "实验"]
    for keyword in keywords:
        if keyword in response:
            score += 0.05

    # 结构化内容加分
    if any(marker in response for marker in ["含义", "用途", "领域", "分类", "步骤", "原理"]):
        score += 0.1

    # JSON格式加分
    if "{" in response and "}" in response:
        score += 0.2

    return min(score, 1.0)

def run_comprehensive_test() -> Dict[str, Any]:
    """运行全面测试"""
    print("=" * 60)
    print("AI服务集成与提示工程全面测试")
    print("=" * 60)

    test_results = {}

    # 1. API连接测试
    print("\n1. API连接测试")
    api_ok = test_api_connection()
    test_results["api_connection"] = api_ok

    if not api_ok:
        print("❌ API连接失败，停止后续测试")
        return test_results

    # 2. 提示词变体测试
    print("\n2. 提示词变体测试")
    prompt_results = test_prompt_variations()
    test_results["prompt_variations"] = prompt_results

    # 3. 单标签分析测试
    print("\n3. 单标签分析测试")

    test_inputs = ["PCR", "Antioxidant", "Cell culture", "Mass spectrometry"]

    single_tag_results = []
    for test_input in test_inputs:
        print(f"\n分析标签: {test_input}")

        result = test_prompt_effectiveness("标签语义分析", test_input)
        single_tag_results.append({
            "tag": test_input,
            "success": result["success"],
            "response_time": result["response_time"],
            "has_json": result["parsed_response"] is not None
        })

        time.sleep(0.5)

    test_results["single_tag_analysis"] = single_tag_results

    # 4. 批量处理测试
    print("\n4. 批量处理测试")
    batch_result = test_batch_processing()
    test_results["batch_processing"] = batch_result

    # 5. 实际标签测试
    print("\n5. 实际标签测试")
    real_tag_result = test_real_tag_analysis()
    test_results["real_tag_analysis"] = real_tag_result

    # 生成总结报告
    print("\n" + "=" * 60)
    print("测试总结报告")
    print("=" * 60)

    # API连接
    print(f"✅ API连接: {'成功' if test_results['api_connection'] else '失败'}")

    # 单标签分析
    single_stats = test_results["single_tag_analysis"]
    success_rate = sum(1 for r in single_stats if r["success"]) / len(single_stats) if single_stats else 0
    json_rate = sum(1 for r in single_stats if r["has_json"]) / len(single_stats) if single_stats else 0
    avg_time = sum(r["response_time"] for r in single_stats if r["success"]) / sum(1 for r in single_stats if r["success"]) if any(r["success"] for r in single_stats) else 0

    print(f"📊 单标签分析:")
    print(f"   成功率: {success_rate:.1%}")
    print(f"   JSON解析率: {json_rate:.1%}")
    print(f"   平均响应时间: {avg_time:.2f}秒")

    # 批量处理
    batch = test_results["batch_processing"]
    if batch["success"]:
        print(f"🚀 批量处理:")
        print(f"   总耗时: {batch['total_time']:.2f}秒")
        print(f"   吞吐量: {batch.get('tags_per_second', 0):.2f} 标签/秒")

    # 实际标签
    real = test_results["real_tag_analysis"]
    print(f"🎯 实际标签测试:")
    print(f"   测试数量: {real['total_tests']}")
    print(f"   API成功率: {real['api_success']}/{real['total_tests']}")
    print(f"   解析成功率: {real['parse_success']}/{real['total_tests']}")

    # 保存测试报告
    save_report = input("\n是否保存详细测试报告到JSON文件? (y/n): ").lower() == 'y'
    if save_report:
        import json
        filename = f"ai_integration_test_report_{int(time.time())}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(test_results, f, indent=2, ensure_ascii=False)
        print(f"✅ 测试报告已保存到 {filename}")

    return test_results

def quick_test():
    """快速测试"""
    print("快速测试AI服务集成...")

    # 测试API连接
    if not test_api_connection():
        print("❌ API连接测试失败")
        return False

    # 测试一个简单的标签分析
    print("\n快速标签分析测试...")
    result = test_prompt_effectiveness("标签语义分析", "PCR")

    if result["success"] and result["parsed_response"]:
        print("✅ AI服务集成测试通过")
        print(f"   示例分析结果: {json.dumps(result['parsed_response'], indent=2, ensure_ascii=False)[:200]}...")
        return True
    else:
        print("❌ AI服务集成测试失败")
        return False

def main():
    """主函数"""
    print("AI服务集成与提示工程测试工具")
    print("=" * 50)

    print("选项:")
    print("1. 快速测试 (API连接 + 简单分析)")
    print("2. 全面测试 (所有功能)")
    print("3. 只测试API连接")
    print("4. 测试提示词变体")
    print("5. 测试批量处理")

    choice = input("\n请选择 (1-5): ").strip()

    if choice == '1':
        success = quick_test()
        if success:
            print("\n✅ 快速测试通过，AI服务集成正常")
        else:
            print("\n❌ 快速测试失败，请检查配置")

    elif choice == '2':
        run_comprehensive_test()

    elif choice == '3':
        test_api_connection()

    elif choice == '4':
        test_prompt_variations()

    elif choice == '5':
        test_batch_processing()

    else:
        print("无效选择")

if __name__ == "__main__":
    main()