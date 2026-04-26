from django.contrib import admin
from .models import Product, Tag, ProductEmbedding, ProductSource  # <--- 记得导入新模型
from sentence_transformers import SentenceTransformer
import json


# 1. 定义文献来源的内联编辑器
class ProductSourceInline(admin.TabularInline):
    model = ProductSource
    extra = 1  # 默认多显示一行空的，方便添加
    verbose_name = "文献 DOI"
    verbose_name_plural = "关联的文献 DOI (支持多个)"


# 2. 定义 Embedding 的内联编辑器 (保持你之前的逻辑)
class ProductEmbeddingInline(admin.StackedInline):
    model = ProductEmbedding
    can_delete = False
    verbose_name_plural = 'AI 分析数据 (向量/描述)'
    fields = ('function', 'embedding_text', 'tags_text', 'grna', 'iupac_name', 'pubchem_description', 'source_database', 'updated_at')
    readonly_fields = ('updated_at',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'product_name')
    search_fields = ('product_name',)

    # 🔥 关键：把 Embedding 和 Source 都嵌入到 Product 页面里
    inlines = [ProductSourceInline, ProductEmbeddingInline]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('tag_id', 'tag_name')


@admin.register(ProductEmbedding)
class ProductEmbeddingAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'source_database', 'updated_at')
    list_filter = ('source_database', 'updated_at')
    search_fields = ('product__product_name', 'function', 'tags_text', 'iupac_name')
    readonly_fields = ('embedding_text', 'updated_at', 'created_at')

    fieldsets = (
        ('产品关联', {
            'fields': ('product',)
        }),
        ('核心功能描述', {
            'fields': ('function', 'grna', 'tags_text')
        }),
        ('PubChem 数据', {
            'fields': ('iupac_name', 'pubchem_description'),
            'classes': ('collapse',)
        }),
        ('来源与向量', {
            'fields': ('source_database', 'embedding_text', 'vector', 'model_name', 'dim')
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

