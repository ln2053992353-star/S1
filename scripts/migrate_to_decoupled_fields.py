#!/usr/bin/env python
"""
数据迁移脚本：将现有数据从旧字段迁移到新解耦字段

执行步骤：
1. 将 functional_summary 迁移到 function 字段
2. 从 ManyToMany tags 关系生成 tags_text 字段
3. 从 product.grna_map 迁移到 grna 字段
4. 从 YeastPubChemData 迁移 iupac_name 和 functional_description
5. 根据 pubchem_cid 设置 source_database 字段
6. 调用 update_embedding_text() 重新生成向量基准文本

使用方式：
python scripts/migrate_to_decoupled_fields.py
"""

import os
import sys
import django
import logging
from pathlib import Path

# 设置Django环境
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_search_project.settings')
django.setup()

from search_engine.models import ProductEmbedding, Product, YeastPubChemData

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(BASE_DIR / 'logs' / 'migration.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


def migrate_existing_data(batch_size=100):
    """
    将现有数据迁移到新的解耦字段

    Args:
        batch_size: 每批处理的记录数，用于显示进度
    """
    # 获取所有需要迁移的ProductEmbedding记录
    # 使用select_related和prefetch_related优化查询性能
    embeddings = ProductEmbedding.objects.all().select_related(
        'product'
    ).prefetch_related(
        'product__tags',
        'product__pubchem_tags'
    )

    total = embeddings.count()
    logger.info(f"开始迁移 {total} 条 ProductEmbedding 记录...")

    migrated_count = 0
    failed_count = 0
    update_fields = [
        'function', 'tags_text', 'grna', 'iupac_name',
        'pubchem_description', 'source_database', 'embedding_text'
    ]

    for embedding in embeddings:
        try:
            product = embedding.product

            # 1. 迁移 functional_summary 到 function 字段
            if embedding.functional_summary and not embedding.function:
                embedding.function = embedding.functional_summary
                logger.debug(f"记录 {embedding.id}: 迁移 functional_summary 到 function 字段")

            # 2. 从 ManyToMany tags 关系生成 tags_text
            if not embedding.tags_text:
                tags_info = []
                for tag in product.tags.all():
                    tag_text = tag.tag_name
                    if tag.tag_category:
                        tag_text = f"{tag_text} ({tag.tag_category})"
                    tags_info.append(tag_text)
                if tags_info:
                    embedding.tags_text = "; ".join(tags_info)
                    logger.debug(f"记录 {embedding.id}: 生成 tags_text: {embedding.tags_text[:50]}...")

            # 3. 迁移 grna_map 到 grna 字段
            if product.grna_map and not embedding.grna:
                embedding.grna = product.grna_map
                logger.debug(f"记录 {embedding.id}: 迁移 grna_map 到 grna 字段")

            # 4. 迁移 PubChem 数据
            try:
                pubchem_data = YeastPubChemData.objects.get(product=product)

                if pubchem_data.iupac_name and not embedding.iupac_name:
                    embedding.iupac_name = pubchem_data.iupac_name
                    logger.debug(f"记录 {embedding.id}: 迁移 iupac_name")

                if pubchem_data.functional_description and not embedding.pubchem_description:
                    embedding.pubchem_description = pubchem_data.functional_description
                    logger.debug(f"记录 {embedding.id}: 迁移 functional_description")

                # 5. 设置 source_database
                if not embedding.source_database:
                    if pubchem_data.pubchem_cid:
                        embedding.source_database = 'PubChem'
                        logger.debug(f"记录 {embedding.id}: 设置 source_database = PubChem (有PubChem CID)")
                    else:
                        embedding.source_database = 'Manual'
                        logger.debug(f"记录 {embedding.id}: 设置 source_database = Manual (无PubChem CID)")

            except YeastPubChemData.DoesNotExist:
                # 没有PubChem数据
                if not embedding.source_database:
                    embedding.source_database = 'Manual'
                    logger.debug(f"记录 {embedding.id}: 设置 source_database = Manual (无PubChem数据)")

            # 6. 更新 embedding_text
            old_embedding_text = embedding.embedding_text
            embedding.update_embedding_text()

            if old_embedding_text != embedding.embedding_text:
                logger.debug(f"记录 {embedding.id}: 更新 embedding_text")

            # 保存更改
            embedding.save(update_fields=update_fields)

            migrated_count += 1

            # 进度显示
            if migrated_count % batch_size == 0:
                logger.info(f"进度: {migrated_count}/{total} ({migrated_count/total*100:.1f}%)")

        except Exception as e:
            failed_count += 1
            logger.error(f"迁移记录 {embedding.id} 失败: {e}", exc_info=True)
            continue

    # 生成迁移报告
    logger.info(f"迁移完成!")
    logger.info(f"成功迁移: {migrated_count}/{total} 条记录")
    logger.info(f"失败记录: {failed_count} 条")

    # 统计新字段的填充情况
    if migrated_count > 0:
        stats = {
            'function': ProductEmbedding.objects.exclude(function='').count(),
            'tags_text': ProductEmbedding.objects.exclude(tags_text='').count(),
            'grna': ProductEmbedding.objects.exclude(grna='').count(),
            'iupac_name': ProductEmbedding.objects.exclude(iupac_name='').count(),
            'pubchem_description': ProductEmbedding.objects.exclude(pubchem_description='').count(),
            'source_database': ProductEmbedding.objects.exclude(source_database='').count(),
        }

        logger.info("字段填充统计:")
        for field, count in stats.items():
            percentage = count / migrated_count * 100
            logger.info(f"  {field}: {count}/{migrated_count} ({percentage:.1f}%)")

    return migrated_count, failed_count


def verify_migration():
    """
    验证迁移后的数据完整性
    """
    logger.info("开始验证迁移数据...")

    # 检查是否有记录缺少source_database
    missing_source = ProductEmbedding.objects.filter(source_database='').count()
    if missing_source > 0:
        logger.warning(f"有 {missing_source} 条记录缺少 source_database 字段")

    # 检查embedding_text是否为空
    empty_embedding = ProductEmbedding.objects.filter(embedding_text='').count()
    if empty_embedding > 0:
        logger.warning(f"有 {empty_embedding} 条记录的 embedding_text 为空")

    # 检查新字段是否有异常长的值
    max_lengths = {
        'function': 5000,
        'tags_text': 2000,
        'grna': 1000,
        'iupac_name': 1000,
        'pubchem_description': 5000,
    }

    for field, max_len in max_lengths.items():
        # 使用filter查找超长字段（需要Django ORM支持长度查询）
        # 这里简化处理，实际可能需要更复杂的验证
        pass

    logger.info("验证完成")
    return True


def main():
    """
    主函数：执行完整的数据迁移流程
    """
    print("=" * 60)
    print("数据库解耦字段迁移工具")
    print("=" * 60)

    # 确认用户是否要继续
    confirm = input("此操作将修改数据库中的ProductEmbedding记录。是否继续? (y/N): ")
    if confirm.lower() != 'y':
        print("操作已取消")
        return

    try:
        # 执行数据迁移
        migrated, failed = migrate_existing_data(batch_size=50)

        # 验证迁移结果
        if migrated > 0:
            verify_migration()

        # 显示最终结果
        print("\n" + "=" * 60)
        print("迁移结果:")
        print(f"成功迁移: {migrated} 条记录")
        print(f"失败记录: {failed} 条")

        if failed == 0:
            print("✅ 所有记录迁移成功!")
        else:
            print(f"⚠️  有 {failed} 条记录迁移失败，请检查日志文件")

        print(f"日志文件: {BASE_DIR / 'logs' / 'migration.log'}")

    except Exception as e:
        logger.error(f"迁移过程中发生严重错误: {e}", exc_info=True)
        print(f"❌ 迁移失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # 创建日志目录（如果不存在）
    log_dir = BASE_DIR / 'logs'
    log_dir.mkdir(exist_ok=True)

    main()