from django.core.management.base import BaseCommand
from search_engine.models import Product, YeastPubChemData


class Command(BaseCommand):
    help = '为现有Product初始化PubChem数据表'

    def handle(self, *args, **options):
        self.stdout.write("开始为现有Product初始化PubChem数据表...")

        created_count = 0
        skipped_count = 0

        for product in Product.objects.all():
            # 检查是否已存在PubChem数据记录
            if hasattr(product, 'pubchem_data'):
                skipped_count += 1
                continue

            # 创建空的PubChem数据记录
            YeastPubChemData.objects.create(product=product)
            created_count += 1

            if created_count % 100 == 0:
                self.stdout.write(f"已初始化{created_count}个产品...")

        self.stdout.write(self.style.SUCCESS(
            f"初始化完成！创建了{created_count}个新记录，跳过了{skipped_count}个已有记录"
        ))