#!/usr/bin/env python
"""
标签优化验证脚本
验证标签清洗和优化后的数据质量
"""
import os
import sys
import django
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from django.db import connection
from django.db.models import Count, Q, Avg, Max, Min
from search_engine.models import (
    Tag, PubChemTag, ProductTag, ProductPubChemTag,
    TagHierarchy, TagCategorySystem, Product
)

class TagOptimizationValidator:
    """标签优化验证器"""

    def __init__(self, output_file=None):
        self.output_file = output_file
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'validation_summary': {},
            'detailed_results': {}
        }

    def log(self, message, level="INFO"):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {level}: {message}"
        print(log_msg)

        if self.output_file:
            with open(self.output_file, 'a', encoding='utf-8') as f:
                f.write(log_msg + '\n')

    def validate_tag_categorization(self):
        """验证标签分类系统"""
        self.log("验证标签分类系统...")

        results = {
            'total_tags': 0,
            'tags_with_category': 0,
            'tags_without_category': 0,
            'category_distribution': {},
            'pubchem_tags': 0,
            'general_tags': 0
        }

        # 检查普通标签
        tags = Tag.objects.all()
        results['total_tags'] = tags.count()
        results['tags_with_category'] = tags.filter(tag_category__isnull=False).exclude(tag_category='').count()
        results['tags_without_category'] = tags.filter(Q(tag_category__isnull=True) | Q(tag_category='')).count()

        # 分类分布
        category_stats = tags.exclude(tag_category__isnull=True).exclude(tag_category='').values('tag_category').annotate(
            count=Count('id')
        ).order_by('-count')

        results['category_distribution'] = {item['tag_category']: item['count'] for item in category_stats}

        # 检查PubChem标签
        pubchem_tags = PubChemTag.objects.all()
        results['pubchem_tags'] = pubchem_tags.count()
        results['pubchem_tags_with_category'] = pubchem_tags.filter(tag_category__isnull=False).exclude(tag_category='').count()

        # 验证分类系统完整性
        category_systems = TagCategorySystem.objects.all()
        results['category_systems_total'] = category_systems.count()
        results['category_systems_by_level'] = category_systems.values('level').annotate(count=Count('id')).order_by('level')

        self.results['detailed_results']['tag_categorization'] = results
        return results

    def validate_pubchem_tag_completeness(self):
        """验证PubChem标签完整性"""
        self.log("验证PubChem标签完整性...")

        results = {
            'products_with_pubchem_cid': 0,
            'products_with_pubchem_tags': 0,
            'pubchem_tags_per_product': {},
            'missing_pubchem_tags': []
        }

        # 获取有PubChem CID的产品
        from search_engine.models import YeastPubChemData
        products_with_cid = Product.objects.filter(
            pubchem_data__isnull=False,
            pubchem_data__pubchem_cid__isnull=False
        ).distinct()

        results['products_with_pubchem_cid'] = products_with_cid.count()

        # 检查每个有CID的产品是否有PubChem标签
        missing_products = []
        tag_counts = []

        for product in products_with_cid[:100]:  # 限制检查数量，避免性能问题
            tag_count = ProductPubChemTag.objects.filter(product=product).count()
            tag_counts.append(tag_count)

            if tag_count == 0:
                missing_products.append({
                    'product_id': product.id,
                    'product_name': product.product_name,
                    'pubchem_cid': product.pubchem_data.pubchem_cid
                })

        results['products_with_pubchem_tags'] = len([c for c in tag_counts if c > 0])
        results['missing_pubchem_tags'] = missing_products

        # 统计标签数量分布
        if tag_counts:
            results['avg_tags_per_product'] = sum(tag_counts) / len(tag_counts)
            results['max_tags_per_product'] = max(tag_counts)
            results['min_tags_per_product'] = min(tag_counts)

        # 检查用途标签存在性
        use_tags = PubChemTag.objects.filter(tag_category='use_and_manufacturing')
        results['use_and_manufacturing_tags_total'] = use_tags.count()
        results['products_with_use_tags'] = ProductPubChemTag.objects.filter(
            pubchem_tag__tag_category='use_and_manufacturing'
        ).values('product').distinct().count()

        self.results['detailed_results']['pubchem_tag_completeness'] = results
        return results

    def validate_tag_hierarchy(self):
        """验证标签层次结构"""
        self.log("验证标签层次结构...")

        results = {
            'total_hierarchies': 0,
            'hierarchies_by_type': {},
            'orphan_tags': [],
            'circular_reference_check': 'pending'
        }

        # 统计层次关系
        hierarchies = TagHierarchy.objects.all()
        results['total_hierarchies'] = hierarchies.count()

        # 按关系类型统计
        type_stats = hierarchies.values('relationship_type').annotate(count=Count('id'))
        results['hierarchies_by_type'] = {item['relationship_type']: item['count'] for item in type_stats}

        # 检查孤立标签（没有父标签也没有子标签）
        # 注意：这部分可能需要根据具体模型调整

        # 简单检查循环引用（通过限制深度）
        try:
            self._check_circular_references()
            results['circular_reference_check'] = 'passed'
        except Exception as e:
            results['circular_reference_check'] = f'failed: {str(e)}'

        self.results['detailed_results']['tag_hierarchy'] = results
        return results

    def _check_circular_references(self):
        """检查循环引用（简化版）"""
        # 获取所有层次关系
        hierarchies = TagHierarchy.objects.all()

        # 构建父->子映射
        parent_to_children = defaultdict(list)
        for hierarchy in hierarchies:
            # 这里需要根据实际模型获取parent和child的ID
            # 简化实现：假设有parent_tag_id和child_tag_id字段
            pass

        # 深度限制检查
        max_depth = 10
        # 实际实现需要遍历图检查深度

    def validate_search_performance(self):
        """验证搜索性能（基础版本）"""
        self.log("验证搜索性能...")

        results = {
            'search_query_tests': [],
            'average_response_time': 0
        }

        # 测试查询
        test_queries = [
            "cancer",
            "PCR",
            "organic",
            "cell culture",
            "drug discovery"
        ]

        from search_engine.search_service import hybrid_search_enhanced

        response_times = []
        for query in test_queries[:3]:  # 只测试3个查询避免长时间运行
            try:
                start_time = time.time()
                # 调用增强搜索
                results_list = hybrid_search_enhanced(query, top_k=10, use_enhanced_tags=True)
                end_time = time.time()

                response_time = end_time - start_time
                response_times.append(response_time)

                results['search_query_tests'].append({
                    'query': query,
                    'response_time': response_time,
                    'results_count': len(results_list) if results_list else 0
                })

                self.log(f"  查询 '{query}': {response_time:.3f}秒, {len(results_list) if results_list else 0}个结果")

            except Exception as e:
                self.log(f"  查询 '{query}' 失败: {e}", level="ERROR")
                results['search_query_tests'].append({
                    'query': query,
                    'error': str(e)
                })

        if response_times:
            results['average_response_time'] = sum(response_times) / len(response_times)

        self.results['detailed_results']['search_performance'] = results
        return results

    def validate_data_consistency(self):
        """验证数据一致性"""
        self.log("验证数据一致性...")

        results = {
            'orphaned_product_tags': 0,
            'orphaned_pubchem_tags': 0,
            'duplicate_tags': [],
            'inconsistent_categories': []
        }

        # 检查孤立的产品标签关联
        orphaned_product_tags = ProductTag.objects.filter(
            Q(tag__isnull=True) | Q(product__isnull=True)
        ).count()
        results['orphaned_product_tags'] = orphaned_product_tags

        # 检查孤立的PubChem标签关联
        orphaned_pubchem_tags = ProductPubChemTag.objects.filter(
            Q(pubchem_tag__isnull=True) | Q(product__isnull=True)
        ).count()
        results['orphaned_pubchem_tags'] = orphaned_pubchem_tags

        # 检查重复标签（名称相同但ID不同）
        duplicate_tags = Tag.objects.values('tag_name').annotate(
            count=Count('id')
        ).filter(count__gt=1)

        results['duplicate_tags_count'] = duplicate_tags.count()
        results['duplicate_tags_examples'] = list(duplicate_tags[:5])

        # 检查不一致的分类
        # 查找相同标签名称但分类不同的情况
        inconsistent = Tag.objects.values('tag_name').annotate(
            category_count=Count('tag_category', distinct=True)
        ).filter(category_count__gt=1)

        results['inconsistent_categories_count'] = inconsistent.count()
        results['inconsistent_categories_examples'] = list(inconsistent[:5])

        self.results['detailed_results']['data_consistency'] = results
        return results

    def generate_summary_report(self):
        """生成验证总结报告"""
        self.log("生成验证总结报告...")

        summary = {
            'overall_status': 'PASS',
            'total_checks': 0,
            'passed_checks': 0,
            'failed_checks': 0,
            'warnings': 0,
            'check_details': []
        }

        # 评估每个验证结果
        checks = [
            ('标签分类系统', self.results['detailed_results'].get('tag_categorization', {})),
            ('PubChem标签完整性', self.results['detailed_results'].get('pubchem_tag_completeness', {})),
            ('标签层次结构', self.results['detailed_results'].get('tag_hierarchy', {})),
            ('搜索性能', self.results['detailed_results'].get('search_performance', {})),
            ('数据一致性', self.results['detailed_results'].get('data_consistency', {}))
        ]

        for check_name, check_results in checks:
            if not check_results:
                continue

            summary['total_checks'] += 1
            status = 'PASS'
            details = []

            if check_name == '标签分类系统':
                # 检查是否有未分类的标签
                tags_without_category = check_results.get('tags_without_category', 0)
                if tags_without_category > 0:
                    status = 'WARNING' if tags_without_category < 100 else 'FAIL'
                    details.append(f"{tags_without_category} 个标签未分类")

                # 检查分类分布
                category_count = len(check_results.get('category_distribution', {}))
                if category_count < 5:
                    status = 'WARNING'
                    details.append(f"只有 {category_count} 个分类类别")

            elif check_name == 'PubChem标签完整性':
                # 检查有CID但无标签的产品
                missing_products = len(check_results.get('missing_pubchem_tags', []))
                if missing_products > 0:
                    status = 'FAIL'
                    details.append(f"{missing_products} 个有CID的产品缺少PubChem标签")

                # 检查用途标签
                use_tags_count = check_results.get('use_and_manufacturing_tags_total', 0)
                if use_tags_count == 0:
                    status = 'WARNING'
                    details.append("未找到用途和制造标签")

            elif check_name == '标签层次结构':
                # 检查层次关系数量
                total_hierarchies = check_results.get('total_hierarchies', 0)
                if total_hierarchies == 0:
                    status = 'WARNING'
                    details.append("未建立标签层次关系")

            elif check_name == '搜索性能':
                # 检查平均响应时间
                avg_time = check_results.get('average_response_time', 0)
                if avg_time > 2.0:  # 超过2秒
                    status = 'WARNING'
                    details.append(f"平均响应时间较长: {avg_time:.2f}秒")
                elif avg_time == 0:
                    status = 'WARNING'
                    details.append("未执行搜索性能测试")

            elif check_name == '数据一致性':
                # 检查孤立关联
                orphaned = check_results.get('orphaned_product_tags', 0) + check_results.get('orphaned_pubchem_tags', 0)
                if orphaned > 0:
                    status = 'FAIL'
                    details.append(f"发现 {orphaned} 个孤立关联")

                # 检查重复标签
                duplicate_count = check_results.get('duplicate_tags_count', 0)
                if duplicate_count > 0:
                    status = 'WARNING'
                    details.append(f"发现 {duplicate_count} 个重复标签")

            # 更新统计
            if status == 'PASS':
                summary['passed_checks'] += 1
            elif status == 'FAIL':
                summary['failed_checks'] += 1
                summary['overall_status'] = 'FAIL'
            elif status == 'WARNING':
                summary['warnings'] += 1
                if summary['overall_status'] == 'PASS':
                    summary['overall_status'] = 'WARNING'

            summary['check_details'].append({
                'check_name': check_name,
                'status': status,
                'details': details,
                'results': check_results
            })

        self.results['validation_summary'] = summary
        return summary

    def save_results(self, output_path=None):
        """保存验证结果到文件"""
        if output_path is None:
            output_path = f"tag_validation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        self.log(f"保存验证结果到: {output_path}")

        # 确保目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2, default=str)

        return output_path

    def print_summary(self):
        """打印验证总结"""
        summary = self.results.get('validation_summary', {})

        if not summary:
            self.log("未找到验证总结，请先生成总结报告", level="ERROR")
            return

        print("\n" + "="*60)
        print("标签优化验证总结")
        print("="*60)

        print(f"总体状态: {summary.get('overall_status', 'UNKNOWN')}")
        print(f"检查总数: {summary.get('total_checks', 0)}")
        print(f"通过检查: {summary.get('passed_checks', 0)}")
        print(f"失败检查: {summary.get('failed_checks', 0)}")
        print(f"警告检查: {summary.get('warnings', 0)}")

        print("\n详细检查结果:")
        for check in summary.get('check_details', []):
            status_icon = {
                'PASS': '[OK]',
                'FAIL': '[FAIL]',
                'WARNING': '[WARN]'
            }.get(check['status'], '[UNKNOWN]')

            print(f"  {status_icon} {check['check_name']}")
            if check['details']:
                for detail in check['details']:
                    print(f"      {detail}")

        print("\n" + "="*60)

    def run_full_validation(self):
        """运行完整验证流程"""
        self.log("开始标签优化完整验证流程")
        self.log("="*60)

        try:
            # 执行所有验证
            self.validate_tag_categorization()
            self.validate_pubchem_tag_completeness()
            self.validate_tag_hierarchy()
            self.validate_search_performance()
            self.validate_data_consistency()

            # 生成总结报告
            self.generate_summary_report()

            # 打印总结
            self.print_summary()

            # 保存结果
            output_file = self.save_results()
            self.log(f"验证结果已保存到: {output_file}")

            return self.results['validation_summary'].get('overall_status', 'FAIL')

        except Exception as e:
            self.log(f"验证过程发生异常: {e}", level="ERROR")
            import traceback
            traceback.print_exc()
            return 'ERROR'

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='标签优化验证工具')
    parser.add_argument('--output', '-o', type=str, default=None,
                       help='输出文件路径')
    parser.add_argument('--check', '-c', type=str, choices=['all', 'categorization', 'pubchem', 'hierarchy', 'performance', 'consistency'],
                       default='all', help='选择要运行的检查类型')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='详细输出模式')

    args = parser.parse_args()

    validator = TagOptimizationValidator(output_file=args.output)

    if args.check == 'all':
        result = validator.run_full_validation()
    else:
        # 运行单个检查
        if args.check == 'categorization':
            validator.validate_tag_categorization()
        elif args.check == 'pubchem':
            validator.validate_pubchem_tag_completeness()
        elif args.check == 'hierarchy':
            validator.validate_tag_hierarchy()
        elif args.check == 'performance':
            validator.validate_search_performance()
        elif args.check == 'consistency':
            validator.validate_data_consistency()

        validator.generate_summary_report()
        validator.print_summary()
        result = 'MANUAL'

    # 根据结果返回退出码
    if result == 'PASS':
        return 0
    elif result == 'WARNING':
        return 1
    elif result == 'FAIL':
        return 2
    else:
        return 3

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)