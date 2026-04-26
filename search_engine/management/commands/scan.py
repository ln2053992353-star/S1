import os
import re
from django.core.management.base import BaseCommand
from search_engine.models import Product, ProductSource

# 尝试导入 PDF 库
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


class Command(BaseCommand):
    help = '扫描本地文件夹中的文献，自动匹配产物名称并提取 DOI 录入数据库'

    def add_arguments(self, parser):
        parser.add_argument('folder_path', type=str, help='文献所在的文件夹路径')

    def handle(self, *args, **options):
        # --- 🛠️ 路径自动修复逻辑 ---
        raw_path = options['folder_path']
        folder_path = raw_path.strip().strip('"').strip("'")
        folder_path = os.path.normpath(folder_path)

        if not os.path.exists(folder_path):
            self.stdout.write(self.style.ERROR(f"❌ 错误：系统找不到路径: [{folder_path}]"))
            return

        self.stdout.write(f"📂 正在扫描目录: {folder_path}")

        # --- 加载数据库 ---
        self.stdout.write("正在加载数据库产物列表...")
        all_products = Product.objects.all()
        # 建立 名字(小写) -> 对象 的映射，过滤掉过短的词防止误判
        product_map = {p.product_name.lower(): p for p in all_products if len(p.product_name) > 3}

        if not product_map:
            self.stdout.write(self.style.WARNING("⚠️ 警告：数据库中没有产物，或者产物名称都太短。"))
            return

        self.stdout.write(f"✅ 加载了 {len(product_map)} 个产物关键词。开始分析文件...")

        files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.pdf', '.txt'))]
        total_files = len(files)
        matched_count = 0

        for i, filename in enumerate(files):
            file_path = os.path.join(folder_path, filename)

            try:
                # 1. 提取文本
                content = self.extract_text(file_path)
                if not content:
                    continue
                content_lower = content.lower()

                # 2. 提取 DOI
                doi = self.extract_doi(content)

                # 3. 匹配产物
                for p_name, product_obj in product_map.items():
                    # 核心匹配逻辑：文本中包含产物名
                    # 使用两边加空格的方式模拟单词边界，防止把 'cell' 匹配到 'cellphone'
                    # 或者直接用 in (更宽松)
                    if p_name in content_lower:

                        current_doi = doi if doi else "N/A"

                        source_obj, created = ProductSource.objects.get_or_create(
                            product=product_obj,
                            doi=current_doi,
                            defaults={'filename': filename}
                        )

                        if created or (source_obj.doi == "N/A" and current_doi != "N/A"):
                            if not created:
                                source_obj.doi = current_doi
                                source_obj.save()

                            self.stdout.write(self.style.SUCCESS(
                                f"   🔗 [MATCH] {filename[:15]}... -> {product_obj.product_name} (DOI: {current_doi})"
                            ))
                            matched_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ 处理出错 {filename}: {e}"))

            if (i + 1) % 10 == 0:
                self.stdout.write(f"   ...已处理 {i + 1}/{total_files} 个文件")

        self.stdout.write(self.style.SUCCESS(f"\n🎉 扫描完成！共建立了 {matched_count} 个文献关联。"))

    def extract_text(self, file_path):
        """提取文本内容"""
        text = ""
        try:
            if file_path.lower().endswith('.pdf'):
                if PdfReader is None:
                    return ""
                reader = PdfReader(file_path)

                # --- 🔥 修复点在这里 🔥 ---
                # pypdf 的 pages 是 _VirtualList，不能直接用 + 号
                # 我们必须把它们转换成 list() 之后再相加
                pages = reader.pages
                total_pages = len(pages)

                if total_pages > 5:
                    # 取前3页 + 后2页
                    target_pages = list(pages[:3]) + list(pages[-2:])
                else:
                    target_pages = list(pages)

                for page in target_pages:
                    extracted = page.extract_text()
                    if extracted: text += extracted + "\n"

            elif file_path.lower().endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
        except Exception as e:
            # 捕获具体的 PDF 读取错误，不中断整个脚本
            pass
        return text

    def extract_doi(self, text):
        """提取 DOI"""
        pattern = r'\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None