#!/usr/bin/env python
"""
数据库导出为Excel工具
将关键表导出为Excel文件，每个表一个工作表
"""
import os
import sys
import pandas as pd
from datetime import datetime
from typing import List, Optional

# 动态检测MySQL客户端
def detect_mysql_client():
    """检测可用的MySQL客户端"""
    try:
        import mysql.connector
        return 'mysql-connector'
    except ImportError:
        try:
            import pymysql
            pymysql.install_as_MySQLdb()
            return 'pymysql'
        except ImportError:
            return None

def load_db_config():
    """加载数据库配置"""
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'demo1'),
        'user': os.getenv('DB_USER', '13892277786'),
        'password': os.getenv('DB_PASSWORD', 'ln20050924'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'charset': 'utf8mb4'
    }

class DatabaseExcelExporter:
    """数据库Excel导出器"""

    def __init__(self, output_file=None):
        self.db_config = load_db_config()
        self.mysql_client = detect_mysql_client()
        self.connection = None

        # 输出文件
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"database_export_{timestamp}.xlsx"
        self.output_file = output_file

        print(f"数据库Excel导出工具")
        print(f"输出文件: {self.output_file}")
        print(f"MySQL客户端: {self.mysql_client}")
        print("-" * 60)

    def connect_to_database(self) -> bool:
        """连接到MySQL数据库"""
        if not self.mysql_client:
            print("错误: 未安装MySQL客户端库，请安装mysql-connector-python或pymysql")
            return False

        try:
            if self.mysql_client == 'mysql-connector':
                import mysql.connector
                self.connection = mysql.connector.connect(**self.db_config)
                print(f"成功连接到数据库: {self.db_config['database']} (使用mysql-connector-python)")
                return True
            elif self.mysql_client == 'pymysql':
                import pymysql
                conn_config = self.db_config.copy()
                if 'charset' in conn_config:
                    conn_config['charset'] = conn_config.pop('charset')
                self.connection = pymysql.connect(**conn_config)
                print(f"成功连接到数据库: {self.db_config['database']} (使用PyMySQL)")
                return True
            else:
                print(f"错误: 不支持的MySQL客户端: {self.mysql_client}")
                return False
        except Exception as e:
            print(f"数据库连接错误: {e}")
            return False

    def disconnect_from_database(self):
        """断开数据库连接"""
        if self.connection:
            self.connection.close()
            print("数据库连接已关闭")

    def read_table_to_dataframe(self, table_name: str, columns=None, where_clause=None) -> Optional[pd.DataFrame]:
        """
        读取表到Pandas DataFrame

        Args:
            table_name: 表名
            columns: 要导出的列列表（None表示所有列）
            where_clause: WHERE子句（不含WHERE关键字）

        Returns:
            DataFrame或None
        """
        if not self.connection:
            print(f"错误: 数据库未连接")
            return None

        try:
            # 构建查询
            if columns:
                columns_str = ', '.join([f'`{col}`' for col in columns])
            else:
                columns_str = '*'

            query = f"SELECT {columns_str} FROM {table_name}"
            if where_clause:
                query += f" WHERE {where_clause}"

            # 使用pandas读取SQL
            df = pd.read_sql(query, self.connection)
            return df

        except Exception as e:
            print(f"读取表 {table_name} 失败: {e}")
            return None

    def get_table_info(self, table_name: str) -> dict:
        """获取表信息"""
        if not self.connection:
            return {}

        try:
            # 获取表结构
            query = f"SHOW COLUMNS FROM {table_name}"
            columns_df = pd.read_sql(query, self.connection)

            # 获取行数
            count_query = f"SELECT COUNT(*) as count FROM {table_name}"
            count_df = pd.read_sql(count_query, self.connection)
            row_count = count_df.iloc[0]['count'] if not count_df.empty else 0

            return {
                'table_name': table_name,
                'row_count': row_count,
                'columns': columns_df.to_dict('records'),
                'column_count': len(columns_df)
            }

        except Exception as e:
            print(f"获取表 {table_name} 信息失败: {e}")
            return {}

    def export_to_excel(self, table_list=None, max_rows_per_sheet=1000000):
        """
        导出表到Excel文件

        Args:
            table_list: 要导出的表列表，None表示使用默认表
            max_rows_per_sheet: 每个工作表最大行数（Excel限制）
        """
        if not self.connect_to_database():
            return False

        try:
            # 默认导出关键表
            if table_list is None:
                table_list = [
                    'products',
                    'pubchem_tags',
                    'product_pubchem_tags',
                    'yeast_pubchem_data',
                    'tags',
                    'product_tags',
                    'tag_hierarchies',
                    'tag_category_system'
                ]

            print(f"导出 {len(table_list)} 个表到Excel:")
            print("-" * 60)

            # 收集表信息
            table_info_list = []
            for table_name in table_list:
                info = self.get_table_info(table_name)
                if info:
                    table_info_list.append(info)
                    print(f"  {table_name}: {info['row_count']} 行, {info['column_count']} 列")

            # 创建Excel写入器
            with pd.ExcelWriter(self.output_file, engine='openpyxl') as writer:
                # 1. 创建表信息工作表
                info_data = []
                for info in table_info_list:
                    info_data.append({
                        '表名': info['table_name'],
                        '行数': info['row_count'],
                        '列数': info['column_count'],
                        '备注': ''
                    })

                if info_data:
                    info_df = pd.DataFrame(info_data)
                    info_df.to_excel(writer, sheet_name='表信息', index=False)
                    print(f"  表信息 -> '表信息'工作表")

                # 2. 导出每个表的数据
                for table_name in table_list:
                    print(f"  导出表: {table_name}...", end='')

                    # 读取数据
                    df = self.read_table_to_dataframe(table_name)
                    if df is not None:
                        # 检查行数，如果超过限制则拆分
                        if len(df) > max_rows_per_sheet:
                            print(f"警告: {table_name} 有 {len(df)} 行，超过限制 {max_rows_per_sheet} 行")
                            # 拆分工作表
                            num_sheets = (len(df) + max_rows_per_sheet - 1) // max_rows_per_sheet
                            for i in range(num_sheets):
                                start_idx = i * max_rows_per_sheet
                                end_idx = min((i + 1) * max_rows_per_sheet, len(df))
                                sheet_df = df.iloc[start_idx:end_idx]
                                sheet_name = f"{table_name}_{i+1}" if num_sheets > 1 else table_name
                                sheet_name = sheet_name[:31]  # Excel工作表名最大31字符
                                sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
                                print(f"    -> '{sheet_name}' 工作表 ({len(sheet_df)} 行)")
                        else:
                            # 单个工作表
                            sheet_name = table_name[:31]  # Excel工作表名最大31字符
                            df.to_excel(writer, sheet_name=sheet_name, index=False)
                            print(f" -> '{sheet_name}' 工作表 ({len(df)} 行)")
                    else:
                        print(f" 失败")

                # 3. 创建列信息工作表
                columns_data = []
                for info in table_info_list:
                    for col in info['columns']:
                        columns_data.append({
                            '表名': info['table_name'],
                            '列名': col.get('Field', col.get('field', '')),
                            '数据类型': col.get('Type', col.get('type', '')),
                            '允许NULL': col.get('Null', col.get('null', '')),
                            '键类型': col.get('Key', col.get('key', '')),
                            '默认值': col.get('Default', col.get('default', ''))
                        })

                if columns_data:
                    columns_df = pd.DataFrame(columns_data)
                    columns_df.to_excel(writer, sheet_name='列信息', index=False)
                    print(f"  列信息 -> '列信息'工作表")

            print("\n" + "=" * 60)
            print("导出完成!")
            print(f"Excel文件: {self.output_file}")
            print(f"文件大小: {os.path.getsize(self.output_file) / 1024:.2f} KB")

            # 显示工作表列表
            print("\nExcel文件中的工作表:")
            excel_file = pd.ExcelFile(self.output_file)
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                print(f"  '{sheet_name}': {len(df)} 行, {len(df.columns)} 列")

            return True

        except Exception as e:
            print(f"导出过程中出错: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.disconnect_from_database()

    def export_selected_tables(self, tables_with_columns=None):
        """
        导出选定的表和列

        Args:
            tables_with_columns: 字典，键为表名，值为列列表
                例如: {'products': ['product_id', 'product_name'], 'tags': ['tag_id', 'tag_name']}
        """
        if not self.connect_to_database():
            return False

        try:
            if tables_with_columns is None:
                return self.export_to_excel()

            print(f"导出 {len(tables_with_columns)} 个选定的表:")
            print("-" * 60)

            output_file = self.output_file.replace('.xlsx', '_selected.xlsx')
            if output_file == self.output_file:
                output_file = self.output_file.replace('.xlsx', '_custom.xlsx')

            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                for table_name, columns in tables_with_columns.items():
                    print(f"  导出表: {table_name} ({len(columns)} 列)...", end='')

                    df = self.read_table_to_dataframe(table_name, columns)
                    if df is not None:
                        sheet_name = table_name[:31]
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        print(f" -> '{sheet_name}' 工作表 ({len(df)} 行)")
                    else:
                        print(f" 失败")

            print("\n" + "=" * 60)
            print("导出完成!")
            print(f"Excel文件: {output_file}")
            return True

        except Exception as e:
            print(f"导出过程中出错: {e}")
            return False
        finally:
            self.disconnect_from_database()

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='数据库导出为Excel工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 导出所有关键表到Excel
  python export_to_excel.py

  # 指定输出文件名
  python export_to_excel.py --output demo1_database.xlsx

  # 只导出指定的表
  python export_to_excel.py --table products tags pubchem_tags

  # 导出选定的列
  python export_to_excel.py --custom-table "products:product_id,product_name" "pubchem_tags:tag_id,tag_name"
        """
    )

    parser.add_argument('--output', '-o', type=str, default=None,
                       help='输出Excel文件名，默认: database_export_YYYYMMDD_HHMMSS.xlsx')
    parser.add_argument('--table', '-t', type=str, nargs='+',
                       help='指定要导出的表名，多个表用空格分隔')
    parser.add_argument('--custom-table', type=str, nargs='+',
                       help='指定表和列，格式: "表名:列1,列2,列3"')

    args = parser.parse_args()

    # 创建导出器
    exporter = DatabaseExcelExporter(output_file=args.output)

    # 处理自定义表列
    if args.custom_table:
        tables_with_columns = {}
        for item in args.custom_table:
            if ':' in item:
                table_name, columns_str = item.split(':', 1)
                columns = [col.strip() for col in columns_str.split(',')]
                tables_with_columns[table_name.strip()] = columns
            else:
                tables_with_columns[item.strip()] = None

        success = exporter.export_selected_tables(tables_with_columns)
    elif args.table:
        success = exporter.export_to_excel(table_list=args.table)
    else:
        success = exporter.export_to_excel()

    # 返回退出码
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()