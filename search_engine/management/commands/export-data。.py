import os
import pandas as pd
from django.core.management.base import BaseCommand
from search_engine.models import Product


class Command(BaseCommand):
    help = '将数据库所有核心数据导出为 Excel，用于人工校准'

    def is_product_normalized(self, product):
        """判断产品是否已完成规范化清洗"""
        # 条件1：检查是否成功提取了PubChem外部数据
        has_external_data = False
        try:
            # 使用try...except处理可能不存在的关系字段
            if hasattr(product, 'pubchem_data'):
                pubchem_data = product.pubchem_data
                if pubchem_data:  # 确保不是None
                    # 检查pubchem_cid不为空
                    if pubchem_data.pubchem_cid:
                        # 根据sync_failed_reason判断是否算成功提取
                        if not pubchem_data.sync_failed:
                            # 未标记为失败，视为成功
                            has_external_data = True
                        else:
                            # 标记为失败，检查失败原因
                            failure_reason = pubchem_data.sync_failed_reason or ""
                            # 某些失败原因可能不影响数据有效性（如网络超时但已获取cid）
                            # 需要根据实际业务逻辑调整
                            non_critical_failures = [
                                "网络超时", "timeout", "速率限制", "rate limit",
                                "临时错误", "temporary error"
                            ]
                            # 如果失败原因不关键，且已有cid，仍可视为成功
                            if any(reason in failure_reason.lower() for reason in non_critical_failures):
                                has_external_data = True
                            # 否则视为失败
        except Exception as e:
            # 如果访问pubchem_data抛出异常（如ObjectDoesNotExist），视为无外部数据
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"访问product.pubchem_data时出错: {e}")
            has_external_data = False

        # 条件2：检查是否有有效、非空的AI功能描述
        has_valid_function = False
        if hasattr(product, 'embedding') and product.embedding:
            embedding = product.embedding
            summary = embedding.function

            if summary and summary.strip():
                summary = summary.strip()

                # 排除常见的占位符和默认值
                placeholders = [
                    "placeholder", "No functional summary", "N/A", "None",
                    "No description", "未找到", "无功能摘要", "待补充",
                    "TODO", "TBD", "待更新", "等待生成"
                ]

                is_placeholder = any(
                    ph.lower() in summary.lower() for ph in placeholders
                )

                # 基本长度检查（AI摘要通常有一定长度）
                min_length = 30

                # 检查是否是英文（AI清洗后应为英文）
                # 简单的英文检测：包含常见英文单词和标点
                has_english_indicators = any(
                    indicator in summary for indicator in
                    ['. ', ', ', ' the ', ' and ', ' for ', ' with ', ' that ']
                )

                # 综合判断：非占位符、足够长、有英文特征
                if (not is_placeholder and
                    len(summary) >= min_length and
                    has_english_indicators):
                    has_valid_function = True

        # 必须同时满足两个条件
        return has_external_data and has_valid_function

    def handle(self, *args, **options):
        self.stdout.write("正在从数据库提取数据...")

        # 1. 查询所有数据，并预加载关联表（防止查询几千次数据库）
        # select_related: 一对一关系 (Embedding, pubchem_data)
        # prefetch_related: 多对多/一对多关系 (Tags, Sources)
        products = Product.objects.all().select_related('embedding', 'pubchem_data').prefetch_related('tags', 'sources')

        data_list = []

        count = products.count()
        self.stdout.write(f"共找到 {count} 条产品数据，开始处理...")

        for p in products:
            # 安全获取 Embedding 数据 (防止有的产品还没有 Embedding)
            ai_summary = ""
            anchor_text = ""
            vector_status = "无向量"

            if hasattr(p, 'embedding'):
                ai_summary = p.embedding.function or ""
                anchor_text = p.embedding.embedding_text or ""
                if p.embedding.vector:
                    vector_status = "已生成 (768维)"

            # 获取标签 (逗号分隔)
            tags = ", ".join([t.tag_name for t in p.tags.all()])

            # 获取 DOI (逗号分隔)
            dois = ", ".join([s.doi for s in p.sources.all() if s.doi])

            # 判断规范化状态
            normalization_status = "已完成规范化清洗" if self.is_product_normalized(p) else "未规范化（数据缺失）"

            # 组装一行数据
            row = {
                'ID': p.product_id,
                '产品名称 (Name)': p.product_name,

                # --- 重点校准区域 ---
                'AI 功能描述 (Function)': ai_summary,
                '向量基准文本 (Anchor Text)': anchor_text,
                # -------------------

                '标签 (Tags)': tags,
                '文献 DOIs': dois,
                '原始描述 (Original)': p.description[:500] + "..." if p.description else "",  # 截断一下防止太长
                '向量状态': vector_status,
                '规范化状态': normalization_status,
                '来源文件': p.source_filename
            }
            data_list.append(row)

        # 2. 生成 DataFrame
        df = pd.DataFrame(data_list)

        # 3. 导出为 Excel
        output_file = "database_export_calibration.xlsx"

        # 简单美化：设置列宽逻辑交给 Excel 软件，这里只负责写入
        try:
            df.to_excel(output_file, index=False)
            self.stdout.write(self.style.SUCCESS(f"✅ 导出成功！文件已保存为: {os.path.abspath(output_file)}"))
            self.stdout.write("提示：请打开 Excel 查看 'AI 功能描述 (Function)' 和 '向量基准文本 (Anchor Text)' 列，这是影响搜索准确度的核心。")
        except PermissionError:
            self.stdout.write(self.style.ERROR("❌ 导出失败：请先关闭已经打开的 'database_export_calibration.xlsx' 文件！"))


