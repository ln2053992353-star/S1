#!/usr/bin/env python
"""
创建标签层次结构系统迁移脚本
"""
import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_search_project.settings")
django.setup()

from django.core.management import call_command

def create_migration():
    """创建迁移文件"""
    print("创建标签层次结构系统迁移...")

    try:
        # 生成迁移文件
        call_command('makemigrations', 'search_engine', interactive=False)
        print("迁移文件创建成功")

        # 显示新创建的迁移
        print("\n最新的迁移文件:")
        migrations_dir = os.path.join(BASE_DIR, 'search_engine', 'migrations')
        migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith('.py') and f.startswith('0')])

        if migration_files:
            latest = migration_files[-1]
            print(f"  {latest}")

            # 显示迁移内容
            migration_path = os.path.join(migrations_dir, latest)
            with open(migration_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print("\n迁移内容预览:")
                lines = content.split('\n')
                for i, line in enumerate(lines[:30]):  # 显示前30行
                    print(f"  {line}")

    except Exception as e:
        print(f"创建迁移失败: {e}")
        import traceback
        traceback.print_exc()

def show_migration_plan():
    """显示迁移计划"""
    print("=" * 60)
    print("标签层次结构系统迁移计划")
    print("=" * 60)

    print("\n将创建以下新表:")
    print("1. tag_hierarchies - 标签层次关系表")
    print("   字段: parent_tag (通用外键), child_tag (通用外键), relationship_type, confidence, source, level")
    print("   索引: parent_tag, child_tag, relationship_type, level")
    print("   唯一约束: (parent_tag, child_tag)")

    print("\n2. tag_category_system - 标签分类系统表")
    print("   字段: category_path, display_name, level, parent_path, description, tag_type, example_tags, usage_count")
    print("   索引: category_path, level, tag_type")
    print("   唯一约束: category_path")

    print("\n将扩展以下现有表:")
    print("1. Tag 模型 - 已有字段不变")
    print("2. PubChemTag 模型 - 已有字段不变")

    print("\n数据迁移:")
    print("1. 初始化预定义分类体系")
    print("2. 基于现有标签构建层次关系")

    print("\n预计影响:")
    print("✓ 数据库: 增加2个新表")
    print("✓ 性能: 新增索引提高查询效率")
    print("✓ 功能: 支持标签层次查询和智能分类")

def run_migration():
    """运行迁移"""
    print("\n运行数据库迁移...")

    try:
        call_command('migrate', 'search_engine', interactive=False)
        print("迁移成功完成")
    except Exception as e:
        print(f"迁移失败: {e}")
        import traceback
        traceback.print_exc()

def initialize_category_system():
    """初始化分类系统"""
    print("\n初始化预定义分类系统...")

    from django.apps import apps
    from search_engine.models import TagCategorySystem

    # 预定义分类体系
    categories = [
        # 实验技术
        {
            'category_path': '实验技术',
            'display_name': '实验技术',
            'level': 1,
            'parent_path': None,
            'description': '实验室研究方法和操作技术',
            'tag_type': 'general',
            'example_tags': 'PCR, Western blot, Cell culture, Flow cytometry'
        },
        {
            'category_path': '实验技术::分子生物学技术',
            'display_name': '分子生物学技术',
            'level': 2,
            'parent_path': '实验技术',
            'description': '涉及DNA、RNA、蛋白质等分子水平的研究技术',
            'tag_type': 'general',
            'example_tags': 'PCR, DNA sequencing, Gene cloning, CRISPR'
        },
        {
            'category_path': '实验技术::细胞生物学技术',
            'display_name': '细胞生物学技术',
            'level': 2,
            'parent_path': '实验技术',
            'description': '细胞培养、操作和分析技术',
            'tag_type': 'general',
            'example_tags': 'Cell culture, Transfection, Immunofluorescence, Flow cytometry'
        },
        {
            'category_path': '实验技术::分析检测技术',
            'display_name': '分析检测技术',
            'level': 2,
            'parent_path': '实验技术',
            'description': '化学分析和生物检测技术',
            'tag_type': 'general',
            'example_tags': 'HPLC, Mass spectrometry, ELISA, Spectroscopy'
        },

        # 化合物类别
        {
            'category_path': '化合物类别',
            'display_name': '化合物类别',
            'level': 1,
            'parent_path': None,
            'description': '化学物质的分类',
            'tag_type': 'both',
            'example_tags': 'Organic compounds, Lipids, Amino acids, Nucleic acids'
        },
        {
            'category_path': '化合物类别::有机化合物',
            'display_name': '有机化合物',
            'level': 2,
            'parent_path': '化合物类别',
            'description': '含碳化合物及其衍生物',
            'tag_type': 'both',
            'example_tags': 'Benzenoids, Alkaloids, Terpenoids, Flavonoids'
        },
        {
            'category_path': '化合物类别::生物大分子',
            'display_name': '生物大分子',
            'level': 2,
            'parent_path': '化合物类别',
            'description': '生物体内的大分子化合物',
            'tag_type': 'both',
            'example_tags': 'Proteins, Nucleic acids, Polysaccharides, Lipids'
        },
        {
            'category_path': '化合物类别::无机化合物',
            'display_name': '无机化合物',
            'level': 2,
            'parent_path': '化合物类别',
            'description': '不含碳的化合物',
            'tag_type': 'both',
            'example_tags': 'Salts, Acids, Bases, Metal ions'
        },

        # 生物过程
        {
            'category_path': '生物过程',
            'display_name': '生物过程',
            'level': 1,
            'parent_path': None,
            'description': '生物体内发生的各种过程',
            'tag_type': 'general',
            'example_tags': 'Metabolism, Signaling, Gene expression, Cell cycle'
        },
        {
            'category_path': '生物过程::代谢过程',
            'display_name': '代谢过程',
            'level': 2,
            'parent_path': '生物过程',
            'description': '物质和能量的转化过程',
            'tag_type': 'general',
            'example_tags': 'Glycolysis, Krebs cycle, Photosynthesis, Fatty acid metabolism'
        },
        {
            'category_path': '生物过程::细胞过程',
            'display_name': '细胞过程',
            'level': 2,
            'parent_path': '生物过程',
            'description': '细胞内发生的过程',
            'tag_type': 'general',
            'example_tags': 'Cell division, Apoptosis, Cell signaling, Cell migration'
        },
        {
            'category_path': '生物过程::遗传过程',
            'display_name': '遗传过程',
            'level': 2,
            'parent_path': '生物过程',
            'description': '遗传信息的传递和表达',
            'tag_type': 'general',
            'example_tags': 'DNA replication, Transcription, Translation, Gene regulation'
        },

        # 疾病相关
        {
            'category_path': '疾病相关',
            'display_name': '疾病相关',
            'level': 1,
            'parent_path': None,
            'description': '与疾病相关的标签',
            'tag_type': 'both',
            'example_tags': 'Cancer, Diabetes, Alzheimer, Inflammation'
        },
        {
            'category_path': '疾病相关::癌症相关',
            'display_name': '癌症相关',
            'level': 2,
            'parent_path': '疾病相关',
            'description': '与癌症相关的标签',
            'tag_type': 'both',
            'example_tags': 'Tumor, Carcinoma, Leukemia, Metastasis'
        },
        {
            'category_path': '疾病相关::神经疾病',
            'display_name': '神经疾病',
            'level': 2,
            'parent_path': '疾病相关',
            'description': '神经系统疾病相关',
            'tag_type': 'both',
            'example_tags': 'Alzheimer, Parkinson, Depression, Autism'
        },
        {
            'category_path': '疾病相关::代谢疾病',
            'display_name': '代谢疾病',
            'level': 2,
            'parent_path': '疾病相关',
            'description': '代谢相关疾病',
            'tag_type': 'both',
            'example_tags': 'Diabetes, Obesity, Hypertension, Hyperlipidemia'
        },

        # 应用领域
        {
            'category_path': '应用领域',
            'display_name': '应用领域',
            'level': 1,
            'parent_path': None,
            'description': '技术或产品的应用领域',
            'tag_type': 'general',
            'example_tags': 'Drug discovery, Agriculture, Environmental science, Diagnostics'
        },
        {
            'category_path': '应用领域::药物研发',
            'display_name': '药物研发',
            'level': 2,
            'parent_path': '应用领域',
            'description': '药物发现和开发',
            'tag_type': 'general',
            'example_tags': 'Drug screening, Pharmacology, Toxicology, Clinical trials'
        },
        {
            'category_path': '应用领域::农业生物',
            'display_name': '农业生物',
            'level': 2,
            'parent_path': '应用领域',
            'description': '农业和生物技术应用',
            'tag_type': 'general',
            'example_tags': 'GMO crops, Pesticides, Fertilizers, Plant breeding'
        },
        {
            'category_path': '应用领域::环境科学',
            'display_name': '环境科学',
            'level': 2,
            'parent_path': '应用领域',
            'description': '环境保护和监测',
            'tag_type': 'general',
            'example_tags': 'Bioremediation, Pollution monitoring, Environmental protection, Ecology'
        },

        # PubChem特定分类
        {
            'category_path': 'PubChem分类',
            'display_name': 'PubChem分类',
            'level': 1,
            'parent_path': None,
            'description': 'PubChem数据库的标准分类',
            'tag_type': 'pubchem',
            'example_tags': 'Organic compounds, Lipids and lipid-like molecules, Benzenoids'
        },
        {
            'category_path': 'PubChem分类::化学分类',
            'display_name': '化学分类',
            'level': 2,
            'parent_path': 'PubChem分类',
            'description': '基于化学结构的分类',
            'tag_type': 'pubchem',
            'example_tags': 'Superclass, Class, Subclass'
        },
        {
            'category_path': 'PubChem分类::MeSH术语',
            'display_name': 'MeSH术语',
            'level': 2,
            'parent_path': 'PubChem分类',
            'description': '医学主题词分类',
            'tag_type': 'pubchem',
            'example_tags': 'Phenols, Antioxidants, Anti-inflammatory agents'
        },
    ]

    created_count = 0
    updated_count = 0

    for category_data in categories:
        category_path = category_data['category_path']

        obj, created = TagCategorySystem.objects.update_or_create(
            category_path=category_path,
            defaults=category_data
        )

        if created:
            created_count += 1
            print(f"  创建: {category_path}")
        else:
            updated_count += 1
            print(f"  更新: {category_path}")

    print(f"\n分类系统初始化完成:")
    print(f"  创建: {created_count} 个分类")
    print(f"  更新: {updated_count} 个分类")

    return created_count + updated_count

def main():
    """主函数"""
    print("标签层次结构系统迁移工具")
    print("=" * 50)

    print("选项:")
    print("1. 显示迁移计划")
    print("2. 创建迁移文件")
    print("3. 运行迁移")
    print("4. 初始化分类系统")
    print("5. 完整流程 (1→2→3→4)")

    choice = input("\n请选择 (1-5): ").strip()

    if choice == '1':
        show_migration_plan()

    elif choice == '2':
        create_migration()

    elif choice == '3':
        run_migration()

    elif choice == '4':
        initialize_category_system()

    elif choice == '5':
        show_migration_plan()
        input("\n按Enter键继续创建迁移文件...")
        create_migration()
        input("\n按Enter键继续运行迁移...")
        run_migration()
        input("\n按Enter键继续初始化分类系统...")
        initialize_category_system()
        print("\n✅ 完整流程完成!")

    else:
        print("无效选择")

if __name__ == "__main__":
    main()