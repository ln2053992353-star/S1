#!/usr/bin/env python
"""
测试PubChem用途信息提取功能
"""
import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.management.commands.sync_pubchem import Command

def test_extract_use_info():
    """测试用途信息提取"""
    cmd = Command()

    # 模拟PubChem API响应数据
    mock_compound_data = {
        'PC_Compounds': [{
            'props': [
                {
                    'urn': {
                        'label': 'Use',
                        'name': 'Use Classification'
                    },
                    'value': {
                        'sval': 'Solvent; Cleaning agent; Heat transfer medium'
                    }
                },
                {
                    'urn': {
                        'label': 'Application',
                        'name': 'Primary Applications'
                    },
                    'value': {
                        'sval': 'Industrial processes; Laboratory reagent; Pharmaceutical manufacturing'
                    }
                },
                {
                    'urn': {
                        'label': 'IUPAC Name',
                        'name': 'Preferred'
                    },
                    'value': {
                        'sval': 'Water'
                    }
                },
                {
                    'urn': {
                        'label': 'Safety/Hazards/Toxicity Information',
                        'name': 'Hazards'
                    },
                    'value': {
                        'sval': 'Non-toxic; May cause drowning if inhaled in large quantities'
                    }
                }
            ]
        }]
    }

    mock_desc_data = {
        'InformationList': {
            'Information': [{
                'Description': 'Water is a transparent, tasteless, odorless, and nearly colorless chemical substance. It is used for drinking, cleaning, agriculture, industrial processes, and many other purposes. It is also employed as a solvent in chemical reactions.'
            }]
        }
    }

    print("测试用途信息提取...")
    use_tags = cmd.extract_use_and_manufacturing_info(mock_compound_data, mock_desc_data)

    print(f"提取到 {len(use_tags)} 个用途标签:")
    for i, tag in enumerate(use_tags, 1):
        print(f"  {i}. {tag['name']} (类别: {tag['category']}, 类型: {tag['type']}, 置信度: {tag['confidence']})")

    # 验证提取结果
    expected_tags = ['Solvent', 'Cleaning agent', 'Heat transfer medium',
                     'Industrial processes', 'Laboratory reagent', 'Pharmaceutical manufacturing',
                     'Non-toxic', 'May cause drowning if inhaled in large quantities',
                     'drinking', 'cleaning', 'agriculture', 'industrial processes', 'many other purposes',
                     'solvent in chemical reactions']

    extracted_names = [tag['name'].lower() for tag in use_tags]

    print("\n验证提取结果:")
    for expected in expected_tags:
        expected_lower = expected.lower()
        if any(expected_lower in extracted or extracted in expected_lower for extracted in extracted_names):
            print(f"  [OK] 找到: {expected}")
        else:
            print(f"  [FAIL] 缺失: {expected}")

    return len(use_tags) > 0

def test_parse_classification_response():
    """测试分类响应解析"""
    cmd = Command()

    # 模拟分类响应数据
    mock_classification_data = {
        'Hierarchies': {
            'Hierarchy': [{
                'Node': [{
                    'Information': {
                        'Name': 'Organic compounds',
                        'Type': 'Superclass',
                        'Kind': 'Chemical Classification'
                    }
                }]
            }]
        },
        'InformationList': {
            'Information': [{
                'MeSHTerms': [
                    {'Name': 'Solvents', 'ID': 'D013108'},
                    {'Name': 'Water', 'ID': 'D014867'}
                ]
            }]
        }
    }

    print("\n测试分类响应解析...")
    classifications, mesh_terms = cmd.parse_classification_response(mock_classification_data)

    print(f"提取到 {len(classifications)} 个分类:")
    for cls in classifications:
        print(f"  - {cls['name']} (类别: {cls['category']}, 类型: {cls['type']})")

    print(f"\n提取到 {len(mesh_terms)} 个MeSH术语:")
    for mesh in mesh_terms:
        print(f"  - {mesh['name']} (ID: {mesh['id']}, 类别: {mesh['category']})")

    return len(classifications) > 0 or len(mesh_terms) > 0

def test_integration():
    """测试集成解析"""
    cmd = Command()

    mock_cid = 962
    mock_compound_data = {
        'PC_Compounds': [{
            'props': [
                {
                    'urn': {'label': 'IUPAC Name', 'name': 'Preferred'},
                    'value': {'sval': 'Water'}
                },
                {
                    'urn': {'label': 'Use', 'name': 'Use Classification'},
                    'value': {'sval': 'Solvent; Industrial applications'}
                }
            ]
        }]
    }

    mock_desc_data = {
        'InformationList': {
            'Information': [{
                'Description': 'Water is used as a solvent and for industrial processes.'
            }]
        }
    }

    mock_classification_data = {
        'Hierarchies': {
            'Hierarchy': [{
                'Node': [{
                    'Information': {
                        'Name': 'Inorganic compounds',
                        'Type': 'Class'
                    }
                }]
            }]
        }
    }

    print("\n测试集成解析...")
    result = cmd.parse_compound_data(
        mock_cid,
        mock_compound_data,
        mock_desc_data,
        mock_classification_data
    )

    print(f"CID: {result['cid']}")
    print(f"IUPAC名称: {result['iupac_name']}")
    print(f"描述: {result.get('description', 'N/A')[:100]}...")
    print(f"分类数量: {len(result['classifications'])}")
    print(f"MeSH术语数量: {len(result['mesh_terms'])}")
    print(f"用途标签数量: {len(result['use_and_manufacturing_tags'])}")

    if result['use_and_manufacturing_tags']:
        print("用途标签:")
        for tag in result['use_and_manufacturing_tags']:
            print(f"  - {tag['name']}")

    return result['use_and_manufacturing_tags'] is not None

def main():
    """主函数"""
    print("PubChem用途信息提取功能测试")
    print("=" * 60)

    tests = [
        ("用途信息提取", test_extract_use_info),
        ("分类响应解析", test_parse_classification_response),
        ("集成解析", test_integration)
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*40}")
        print(f"测试: {test_name}")
        print('='*40)
        try:
            success = test_func()
            results.append((test_name, success))
            status = "通过" if success else "失败"
            print(f"结果: {status}")
        except Exception as e:
            print(f"测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    print(f"\n{'='*60}")
    print("测试总结:")
    for test_name, success in results:
        status = "[OK] 通过" if success else "[FAIL] 失败"
        print(f"  {test_name}: {status}")

    all_passed = all(success for _, success in results)
    if all_passed:
        print("\n所有测试通过!")
    else:
        print("\n部分测试失败，请检查代码。")

    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)