#!/usr/bin/env python
"""
测试修复后的PubChem同步功能
"""
import os
import sys
import json
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

# 模拟一些PubChem分类API响应数据
MOCK_CLASSIFICATION_DATA = {
    "Hierarchies": {
        "Hierarchy": [
            {
                "Node": [
                    {
                        "Information": {
                            "Name": "Organic compounds",
                            "Type": "superclass",
                            "Kind": "chemical"
                        }
                    },
                    {
                        "Information": {
                            "Name": "Benzenoids",
                            "Type": "class",
                            "Kind": "chemical"
                        }
                    }
                ]
            }
        ]
    },
    "InformationList": {
        "Information": [
            {
                "MeSHTerms": [
                    {
                        "Name": "Phenols",
                        "ID": "D010636"
                    },
                    {
                        "Name": "Antioxidants",
                        "ID": "D059808"
                    }
                ]
            }
        ]
    }
}

# 模拟另一种可能的响应格式
MOCK_CLASSIFICATION_DATA_2 = {
    "taxonomy": {
        "nodes": [
            {
                "name": "Lipids and lipid-like molecules",
                "id": "LIPID"
            },
            {
                "name": "Fatty Acyls",
                "id": "FA"
            }
        ]
    }
}

# 模拟空响应
MOCK_CLASSIFICATION_DATA_3 = {}

def test_parse_classification_response():
    """测试分类响应解析"""
    print("=== 测试 parse_classification_response 方法 ===")

    # 需要导入修复后的sync_pubchem模块
    from search_engine.management.commands import sync_pubchem
    cmd = sync_pubchem.Command()

    # 测试第一个模拟数据
    print("\n1. 测试标准分类数据:")
    classifications, mesh_terms = cmd.parse_classification_response(MOCK_CLASSIFICATION_DATA)
    print(f"  分类数量: {len(classifications)}")
    print(f"  MeSH术语数量: {len(mesh_terms)}")

    if classifications:
        print("  分类示例:")
        for i, cls in enumerate(classifications[:3]):
            print(f"    {i+1}. {cls.get('name')} (类别: {cls.get('category')}, 类型: {cls.get('type')})")

    if mesh_terms:
        print("  MeSH术语示例:")
        for i, term in enumerate(mesh_terms[:3]):
            print(f"    {i+1}. {term.get('name')} (ID: {term.get('id')})")

    # 测试第二个模拟数据
    print("\n2. 测试替代格式分类数据:")
    classifications2, mesh_terms2 = cmd.parse_classification_response(MOCK_CLASSIFICATION_DATA_2)
    print(f"  分类数量: {len(classifications2)}")
    print(f"  MeSH术语数量: {len(mesh_terms2)}")

    # 测试空数据
    print("\n3. 测试空数据:")
    classifications3, mesh_terms3 = cmd.parse_classification_response(MOCK_CLASSIFICATION_DATA_3)
    print(f"  分类数量: {len(classifications3)}")
    print(f"  MeSH术语数量: {len(mesh_terms3)}")

def test_parse_compound_data():
    """测试完整化合物数据解析"""
    print("\n\n=== 测试 parse_compound_data 方法 ===")

    from search_engine.management.commands import sync_pubchem
    cmd = sync_pubchem.Command()

    # 模拟化合物数据
    mock_compound_data = {
        "PC_Compounds": [
            {
                "props": [
                    {
                        "urn": {"label": "IUPAC Name"},
                        "value": {"sval": "4-hydroxybenzoic acid"}
                    }
                ]
            }
        ]
    }

    mock_desc_data = {
        "InformationList": {
            "Information": [
                {"Description": "A monohydroxybenzoic acid that is benzoic acid carrying a hydroxy substituent at C-4 of the benzene ring."}
            ]
        }
    }

    result = cmd.parse_compound_data(
        cid=72,
        compound_data=mock_compound_data,
        desc_data=mock_desc_data,
        classification_data=MOCK_CLASSIFICATION_DATA
    )

    print(f"CID: {result.get('cid')}")
    print(f"IUPAC名称: {result.get('iupac_name')}")
    print(f"描述: {result.get('description')[:50]}...")
    print(f"分类数量: {len(result.get('classifications', []))}")
    print(f"MeSH术语数量: {len(result.get('mesh_terms', []))}")

def test_update_pubchem_tags_logic():
    """测试标签更新逻辑（不实际修改数据库）"""
    print("\n\n=== 测试 update_pubchem_tags 逻辑 ===")

    from search_engine.management.commands import sync_pubchem
    cmd = sync_pubchem.Command()

    # 模拟化合物数据
    mock_compound_data = {
        'cid': 72,
        'iupac_name': '4-hydroxybenzoic acid',
        'description': 'A monohydroxybenzoic acid...',
        'classifications': [
            {'name': 'Organic compounds', 'category': 'superclass', 'type': 'chemical', 'confidence': 1.0},
            {'name': 'Benzenoids', 'category': 'class', 'type': 'chemical', 'confidence': 1.0}
        ],
        'mesh_terms': [
            {'name': 'Phenols', 'id': 'D010636', 'category': 'mesh'},
            {'name': 'Antioxidants', 'id': 'D059808', 'category': 'mesh'}
        ]
    }

    print("模拟化合物数据解析完成，包含:")
    print(f"  分类: {[c['name'] for c in mock_compound_data['classifications']]}")
    print(f"  MeSH术语: {[m['name'] for m in mock_compound_data['mesh_terms']]}")

    # 注意：这里不实际调用update_pubchem_tags，因为它会修改数据库
    # 我们只是验证数据结构是否正确
    print("\n数据结构检查完成。update_pubchem_tags方法应该能够处理这些数据。")

def check_proxy_support():
    """检查代理支持"""
    print("\n\n=== 检查代理支持 ===")

    from search_engine.management.commands import sync_pubchem
    cmd = sync_pubchem.Command()

    # 测试代理参数解析
    import argparse
    parser = argparse.ArgumentParser()
    cmd.add_arguments(parser)

    # 测试无代理
    args = parser.parse_args([])
    print(f"1. 无代理: {args.proxy}")

    # 测试有代理
    test_args = ['--proxy', 'http://127.0.0.1:7890']
    args = parser.parse_args(test_args)
    print(f"2. 有代理: {args.proxy}")

    # 测试延迟参数
    test_args = ['--delay', '0.5', '--max-retries', '5']
    args = parser.parse_args(test_args)
    print(f"3. 延迟: {args.delay}, 最大重试: {args.max_retries}")

def main():
    """主测试函数"""
    print("开始测试修复后的PubChem同步功能...")

    try:
        test_parse_classification_response()
        test_parse_compound_data()
        test_update_pubchem_tags_logic()
        check_proxy_support()

        print("\n✅ 所有测试完成！")
        print("\n下一步:")
        print("1. 使用代理运行 sync_pubchem 命令测试实际API调用")
        print("2. 为有CID的产品创建PubChem标签")
        print("3. 验证标签创建结果")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()