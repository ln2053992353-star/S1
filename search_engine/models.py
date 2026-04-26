from django.db import models
import re
from django.utils.functional import cached_property
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


# =============================================================================
# 1. 核心业务模型 (对接原有数据库表)
# =============================================================================

class Product(models.Model):
    product_id = models.AutoField(primary_key=True)
    product_name = models.CharField(unique=True, max_length=255)
    grna_map = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    source_filename = models.CharField(max_length=255, blank=True, null=True)
    source_doi = models.CharField(max_length=255, blank=True, null=True)

    tags = models.ManyToManyField('Tag', through='ProductTag')

    # 新增PubChem标签关系
    pubchem_tags = models.ManyToManyField(
        'PubChemTag',
        through='ProductPubChemTag',
        related_name='products',
        blank=True,
        verbose_name="PubChem标签"
    )

    class Meta:
        managed = False  # 指向现有表
        db_table = 'products'
        verbose_name = 'Product'

    def __str__(self):
        return self.product_name


class Tag(models.Model):
    tag_id = models.AutoField(primary_key=True)
    tag_name = models.CharField(unique=True, max_length=255)
    tag_category = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tags'

    def __str__(self):
        return self.tag_name


class ProductTag(models.Model):
    id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, models.DO_NOTHING, db_column='product_id')
    tag = models.ForeignKey(Tag, models.DO_NOTHING, db_column='tag_id')

    class Meta:
        managed = False
        db_table = 'product_tags'
        unique_together = (('product', 'tag'),)


# ... 前面的 Product, Tag 等模型代码保持不变 ...

# =============================================================================
# 2. 向量搜索模型
# =============================================================================

class ProductEmbedding(models.Model):
    """
    存储 AI 分析结果和向量
    """
    product = models.OneToOneField(
        'Product',
        on_delete=models.CASCADE,
        related_name='embedding'
    )

    embedding_text = models.TextField(blank=True, null=True, verbose_name="向量基准文本")
    function = models.TextField(blank=True, null=True, verbose_name="功能描述")
    pubchem_description = models.TextField(blank=True, null=True, verbose_name="PubChem描述")
    tags_text = models.TextField(blank=True, null=True, verbose_name="标签文本")
    grna = models.TextField(blank=True, null=True, verbose_name="gRNA信息")
    iupac_name = models.TextField(blank=True, null=True, verbose_name="IUPAC名称")

    class SourceDatabase(models.TextChoices):
        PUBCHEM = 'PubChem', 'PubChem'
        MANUAL = 'Manual', 'Manual Entry / Local'
        UNIPROT = 'UniProt', 'UniProt'
        KEGG = 'KEGG', 'KEGG Pathway'

    source_database = models.CharField(
        max_length=20,
        choices=SourceDatabase.choices,
        default=SourceDatabase.MANUAL,
        verbose_name="来源数据库"
    )
    vector = models.TextField(help_text="JSON array of embedding floats")

    # 这里确保是 768 (对应 PubMedBert)
    model_name = models.CharField(max_length=100, default="S-PubMedBert-MS-MARCO")
    dim = models.IntegerField(default=768)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = "product_embeddings"

    def update_embedding_text(self):
        """构建丰富的嵌入文本，实现优雅降级的动态拼接（数据库解耦版）"""
        # 1. 产品基本信息（始终可用）
        product_name = self.product.product_name or ""
        description = self.product.description or ""

        # 2. 优先使用新字段，回退到旧字段和关联模型（优雅降级）
        # 功能描述
        function = self.function or ""

        # 标签文本：优先使用tags_text，否则遍历ManyToMany关系
        tags_str = self.tags_text or ""
        if not tags_str:
            try:
                tags_info = []
                for tag in self.product.tags.all():
                    tag_text = tag.tag_name
                    if tag.tag_category:
                        tag_text = f"{tag_text} ({tag.tag_category})"
                    tags_info.append(tag_text)
                tags_str = "; ".join(tags_info) if tags_info else ""
            except Exception:
                tags_str = ""

        # gRNA信息：优先使用grna字段，回退到product.grna_map
        grna = self.grna or self.product.grna_map or ""

        # IUPAC名称：优先使用iupac_name字段，回退到PubChem数据
        iupac_name = self.iupac_name or ""
        if not iupac_name and hasattr(self.product, 'pubchem_data') and self.product.pubchem_data:
            iupac_name = self.product.pubchem_data.iupac_name or ""

        # PubChem描述：优先使用pubchem_description字段，回退到PubChem数据
        pubchem_description = self.pubchem_description or ""
        if not pubchem_description and hasattr(self.product, 'pubchem_data') and self.product.pubchem_data:
            pubchem_description = self.product.pubchem_data.functional_description or ""

        # 3. 智能拼接：仅包含有值的字段，不添加任何占位符
        parts = []

        if product_name:
            parts.append(f"Product: {product_name}")

        if description:
            # 限制描述长度，避免文本过长
            desc_preview = description[:500] + "..." if len(description) > 500 else description
            parts.append(f"Description: {desc_preview}")

        if function:
            parts.append(f"Function: {function}")

        if grna:
            parts.append(f"gRNA: {grna}")

        if iupac_name:
            parts.append(f"IUPAC Name: {iupac_name}")

        if pubchem_description:
            # 限制PubChem描述长度
            desc_preview = pubchem_description[:500] + "..." if len(pubchem_description) > 500 else pubchem_description
            parts.append(f"PubChem Description: {desc_preview}")

        if tags_str:
            parts.append(f"Tags: {tags_str}")

        # 添加PubChem标签（从ManyToMany关系）
        pubchem_tags_info = []
        try:
            for tag in self.product.pubchem_tags.all():
                tag_text = tag.tag_name
                if tag.tag_category:
                    tag_text = f"{tag_text} ({tag.tag_category})"
                pubchem_tags_info.append(tag_text)
        except Exception:
            pubchem_tags_info = []

        pubchem_tags_str = "; ".join(pubchem_tags_info) if pubchem_tags_info else ""
        if pubchem_tags_str:
            parts.append(f"PubChem Tags: {pubchem_tags_str}")

        # 添加来源数据库信息（如果有值）
        if self.source_database:
            parts.append(f"Source Database: {self.source_database}")

        self.embedding_text = "\n".join(parts)

        # 4. 回退机制：如果没有任何内容，使用产品名称
        if not self.embedding_text.strip():
            self.embedding_text = product_name or "Unknown product"

        # 5. 限制总文本长度，避免超出模型token限制
        if len(self.embedding_text) > 2000:
            self.embedding_text = self.embedding_text[:1997] + "..."

    def parse_embedding_text(self):
        """
        从 embedding_text 中提取结构化信息，具备强鲁棒性

        格式示例：
        Product: Yeast strain with GFP reporter
        Description: A yeast strain engineered to express GFP...
        Function: This strain is used for monitoring protein expression...
        gRNA: ATGCTAGCTAG
        IUPAC Name: (2S)-2-amino-3-phenylpropanoic acid
        PubChem Description: A fluorescent protein used as a reporter...
        Tags: GFP (Fluorescent Proteins); Reporter (Reporters)
        PubChem Tags: Fluorescent dye (Organic dyes)
        Source Database: PubChem
        """
        parsed = {
            'product_name': '',
            'description': '',
            'function': '',
            'tags': [],
            'pubchem_tags': [],
            'grna': '',
            'iupac_name': '',
            'pubchem_description': '',
            'source_database': ''
        }

        if not self.embedding_text:
            return parsed

        try:
            # 使用正则表达式提取结构化信息
            text = self.embedding_text.strip()

            # 提取产品名称
            product_match = re.search(r'Product:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
            if product_match:
                parsed['product_name'] = product_match.group(1).strip()

            # 提取描述
            desc_match = re.search(r'Description:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
            if desc_match:
                parsed['description'] = desc_match.group(1).strip()

            # 提取功能描述（支持多行）
            func_match = re.search(r'Function:\s*(.+?)(?:\n(?!\w+:)|$)', text, re.IGNORECASE | re.DOTALL)
            if func_match:
                parsed['function'] = func_match.group(1).strip()

            # 提取标签
            tags_match = re.search(r'Tags:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
            if tags_match:
                tags_str = tags_match.group(1).strip()
                parsed['tags'] = [tag.strip() for tag in tags_str.split(';') if tag.strip()]

            # 提取PubChem标签
            pubchem_match = re.search(r'PubChem Tags:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
            if pubchem_match:
                tags_str = pubchem_match.group(1).strip()
                parsed['pubchem_tags'] = [tag.strip() for tag in tags_str.split(';') if tag.strip()]

            # 提取gRNA信息
            grna_match = re.search(r'gRNA:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
            if grna_match:
                parsed['grna'] = grna_match.group(1).strip()

            # 提取IUPAC名称
            iupac_match = re.search(r'IUPAC Name:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
            if iupac_match:
                parsed['iupac_name'] = iupac_match.group(1).strip()

            # 提取PubChem描述（支持多行）
            pubchem_desc_match = re.search(r'PubChem Description:\s*(.+?)(?:\n(?!\w+:)|$)', text, re.IGNORECASE | re.DOTALL)
            if pubchem_desc_match:
                parsed['pubchem_description'] = pubchem_desc_match.group(1).strip()

            # 提取来源数据库
            source_match = re.search(r'Source Database:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
            if source_match:
                parsed['source_database'] = source_match.group(1).strip()

        except Exception as e:
            # 记录错误但返回安全默认值
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"解析embedding_text失败 (ID: {self.pk if hasattr(self, 'pk') else 'unknown'}): {e}")

        return parsed

    @cached_property
    def parsed_embedding_text(self):
        """缓存解析结果，避免重复计算"""
        return self.parse_embedding_text()

    @cached_property
    def extracted_functional_summary(self):
        """从embedding_text中提取功能描述（缓存属性）"""
        return self.parsed_embedding_text.get('function', '')

    @cached_property
    def extracted_tags(self):
        """从embedding_text中提取标签（缓存属性）"""
        return self.parsed_embedding_text.get('tags', [])


# =============================================================================
# 5. 信号机制 (移到了类外面，这是正确的位置！)
# =============================================================================
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Product)
def auto_create_embedding(sender, instance, created, **kwargs):
    """
    当 Product 被创建时，自动创建一个对应的空 ProductEmbedding。
    """
    if created:
        ProductEmbedding.objects.get_or_create(product=instance)


# =============================================================================
# 6. 多来源支持 (解决一个产品对应多个 DOI 的问题)
# =============================================================================

class ProductSource(models.Model):
    """
    来源表：存储该产品对应的文献来源 (DOI)
    一个 Product 可以对应多个 ProductSource
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='sources'  # 关键：这让我们能通过 product.sources.all() 查到所有 DOI
    )

    doi = models.CharField(max_length=255, verbose_name="论文DOI")
    filename = models.CharField(max_length=255, blank=True, null=True, verbose_name="文件名/来源名")

    # 以后可以扩展：年份、作者、期刊名等
    # year = models.IntegerField(null=True)

    class Meta:
        managed = True
        db_table = 'product_sources'
        verbose_name = '文献来源'
        verbose_name_plural = '文献来源'

    def __str__(self):
        return f"{self.doi} ({self.product.product_name})"


# =============================================================================
# 7. PubChem数据库集成
# =============================================================================

class YeastPubChemData(models.Model):
    """
    PubChem数据扩展表，通过OneToOne关联到Product
    避免修改原有的managed=False的Product表
    """
    product = models.OneToOneField(
        'Product',
        on_delete=models.CASCADE,
        related_name='pubchem_data',
        primary_key=True,
        db_column='product_id'
    )

    # PubChem核心字段
    pubchem_cid = models.IntegerField(null=True, blank=True, verbose_name="PubChem CID")
    iupac_name = models.TextField(null=True, blank=True, verbose_name="IUPAC名称")
    functional_description = models.TextField(null=True, blank=True, verbose_name="功能描述(PubChem)")

    # 同步状态字段
    sync_failed = models.BooleanField(default=False, verbose_name="同步失败")
    sync_failed_reason = models.CharField(max_length=255, null=True, blank=True, verbose_name="失败原因")
    last_sync_attempt = models.DateTimeField(null=True, blank=True, verbose_name="最后同步尝试时间")
    last_sync_success = models.DateTimeField(null=True, blank=True, verbose_name="最后成功同步时间")

    class Meta:
        managed = True
        db_table = 'yeast_pubchem_data'
        verbose_name = 'PubChem数据'
        verbose_name_plural = 'PubChem数据'
        indexes = [
            models.Index(fields=['pubchem_cid']),
            models.Index(fields=['sync_failed']),
        ]

    def __str__(self):
        return f"PubChem数据 - {self.product.product_name}"


class PubChemTag(models.Model):
    """
    PubChem规范化标签系统（补充原有Tag系统）
    """
    tag_id = models.AutoField(primary_key=True)
    tag_name = models.CharField(max_length=255, unique=True, verbose_name="标签名称")
    tag_category = models.CharField(max_length=100, blank=True, null=True, verbose_name="标签类别")

    # PubChem分类信息
    pubchem_classification = models.CharField(max_length=200, blank=True, null=True, verbose_name="PubChem分类")
    mesh_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="MeSH ID")

    class Meta:
        managed = True
        db_table = 'pubchem_tags'
        verbose_name = 'PubChem标签'
        verbose_name_plural = 'PubChem标签'
        indexes = [
            models.Index(fields=['tag_category']),
            models.Index(fields=['pubchem_classification']),
        ]

    def __str__(self):
        category = f" ({self.tag_category})" if self.tag_category else ""
        return f"{self.tag_name}{category}"


class ProductPubChemTag(models.Model):
    """
    产品与PubChem标签的关联表（独立于原有的ProductTag）
    """
    id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, models.DO_NOTHING, db_column='product_id')
    pubchem_tag = models.ForeignKey(PubChemTag, models.DO_NOTHING, db_column='pubchem_tag_id')

    # 关联元数据
    confidence_score = models.FloatField(default=1.0, verbose_name="置信度")
    source = models.CharField(
        max_length=50,
        default='pubchem_api',
        choices=[('pubchem_api', 'PubChem API'), ('manual', '手动'), ('ai', 'AI分析')],
        verbose_name="来源"
    )

    class Meta:
        managed = True
        db_table = 'product_pubchem_tags'
        unique_together = (('product', 'pubchem_tag'),)
        verbose_name = '产品PubChem标签关联'
        verbose_name_plural = '产品PubChem标签关联'

    def __str__(self):
        return f"{self.product.product_name} - {self.pubchem_tag.tag_name}"


# =============================================================================
# 3. 标签层次结构系统
# =============================================================================

class TagHierarchy(models.Model):
    """
    标签层次关系系统（支持普通标签和PubChem标签）
    使用通用外键支持不同类型的标签
    """
    id = models.AutoField(primary_key=True)

    # 父标签（通用关系）
    parent_content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE,
        related_name='parent_tag_hierarchies',
        null=True,
        blank=True,
        verbose_name="父标签类型"
    )
    parent_object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name="父标签ID")
    parent_tag = GenericForeignKey('parent_content_type', 'parent_object_id')

    # 子标签（通用关系）
    child_content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE,
        related_name='child_tag_hierarchies',
        verbose_name="子标签类型"
    )
    child_object_id = models.PositiveIntegerField(verbose_name="子标签ID")
    child_tag = GenericForeignKey('child_content_type', 'child_object_id')

    # 关系属性
    relationship_type = models.CharField(
        max_length=50,
        choices=[
            ('parent_child', '父子关系'),
            ('synonym', '同义词'),
            ('related', '相关关系'),
            ('brother', '兄弟关系')
        ],
        default='parent_child',
        verbose_name="关系类型"
    )

    confidence = models.FloatField(default=1.0, verbose_name="置信度")
    source = models.CharField(
        max_length=50,
        choices=[
            ('ai_analysis', 'AI分析'),
            ('pubchem_api', 'PubChem API'),
            ('manual', '手动添加'),
            ('rule_based', '规则匹配')
        ],
        default='ai_analysis',
        verbose_name="来源"
    )

    # 层次级别（父标签的深度）
    level = models.IntegerField(default=1, verbose_name="层次级别")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'tag_hierarchies'
        verbose_name = '标签层次关系'
        verbose_name_plural = '标签层次关系'
        unique_together = (('parent_content_type', 'parent_object_id', 'child_content_type', 'child_object_id'),)
        indexes = [
            models.Index(fields=['parent_content_type', 'parent_object_id']),
            models.Index(fields=['child_content_type', 'child_object_id']),
            models.Index(fields=['relationship_type']),
            models.Index(fields=['level']),
        ]

    def __str__(self):
        parent_name = self.parent_tag.tag_name if self.parent_tag else 'ROOT'
        child_name = self.child_tag.tag_name if self.child_tag else 'UNKNOWN'
        return f"{parent_name} → {child_name} ({self.relationship_type})"

    def get_ancestors(self):
        """获取所有祖先标签"""
        ancestors = []
        current = self
        while current and current.parent_tag:
            ancestors.append(current.parent_tag)
            # 查找父级关系
            parent_hierarchy = TagHierarchy.objects.filter(
                child_content_type=current.parent_content_type,
                child_object_id=current.parent_object_id
            ).first()
            current = parent_hierarchy
        return list(reversed(ancestors))

    def get_descendants(self, max_depth=5):
        """获取所有后代标签（递归）"""
        descendants = []
        if max_depth <= 0:
            return descendants

        child_relations = TagHierarchy.objects.filter(
            parent_content_type=self.child_content_type,
            parent_object_id=self.child_object_id
        )

        for relation in child_relations:
            descendants.append(relation.child_tag)
            # 递归获取更深层次的后代
            if relation.child_tag:
                # 需要创建临时TagHierarchy对象来调用get_descendants
                temp_hierarchy = TagHierarchy(
                    child_content_type=relation.child_content_type,
                    child_object_id=relation.child_object_id
                )
                descendants.extend(temp_hierarchy.get_descendants(max_depth - 1))

        return descendants


class TagCategorySystem(models.Model):
    """
    标签分类系统 - 预定义分类层次
    """
    id = models.AutoField(primary_key=True)

    # 分类路径（例如：实验技术::分子生物学技术::PCR）
    category_path = models.CharField(max_length=255, unique=True, verbose_name="分类路径")

    # 显示名称
    display_name = models.CharField(max_length=255, verbose_name="显示名称")

    # 层级信息
    level = models.IntegerField(verbose_name="层级")
    parent_path = models.CharField(max_length=255, blank=True, null=True, verbose_name="父级路径")

    # 分类描述
    description = models.TextField(blank=True, null=True, verbose_name="描述")

    # 适用标签类型
    tag_type = models.CharField(
        max_length=20,
        choices=[
            ('general', '普通标签'),
            ('pubchem', 'PubChem标签'),
            ('both', '两者均可')
        ],
        default='both',
        verbose_name="适用标签类型"
    )

    # 示例标签
    example_tags = models.TextField(blank=True, null=True, verbose_name="示例标签")

    # 使用计数（用于智能推荐）
    usage_count = models.IntegerField(default=0, verbose_name="使用次数")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'tag_category_system'
        verbose_name = '标签分类'
        verbose_name_plural = '标签分类系统'
        indexes = [
            models.Index(fields=['category_path']),
            models.Index(fields=['level']),
            models.Index(fields=['tag_type']),
        ]

    def __str__(self):
        return f"{self.category_path} ({self.display_name})"

    def get_full_hierarchy(self):
        """获取完整的分类层次"""
        hierarchy = []
        current = self

        while current:
            hierarchy.insert(0, {
                'path': current.category_path,
                'name': current.display_name,
                'level': current.level
            })

            if current.parent_path:
                current = TagCategorySystem.objects.filter(category_path=current.parent_path).first()
            else:
                current = None

        return hierarchy

    @classmethod
    def get_category_tree(cls, tag_type='both'):
        """获取分类树结构"""
        categories = cls.objects.filter(tag_type__in=[tag_type, 'both']).order_by('category_path')

        # 构建树结构
        tree = {}
        for category in categories:
            parts = category.category_path.split('::')

            current_level = tree
            for part in parts:
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]

            # 在叶子节点存储类别信息
            if not current_level:
                current_level['_category'] = {
                    'id': category.id,
                    'display_name': category.display_name,
                    'description': category.description
                }

        return tree


# =============================================================================
# 8. 统一标签系统
# =============================================================================

class UnifiedTag(models.Model):
    """
    统一标签表 - 合并手工标签和PubChem标签
    """
    id = models.AutoField(primary_key=True)
    tag_name = models.CharField(max_length=255, unique=True, verbose_name="标签名称")
    tag_category = models.CharField(max_length=100, blank=True, null=True, verbose_name="标签类别")

    # 来源信息
    SOURCE_CHOICES = [
        ('manual', '手工标签'),
        ('pubchem_api', 'PubChem API'),
        ('ai', 'AI分析'),
    ]
    source = models.CharField(
        max_length=50,
        choices=SOURCE_CHOICES,
        default='manual',
        verbose_name="来源"
    )

    # 原始标签信息（用于追溯）
    original_tag_id = models.IntegerField(null=True, blank=True, verbose_name="原始标签ID")
    original_source_type = models.CharField(
        max_length=20,
        choices=[('manual_tag', '手工标签'), ('pubchem_tag', 'PubChem标签')],
        null=True,
        blank=True,
        verbose_name="原始标签类型"
    )

    # PubChem特定字段（如果适用）
    pubchem_classification = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="PubChem分类"
    )
    mesh_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="MeSH ID"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'unified_tags'
        verbose_name = '统一标签'
        verbose_name_plural = '统一标签'
        indexes = [
            models.Index(fields=['tag_name']),
            models.Index(fields=['tag_category']),
            models.Index(fields=['source']),
        ]

    def __str__(self):
        source_display = dict(self.SOURCE_CHOICES).get(self.source, self.source)
        return f"{self.tag_name} ({source_display})"


class UnifiedProductTagMapping(models.Model):
    """
    统一产品-标签关联表
    """
    id = models.AutoField(primary_key=True)
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        db_column='product_id',
        verbose_name="产品"
    )
    tag = models.ForeignKey(
        UnifiedTag,
        on_delete=models.CASCADE,
        db_column='tag_id',
        verbose_name="标签"
    )

    # 置信度评分
    confidence_score = models.FloatField(default=1.0, verbose_name="置信度")

    # 原始关联信息（用于追溯）
    original_mapping_id = models.IntegerField(null=True, blank=True, verbose_name="原始关联ID")
    original_source_type = models.CharField(
        max_length=20,
        choices=[('manual_mapping', '手工关联'), ('pubchem_mapping', 'PubChem关联')],
        null=True,
        blank=True,
        verbose_name="原始关联类型"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'unified_product_tag_mapping'
        verbose_name = '统一产品标签关联'
        verbose_name_plural = '统一产品标签关联'
        unique_together = (('product', 'tag'),)
        indexes = [
            models.Index(fields=['product', 'tag']),
            models.Index(fields=['confidence_score']),
        ]

    def __str__(self):
        return f"{self.product.product_name} - {self.tag.tag_name} ({self.confidence_score})"