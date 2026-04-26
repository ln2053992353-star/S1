# scripts/build_embedding_text.py
# 注意：建议使用 ProductEmbedding.update_embedding_text() 方法
# 此函数保留用于向后兼容

def build_product_text(product):
    """
    构建产品嵌入文本（兼容旧版本）
    """
    # 获取标签信息
    tags_info = []
    for tag in product.tags.all():
        tag_text = tag.tag_name
        if tag.tag_category:
            tag_text = f"{tag_text} ({tag.tag_category})"
        tags_info.append(tag_text)
    tags_str = "; ".join(tags_info) if tags_info else ""

    # 构建文本（与 ProductEmbedding.update_embedding_text() 保持一致）
    parts = []

    product_name = product.product_name or ""
    description = product.description or ""
    grna_info = product.grna_map or ""

    if product_name:
        parts.append(f"Product: {product_name}")
    if description:
        desc_preview = description[:500] + "..." if len(description) > 500 else description
        parts.append(f"Description: {desc_preview}")
    if grna_info:
        parts.append(f"gRNA: {grna_info}")
    if tags_str:
        parts.append(f"Tags: {tags_str}")

    text = "\n".join(parts)
    return text if text.strip() else product_name or "Unknown product"
