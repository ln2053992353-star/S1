#!/usr/bin/env python
"""
记录标签清洗前的数据状态，用于后续验证和对比
"""
import os
import sys
import json
import django
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import Tag, PubChemTag, Product, YeastPubChemData, ProductPubChemTag

def record_status():
    """记录当前数据状态"""
    status = {
        'timestamp': datetime.now().isoformat(),
        'database': 'demo1',
        'record_type': 'pre_cleanup_status',
        'data': {}
    }

    # 1. 标签统计
    tags = Tag.objects.all()
    status['data']['tags'] = {
        'total_count': tags.count(),
        'with_category': tags.filter(tag_category__isnull=False).count(),
        'without_category': tags.filter(tag_category__isnull=True).count(),
        'sample_tags': [{'id': t.tag_id, 'name': t.tag_name, 'category': t.tag_category}
                       for t in tags[:20]]
    }

    # 2. PubChem标签统计
    pubchem_tags = PubChemTag.objects.all()
    status['data']['pubchem_tags'] = {
        'total_count': pubchem_tags.count(),
        'with_classification': pubchem_tags.filter(pubchem_classification__isnull=False).count(),
        'sample_tags': [{'id': t.tag_id, 'name': t.tag_name, 'category': t.tag_category,
                        'classification': t.pubchem_classification}
                       for t in pubchem_tags[:20]]
    }

    # 3. 产品标签关联统计
    products_with_tags = Product.objects.filter(tags__isnull=False).distinct()
    products_with_pubchem_tags = Product.objects.filter(pubchem_tags__isnull=False).distinct()

    status['data']['product_tag_relations'] = {
        'products_with_tags': products_with_tags.count(),
        'products_with_pubchem_tags': products_with_pubchem_tags.count(),
        'total_product_tag_relations': Tag.objects.filter(product__isnull=False).count(),
        'total_pubchem_tag_relations': ProductPubChemTag.objects.count()
    }

    # 4. PubChem数据统计
    pubchem_data = YeastPubChemData.objects.all()
    status['data']['pubchem_data'] = {
        'total_records': pubchem_data.count(),
        'with_cid': pubchem_data.filter(pubchem_cid__isnull=False).count(),
        'without_cid': pubchem_data.filter(pubchem_cid__isnull=True).count(),
        'sync_failed': pubchem_data.filter(sync_failed=True).count(),
        'sync_success': pubchem_data.filter(sync_failed=False, pubchem_cid__isnull=False).count()
    }

    # 5. 标签名称分析（去重后）
    tag_names = [t.tag_name.lower() for t in tags]
    unique_tag_names = set(tag_names)

    status['data']['tag_analysis'] = {
        'total_unique_lowercase': len(unique_tag_names),
        'case_variations': len(tag_names) - len(unique_tag_names),
        'avg_tag_length': sum(len(name) for name in tag_names) / len(tag_names) if tag_names else 0
    }

    # 保存状态文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"backups/pre_cleanup_status_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(f"状态记录已保存到: {output_file}")
    print(f"标签总数: {status['data']['tags']['total_count']}")
    print(f"有分类的标签: {status['data']['tags']['with_category']}")
    print(f"PubChem标签总数: {status['data']['pubchem_tags']['total_count']}")
    print(f"有PubChem CID的产品: {status['data']['pubchem_data']['with_cid']}")
    print(f"同步失败的产品: {status['data']['pubchem_data']['sync_failed']}")

    return output_file

if __name__ == "__main__":
    record_status()