from django.core.management.base import BaseCommand
from django.db.models import Count, Min
from django.db import transaction
from database.models import Product, ProductTag, Tag


class Command(BaseCommand):
    help = 'Merge duplicate products and consolidate their tags (Refining the Knowledge Graph)'

    def handle(self, *args, **options):
        print("🚀 Starting Product Deduplication & Tag Fusion...")

        # 1. 找到所有重复的产物名称 (名字相同，但 ID 不同)
        duplicates = Product.objects.values('product_name') \
            .annotate(name_count=Count('product_id')) \
            .filter(name_count__gt=1)

        print(f"Found {duplicates.count()} products with duplicate entries.")

        with transaction.atomic():
            for dup in duplicates:
                name = dup['product_name']

                # 获取该名字下的所有记录
                products = list(Product.objects.filter(product_name=name).order_by('product_id'))

                # 选定第一个为主记录 (Master)，其他的为从记录 (Slaves)
                master_product = products[0]
                slave_products = products[1:]

                print(f"\nProcessing: {name}")
                print(f" > Master ID: {master_product.product_id}")

                # 2. 融合标签 (响应老师点 ①：合并文献1和文献2的描述)
                # 遍历所有从记录，把它们的标签“过继”给主记录
                moved_tags_count = 0
                for slave in slave_products:
                    # 获取从记录的所有标签关联
                    slave_relations = ProductTag.objects.filter(product=slave)

                    for relation in slave_relations:
                        tag = relation.tag
                        # 检查主记录是否已经有了这个标签
                        if not ProductTag.objects.filter(product=master_product, tag=tag).exists():
                            # 如果没有，就给主记录加上
                            ProductTag.objects.create(product=master_product, tag=tag)
                            moved_tags_count += 1

                    # 3. 融合描述 (可选：把 description 也拼起来，让描述更全面)
                    if slave.description and slave.description not in master_product.description:
                        master_product.description += f" | {slave.description}"

                master_product.save()

                # 4. 删除从记录 (响应老师点 ③：合并产物)
                # 注意：因为是从 Product 层面删除，级联删除会自动删掉旧的 product_tags 关联
                for slave in slave_products:
                    print(f" > Deleting duplicate ID: {slave.product_id}")
                    slave.delete()

                print(f" > Merged {len(slave_products)} duplicates. Added {moved_tags_count} new tags to Master.")

        print("\n✅ Deduplication Complete! The database is now cleaner and richer.")