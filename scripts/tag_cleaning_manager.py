#!/usr/bin/env python
"""
标签清洗管理器

功能：
1. 管理分批清洗普通标签（三批次共2733个）
2. 进度跟踪和断点续传
3. 质量监控和报告生成
"""
import os
import sys
import django
import time
import json
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from search_engine.models import Tag, ProductTag, Product

# 导入清洗器
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from ai_tag_cleaner import TagCleaner
    AI_CLEANER_AVAILABLE = True
except ImportError:
    AI_CLEANER_AVAILABLE = False
    print("警告: 无法导入ai_tag_cleaner，将使用基础清洗功能")

class TagCleaningManager:
    """标签清洗管理器"""

    def __init__(self, progress_file: str = "tag_cleaning_progress.json"):
        """
        初始化管理器

        Args:
            progress_file: 进度文件路径
        """
        self.progress_file = progress_file
        self.progress = self._load_progress()

        # 创建清洗器
        if AI_CLEANER_AVAILABLE:
            self.cleaner = TagCleaner(batch_size=30, delay=0.4)
        else:
            self.cleaner = None

    def _load_progress(self) -> Dict[str, Any]:
        """加载进度"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass

        # 默认进度
        return {
            "total_tags": 0,
            "processed_tags": 0,
            "batches_completed": 0,
            "current_batch": 1,
            "start_time": None,
            "last_update": None,
            "status": "not_started",
            "batches": {
                "batch_1": {"size": 500, "processed": 0, "status": "pending"},
                "batch_2": {"size": 1000, "processed": 0, "status": "pending"},
                "batch_3": {"size": 1233, "processed": 0, "status": "pending"}
            }
        }

    def _save_progress(self):
        """保存进度"""
        self.progress["last_update"] = datetime.now().isoformat()

        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存进度失败: {e}")

    def get_current_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        # 数据库实际状态
        total_tags = Tag.objects.count()
        categorized_tags = Tag.objects.filter(tag_category__isnull=False).count()
        uncategorized_tags = total_tags - categorized_tags

        # 更新进度中的总数
        self.progress["total_tags"] = total_tags
        self.progress["uncategorized_tags"] = uncategorized_tags

        return {
            "database_stats": {
                "total_tags": total_tags,
                "categorized_tags": categorized_tags,
                "uncategorized_tags": uncategorized_tags,
                "categorization_rate": categorized_tags / total_tags if total_tags > 0 else 0
            },
            "progress": self.progress,
            "ai_cleaner_available": AI_CLEANER_AVAILABLE
        }

    def prepare_batches(self) -> List[Dict[str, Any]]:
        """准备分批任务"""
        print("准备分批清洗任务...")

        # 获取所有未分类标签
        uncategorized_tags = Tag.objects.filter(tag_category__isnull=False)
        # 注意：我们实际要清洗的是未分类标签，但根据之前记录，所有2733个标签都未分类
        # 所以我们应该清洗所有标签
        all_tags = Tag.objects.all()
        total_tags = all_tags.count()

        print(f"找到 {total_tags} 个标签")

        # 定义批次（根据计划）
        batch_sizes = [500, 1000, 1233]
        batches = []

        start_index = 0
        for i, size in enumerate(batch_sizes):
            if start_index >= total_tags:
                break

            actual_size = min(size, total_tags - start_index)
            batch_tags = all_tags[start_index:start_index + actual_size]

            batches.append({
                "batch_id": i + 1,
                "planned_size": size,
                "actual_size": actual_size,
                "start_index": start_index,
                "end_index": start_index + actual_size - 1,
                "tag_ids": [tag.tag_id for tag in batch_tags],
                "status": "pending"
            })

            start_index += actual_size

        # 如果有剩余标签，添加到最后一个批次
        if start_index < total_tags:
            if batches:
                last_batch = batches[-1]
                remaining = total_tags - start_index
                last_batch["actual_size"] += remaining
                last_batch["end_index"] = total_tags - 1
                # 获取额外的标签ID
                extra_tags = all_tags[start_index:total_tags]
                last_batch["tag_ids"].extend([tag.tag_id for tag in extra_tags])
            else:
                # 只有一个批次
                batches.append({
                    "batch_id": 1,
                    "planned_size": total_tags,
                    "actual_size": total_tags,
                    "start_index": 0,
                    "end_index": total_tags - 1,
                    "tag_ids": [tag.tag_id for tag in all_tags],
                    "status": "pending"
                })

        print(f"准备完成: {len(batches)} 个批次")
        for batch in batches:
            print(f"  批次 {batch['batch_id']}: {batch['actual_size']} 个标签")

        # 保存批次信息到进度
        self.progress["batches"] = {}
        for batch in batches:
            self.progress["batches"][f"batch_{batch['batch_id']}"] = {
                "size": batch["actual_size"],
                "processed": 0,
                "status": "pending",
                "tag_ids": batch["tag_ids"]
            }

        self._save_progress()

        return batches

    def run_batch(self, batch_id: int, dry_run: bool = False) -> Dict[str, Any]:
        """
        运行单个批次

        Args:
            batch_id: 批次ID
            dry_run: 试运行（不实际修改数据库）

        Returns:
            批次结果
        """
        print(f"\n{'='*60}")
        print(f"运行批次 {batch_id}")
        print(f"{'='*60}")

        # 检查批次是否存在
        batch_key = f"batch_{batch_id}"
        if batch_key not in self.progress["batches"]:
            print(f"错误: 批次 {batch_id} 不存在")
            return {"success": False, "error": f"批次 {batch_id} 不存在"}

        batch_info = self.progress["batches"][batch_key]

        # 获取标签
        tag_ids = batch_info.get("tag_ids", [])
        if not tag_ids:
            print(f"批次 {batch_id} 没有标签")
            return {"success": False, "error": "没有标签"}

        tags = Tag.objects.filter(tag_id__in=tag_ids)
        actual_count = tags.count()

        print(f"批次大小: {batch_info['size']} (实际找到: {actual_count})")
        print(f"试运行模式: {dry_run}")

        if actual_count == 0:
            print("没有找到标签，跳过批次")
            batch_info["status"] = "skipped"
            self._save_progress()
            return {"success": True, "skipped": True}

        # 更新状态
        batch_info["status"] = "running"
        self.progress["status"] = f"running_batch_{batch_id}"
        self.progress["current_batch"] = batch_id
        if not self.progress["start_time"]:
            self.progress["start_time"] = datetime.now().isoformat()
        self._save_progress()

        # 运行清洗
        if self.cleaner and not dry_run:
            print("使用AI清洗器...")
            result = self._run_with_ai_cleaner(tags, batch_id)
        else:
            print(f"{'试运行' if dry_run else '使用基础清洗'}...")
            result = self._run_basic_cleaning(tags, batch_id, dry_run)

        # 更新进度
        batch_info["status"] = "completed" if result["success"] else "failed"
        batch_info["processed"] = result.get("processed_count", 0)
        batch_info["success_count"] = result.get("success_count", 0)
        batch_info["fail_count"] = result.get("fail_count", 0)
        batch_info["completion_time"] = datetime.now().isoformat()
        batch_info["result"] = result

        # 更新总进度
        self.progress["processed_tags"] += result.get("processed_count", 0)
        self.progress["batches_completed"] += 1 if result["success"] else 0

        if self.progress["batches_completed"] == len(self.progress["batches"]):
            self.progress["status"] = "completed"
        else:
            self.progress["status"] = "in_progress"

        self._save_progress()

        print(f"\n批次 {batch_id} 完成:")
        print(f"  处理标签: {result.get('processed_count', 0)}")
        print(f"  成功: {result.get('success_count', 0)}")
        print(f"  失败: {result.get('fail_count', 0)}")
        if result.get('success_count', 0) > 0:
            print(f"  成功率: {result.get('success_count', 0)/result.get('processed_count', 1):.1%}")

        return result

    def _run_with_ai_cleaner(self, tags, batch_id: int) -> Dict[str, Any]:
        """使用AI清洗器运行"""
        if not self.cleaner:
            return {"success": False, "error": "AI清洗器不可用"}

        # 暂时修改清洗器的批次大小
        original_batch_size = self.cleaner.batch_size
        self.cleaner.batch_size = min(20, len(tags))  # 更小的批次以减少内存使用

        try:
            # 运行清洗
            result = self.cleaner.clean_all_tags(limit=len(tags))

            return {
                "success": True,
                "processed_count": result["stats"]["processed_tags"],
                "success_count": result["success_count"],
                "fail_count": result["fail_count"],
                "success_rate": result["success_rate"],
                "details": result
            }

        except Exception as e:
            print(f"AI清洗失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "processed_count": 0,
                "success_count": 0,
                "fail_count": 0
            }
        finally:
            # 恢复原始批次大小
            self.cleaner.batch_size = original_batch_size

    def _run_basic_cleaning(self, tags, batch_id: int, dry_run: bool = False) -> Dict[str, Any]:
        """基础清洗（规则基础）"""
        success_count = 0
        fail_count = 0

        print(f"开始基础清洗 {len(tags)} 个标签...")

        # 简单分类规则
        category_rules = [
            (["PCR", "测序", "克隆", "基因编辑", "表达"], "实验技术::分子生物学技术"),
            (["细胞", "培养", "转染", "凋亡", "增殖"], "实验技术::细胞生物学技术"),
            (["HPLC", "质谱", "色谱", "光谱", "分析"], "实验技术::分析检测技术"),
            (["酸", "碱", "盐", "化合物", "分子"], "化合物类别::有机化合物"),
            (["蛋白", "酶", "抗体", "多肽"], "化合物类别::生物大分子"),
            (["代谢", "通路", "信号", "调控", "表达"], "生物过程::代谢过程"),
            (["癌症", "肿瘤", "疾病", "治疗", "药物"], "疾病相关::癌症相关"),
        ]

        for i, tag in enumerate(tags):
            try:
                # 检查是否已分类
                if tag.tag_category and not dry_run:
                    success_count += 1
                    continue

                # 应用规则
                assigned_category = None
                tag_lower = tag.tag_name.lower()

                for keywords, category in category_rules:
                    if any(keyword.lower() in tag_lower for keyword in keywords):
                        assigned_category = category
                        break

                if not assigned_category:
                    # 默认分类
                    assigned_category = "其他::未分类"

                # 更新标签（如果不是试运行）
                if not dry_run:
                    tag.tag_category = assigned_category
                    tag.save()

                success_count += 1

                # 进度显示
                if (i + 1) % 50 == 0:
                    print(f"  进度: {i+1}/{len(tags)}")

            except Exception as e:
                print(f"  处理失败 {tag.tag_name}: {e}")
                fail_count += 1

            # 小延迟避免数据库压力
            if not dry_run and (i + 1) % 20 == 0:
                time.sleep(0.1)

        return {
            "success": True,
            "processed_count": len(tags),
            "success_count": success_count,
            "fail_count": fail_count,
            "success_rate": success_count / len(tags) if len(tags) > 0 else 0,
            "method": "basic_cleaning",
            "dry_run": dry_run
        }

    def run_all_batches(self, start_from: int = 1, dry_run: bool = False) -> Dict[str, Any]:
        """
        运行所有批次

        Args:
            start_from: 从哪个批次开始
            dry_run: 试运行

        Returns:
            总体结果
        """
        print("开始运行所有批次...")

        total_results = {
            "total_batches": 0,
            "completed_batches": 0,
            "total_tags_processed": 0,
            "total_success": 0,
            "total_fail": 0,
            "batch_results": []
        }

        # 获取批次列表
        batch_keys = sorted([k for k in self.progress["batches"].keys() if k.startswith("batch_")])
        total_results["total_batches"] = len(batch_keys)

        print(f"总共 {len(batch_keys)} 个批次")

        for batch_key in batch_keys:
            batch_id = int(batch_key.replace("batch_", ""))

            if batch_id < start_from:
                print(f"跳过批次 {batch_id} (从批次 {start_from} 开始)")
                continue

            # 检查批次状态
            batch_info = self.progress["batches"][batch_key]
            if batch_info["status"] == "completed":
                print(f"批次 {batch_id} 已完成，跳过")
                continue

            # 运行批次
            batch_result = self.run_batch(batch_id, dry_run=dry_run)

            total_results["batch_results"].append({
                "batch_id": batch_id,
                "result": batch_result
            })

            if batch_result["success"]:
                total_results["completed_batches"] += 1
                total_results["total_tags_processed"] += batch_result.get("processed_count", 0)
                total_results["total_success"] += batch_result.get("success_count", 0)
                total_results["total_fail"] += batch_result.get("fail_count", 0)

            # 批次间延迟
            if batch_id < len(batch_keys):
                print(f"\n等待3秒后继续下一个批次...")
                time.sleep(3)

        # 计算总体成功率
        if total_results["total_tags_processed"] > 0:
            total_results["overall_success_rate"] = total_results["total_success"] / total_results["total_tags_processed"]
        else:
            total_results["overall_success_rate"] = 0

        print(f"\n{'='*60}")
        print("所有批次完成!")
        print(f"{'='*60}")
        print(f"总批次: {total_results['total_batches']}")
        print(f"完成批次: {total_results['completed_batches']}")
        print(f"处理标签: {total_results['total_tags_processed']}")
        print(f"成功标签: {total_results['total_success']}")
        print(f"失败标签: {total_results['total_fail']}")
        print(f"总体成功率: {total_results['overall_success_rate']:.1%}")

        # 生成最终报告
        if not dry_run:
            self.generate_final_report(total_results)

        return total_results

    def generate_final_report(self, results: Dict[str, Any] = None) -> Dict[str, Any]:
        """生成最终报告"""
        print("\n生成最终报告...")

        # 获取当前状态
        status = self.get_current_status()
        db_stats = status["database_stats"]

        # 最终报告
        report = {
            "generated_at": datetime.now().isoformat(),
            "database_summary": db_stats,
            "cleaning_progress": self.progress,
            "batch_results": results
        }

        # 保存报告到文件
        report_file = f"tag_cleaning_final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"最终报告已保存到: {report_file}")
        except Exception as e:
            print(f"保存报告失败: {e}")

        # 打印摘要
        print(f"\n{'='*60}")
        print("清洗完成摘要")
        print(f"{'='*60}")
        print(f"标签总数: {db_stats['total_tags']}")
        print(f"已分类标签: {db_stats['categorized_tags']}")
        print(f"未分类标签: {db_stats['uncategorized_tags']}")
        print(f"分类率: {db_stats['categorization_rate']:.1%}")

        if results:
            print(f"\n批次处理结果:")
            print(f"  总批次: {results['total_batches']}")
            print(f"  完成批次: {results['completed_batches']}")
            print(f"  处理标签: {results['total_tags_processed']}")
            print(f"  总体成功率: {results.get('overall_success_rate', 0):.1%}")

        return report

    def reset_progress(self):
        """重置进度"""
        confirm = input("确认重置进度? 这将删除所有进度记录。 (y/n): ").lower() == 'y'
        if confirm:
            self.progress = {
                "total_tags": 0,
                "processed_tags": 0,
                "batches_completed": 0,
                "current_batch": 1,
                "start_time": None,
                "last_update": None,
                "status": "not_started",
                "batches": {}
            }
            self._save_progress()
            print("进度已重置")
        else:
            print("取消重置")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='标签清洗管理器')
    parser.add_argument('action', choices=['status', 'prepare', 'run-batch', 'run-all', 'report', 'reset'],
                       help='执行的操作')
    parser.add_argument('--batch', type=int, help='批次ID (用于run-batch)')
    parser.add_argument('--start-from', type=int, default=1, help='从哪个批次开始 (用于run-all)')
    parser.add_argument('--dry-run', action='store_true', help='试运行模式')
    parser.add_argument('--progress-file', default='tag_cleaning_progress.json',
                       help='进度文件路径')

    args = parser.parse_args()

    manager = TagCleaningManager(progress_file=args.progress_file)

    if args.action == 'status':
        # 显示状态
        status = manager.get_current_status()
        db_stats = status["database_stats"]

        print("当前状态:")
        print(f"  标签总数: {db_stats['total_tags']}")
        print(f"  已分类: {db_stats['categorized_tags']}")
        print(f"  未分类: {db_stats['uncategorized_tags']}")
        print(f"  分类率: {db_stats['categorization_rate']:.1%}")

        print(f"\n进度状态: {status['progress']['status']}")
        print(f"处理标签: {status['progress']['processed_tags']}")
        print(f"完成批次: {status['progress']['batches_completed']}")

        if status['progress']['batches']:
            print("\n批次详情:")
            for batch_key, batch_info in status['progress']['batches'].items():
                print(f"  {batch_key}: {batch_info['size']} 标签, 状态: {batch_info['status']}, 已处理: {batch_info['processed']}")

        print(f"\nAI清洗器可用: {status['ai_cleaner_available']}")

    elif args.action == 'prepare':
        # 准备批次
        batches = manager.prepare_batches()
        print(f"准备完成: {len(batches)} 个批次")

    elif args.action == 'run-batch':
        # 运行单个批次
        if not args.batch:
            print("错误: 需要指定 --batch 参数")
            return

        manager.run_batch(args.batch, dry_run=args.dry_run)

    elif args.action == 'run-all':
        # 运行所有批次
        manager.run_all_batches(start_from=args.start_from, dry_run=args.dry_run)

    elif args.action == 'report':
        # 生成报告
        manager.generate_final_report()

    elif args.action == 'reset':
        # 重置进度
        manager.reset_progress()

if __name__ == "__main__":
    main()