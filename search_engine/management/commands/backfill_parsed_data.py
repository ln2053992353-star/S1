import sys
import time
import re
from django.core.management.base import BaseCommand
from django.db import transaction
from search_engine.models import ProductEmbedding, YeastPubChemData


class Command(BaseCommand):
    help = '数据回填：从embedding_text解析结构化信息，填充新字段，并根据PubChem CID修正source_database'

    def add_arguments(self, parser):
        """定义命令行参数"""
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=1000,
            help='分块处理大小（避免内存溢出），默认 1000'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='试运行模式（不实际保存更改）'
        )

    def handle(self, *args, **options):
        """命令主处理逻辑"""
        self.stdout.write("开始数据回填：解析embedding_text并填充新字段")
        self.stdout.write("=" * 60)

        chunk_size = options['chunk_size']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write("[警告] 试运行模式：不会实际保存更改")

        self.stdout.write(f"分块大小: {chunk_size}")
        self.stdout.write(f"试运行: {'是' if dry_run else '否'}")
        self.stdout.write("=" * 60)

        start_time = time.time()
        total_processed = 0
        total_updated = 0
        total_source_db_updated = 0

        try:
            # 获取所有ProductEmbedding对象，使用select_related优化查询
            embeddings = ProductEmbedding.objects.select_related(
                'product',
                'product__pubchem_data'
            ).prefetch_related('product__tags').all()

            # 用于批量更新的列表
            embeddings_to_update = []

            for i, embedding in enumerate(embeddings.iterator(chunk_size=chunk_size), 1):
                total_processed += 1
                updated = False

                # 1. 回填source_database：根据PubChem CID判断
                if hasattr(embedding.product, 'pubchem_data') and embedding.product.pubchem_data:
                    pubchem_data = embedding.product.pubchem_data
                    if pubchem_data.pubchem_cid and pubchem_data.pubchem_cid > 0:
                        # 存在有效的PubChem CID，将source_database设置为'PubChem'
                        if embedding.source_database != 'PubChem':
                            embedding.source_database = 'PubChem'
                            updated = True
                            total_source_db_updated += 1
                    else:
                        # 没有有效的PubChem CID，保持'Manual'
                        if embedding.source_database != 'Manual':
                            embedding.source_database = 'Manual'
                            updated = True
                            total_source_db_updated += 1
                else:
                    # 没有PubChem数据，保持'Manual'
                    if embedding.source_database != 'Manual':
                        embedding.source_database = 'Manual'
                        updated = True
                        total_source_db_updated += 1

                # 2. 从embedding_text解析结构化信息
                if embedding.embedding_text:
                    # 使用模型的解析方法
                    parsed = embedding.parse_embedding_text()

                    # 自定义解析IUPAC（处理"IUPAC: "格式）
                    iupac_from_text = self._extract_iupac_from_text(embedding.embedding_text)

                    # 填充function字段（如果为空且解析结果中有值）
                    if not embedding.function and parsed.get('function'):
                        embedding.function = parsed['function']
                        updated = True

                    # 填充pubchem_description字段
                    if not embedding.pubchem_description and parsed.get('pubchem_description'):
                        embedding.pubchem_description = parsed['pubchem_description']
                        updated = True

                    # 填充iupac_name字段 - 优先使用自定义解析结果
                    if not embedding.iupac_name:
                        if iupac_from_text:
                            embedding.iupac_name = iupac_from_text
                            updated = True
                        elif parsed.get('iupac_name'):
                            embedding.iupac_name = parsed['iupac_name']
                            updated = True

                    # 填充grna字段
                    if not embedding.grna and parsed.get('grna'):
                        embedding.grna = parsed['grna']
                        updated = True

                # 3. 从tags多对多关系生成tags_text
                if not embedding.tags_text and hasattr(embedding.product, 'tags'):
                    try:
                        tags = embedding.product.tags.all()
                        if tags:
                            tags_list = []
                            for tag in tags:
                                tag_text = tag.tag_name
                                if tag.tag_category:
                                    tag_text = f"{tag_text} ({tag.tag_category})"
                                tags_list.append(tag_text)
                            tags_text = "; ".join(tags_list)
                            if tags_text and tags_text != embedding.tags_text:
                                embedding.tags_text = tags_text
                                updated = True
                    except Exception as e:
                        self.stderr.write(f"警告: 处理产品 {embedding.product.product_id} 的标签时出错: {e}")

                # 如果字段有更新，添加到批量更新列表
                if updated:
                    embeddings_to_update.append(embedding)
                    total_updated += 1

                # 每处理1000条记录输出进度
                if i % 1000 == 0:
                    self.stdout.write(f"已处理 {i} 条记录，已更新 {total_updated} 条")

                # 批量更新：达到分块大小时执行
                if len(embeddings_to_update) >= chunk_size:
                    if not dry_run:
                        self._bulk_update_fields(embeddings_to_update)
                    else:
                        self.stdout.write(f"[试运行] 将批量更新 {len(embeddings_to_update)} 条记录")
                    embeddings_to_update = []

            # 处理剩余未更新的记录
            if embeddings_to_update:
                if not dry_run:
                    self._bulk_update_fields(embeddings_to_update)
                else:
                    self.stdout.write(f"[试运行] 将批量更新 {len(embeddings_to_update)} 条记录")

            elapsed_time = time.time() - start_time

            self.stdout.write("=" * 60)
            self.stdout.write("数据回填完成！")
            self.stdout.write(f"总处理记录: {total_processed}")
            self.stdout.write(f"总更新记录: {total_updated}")
            self.stdout.write(f"source_database更新数: {total_source_db_updated}")
            self.stdout.write(f"耗时: {elapsed_time:.2f} 秒")
            self.stdout.write(f"平均速度: {total_processed / elapsed_time:.2f} 条/秒")

            if dry_run:
                self.stdout.write("[警告]  试运行模式：未实际保存更改")
            else:
                self.stdout.write("[成功] 所有更改已保存到数据库")

        except Exception as e:
            self.stderr.write(f"[错误] 数据回填失败: {e}")
            import traceback
            self.stderr.write(traceback.format_exc())
            sys.exit(1)

    def _bulk_update_fields(self, embeddings):
        """批量更新指定的字段"""
        fields_to_update = [
            'source_database',
            'function',
            'pubchem_description',
            'iupac_name',
            'grna',
            'tags_text'
        ]

        try:
            with transaction.atomic():
                ProductEmbedding.objects.bulk_update(
                    embeddings,
                    fields_to_update,
                    batch_size=1000
                )
            self.stdout.write(f"[成功] 批量更新了 {len(embeddings)} 条记录")
        except Exception as e:
            self.stderr.write(f"[错误] 批量更新失败: {e}")
            raise

    def _extract_iupac_from_text(self, text):
        """从embedding_text中提取IUPAC名称（支持多种格式）"""
        if not text:
            return None

        # 尝试多种格式匹配
        patterns = [
            r'IUPAC:\s*(.+?)(?:\n|$)',          # 格式: IUPAC: xxx
            r'IUPAC Name:\s*(.+?)(?:\n|$)',     # 格式: IUPAC Name: xxx
            r'IUPAC[\s\-]?Name:\s*(.+?)(?:\n|$)' # 格式: IUPAC-Name: xxx 或 IUPAC Name: xxx
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                iupac = match.group(1).strip()
                # 清理可能的尾随标点
                iupac = re.sub(r'[.,;]$', '', iupac)
                if iupac and iupac.lower() not in ['n/a', 'na', 'none', '']:
                    return iupac

        return None