#!/usr/bin/env python
"""
测试PubChem分类API响应格式
"""
import requests
import json
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_classification_api(cid=72):
    """测试PubChem分类API"""
    print(f"测试PubChem分类API，CID: {cid}")

    # 分类API
    classification_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/classification/JSON"

    try:
        print(f"请求URL: {classification_url}")
        response = requests.get(classification_url, verify=False, timeout=30)

        if response.status_code == 200:
            data = response.json()
            print("\n=== 分类API响应 ===")
            print(f"响应类型: {type(data)}")
            print(f"响应键: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")

            # 格式化打印JSON
            print("\n完整响应:")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:2000] + "..." if len(json.dumps(data)) > 2000 else json.dumps(data, indent=2, ensure_ascii=False))

            # 尝试解析分类结构
            if isinstance(data, dict):
                print("\n=== 尝试解析分类结构 ===")
                parse_classification_structure(data)
        else:
            print(f"API请求失败: {response.status_code}")
            print(f"响应内容: {response.text[:500]}")

    except Exception as e:
        print(f"请求异常: {e}")
        import traceback
        traceback.print_exc()

def parse_classification_structure(data, indent=0):
    """递归解析分类数据结构"""
    prefix = "  " * indent

    if isinstance(data, dict):
        for key, value in data.items():
            print(f"{prefix}{key}: ", end="")
            if isinstance(value, (dict, list)):
                print(f"{type(value).__name__} ({len(value) if isinstance(value, list) else 'dict'})")
                if isinstance(value, dict) and indent < 3:  # 限制递归深度
                    parse_classification_structure(value, indent + 1)
                elif isinstance(value, list) and value and indent < 3:
                    if len(value) > 0:
                        print(f"{prefix}  第一个元素:")
                        parse_classification_structure(value[0], indent + 2)
            else:
                print(f"{value}")
    elif isinstance(data, list):
        print(f"{prefix}列表长度: {len(data)}")
        if len(data) > 0 and indent < 3:
            print(f"{prefix}第一个元素:")
            parse_classification_structure(data[0], indent + 1)

def test_compound_api(cid=72):
    """测试化合物基本信息API"""
    print(f"\n\n测试化合物基本信息API，CID: {cid}")

    compound_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/JSON"

    try:
        response = requests.get(compound_url, verify=False, timeout=30)

        if response.status_code == 200:
            data = response.json()
            print("\n=== 化合物API响应 ===")

            # 检查PC_Compounds结构
            if 'PC_Compounds' in data:
                print("找到PC_Compounds结构")
                pc_compound = data['PC_Compounds'][0]
                print(f"PC_Compounds键: {list(pc_compound.keys())}")

                # 检查props
                if 'props' in pc_compound:
                    print(f"props数量: {len(pc_compound['props'])}")
                    # 先打印所有label
                    print("\n所有props标签:")
                    for i, prop in enumerate(pc_compound['props']):
                        urn = prop.get('urn', {})
                        label = urn.get('label', 'Unknown')
                        name = urn.get('name', '')
                        print(f"  {i+1:2d}. {label} (name: {name})")

                    # 检查是否有用途相关的标签
                    print("\n用途相关标签:")
                    use_keywords = ['use', 'application', 'manufacturing', 'preparation', 'safety', 'hazard', 'toxicity', 'purpose']
                    for i, prop in enumerate(pc_compound['props']):
                        urn = prop.get('urn', {})
                        label = urn.get('label', 'Unknown')
                        label_lower = label.lower()
                        if any(keyword in label_lower for keyword in use_keywords):
                            name = urn.get('name', '')
                            value = prop.get('value', {})
                            print(f"  {i+1:2d}. {label} (name: {name}): {value}")

        else:
            print(f"化合物API请求失败: {response.status_code}")

    except Exception as e:
        print(f"化合物API请求异常: {e}")

if __name__ == "__main__":
    print("开始测试PubChem API...")
    # 测试水的CID=962
    cid = 962
    print(f"\n{'='*60}")
    print(f"测试CID: {cid} (水)")
    test_classification_api(cid)
    test_compound_api(cid)