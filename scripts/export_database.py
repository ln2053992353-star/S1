#!/usr/bin/env python
"""
数据库导出工具
将关键表导出为CSV格式，方便查看数据
"""
import os
import sys
import csv
import time
from datetime import datetime
from typing import List, Dict, Any

# 动态检测MySQL客户端
def detect_mysql_client():
    """检测可用的MySQL客户端"""
    try:
        import mysql.connector
        return 'mysql-connector'
    except ImportError:
        try:
            import pymysql
            # 将pymysql配置为MySQLdb兼容层
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

class DatabaseExporter:
    """数据库导出器"""

    def __init__(self, output_dir=None):
        self.db_config = load_db_config()
        self.mysql_client = detect_mysql_client()
        self.connection = None

        # 输出目录
        if output_dir is None:
            output_dir = f"database_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.output_dir = output_dir

        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)

        print(f"数据库导出工具")
        print(f"输出目录: {self.output_dir}")
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
                # PyMySQL连接参数略有不同
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

    def export_table_to_csv(self, table_name: str, columns=None, where_clause=None) -> str:
        """
        导出表为CSV文件

        Args:
            table_name: 表名
            columns: 要导出的列列表（None表示所有列）
            where_clause: WHERE子句（不含WHERE关键字）

        Returns:
            导出的CSV文件路径
        """
        if not self.connection:
            print(f"错误: 数据库未连接")
            return None

        cursor = None
        output_file = os.path.join(self.output_dir, f"{table_name}.csv")

        try:
            # 创建游标
            if self.mysql_client == 'mysql-connector':
                cursor = self.connection.cursor(dictionary=True)
            elif self.mysql_client == 'pymysql':
                import pymysql.cursors
                cursor = self.connection.cursor(pymysql.cursors.DictCursor)

            # 构建查询
            if columns:
                columns_str = ', '.join([f'`{col}`' for col in columns])
            else:
                # 获取所有列名
                cursor.execute(f"SHOW COLUMNS FROM {table_name}")
                columns = [row['Field'] for row in cursor.fetchall()]
                columns_str = '*'

            query = f"SELECT {columns_str} FROM {table_name}"
            if where_clause:
                query += f" WHERE {where_clause}"

            # 执行查询
            cursor.execute(query)
            rows = cursor.fetchall()

            # 写入CSV
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
                if rows:
                    fieldnames = list(rows[0].keys())
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)

                print(f"  导出 {table_name}: {len(rows)} 行 -> {output_file}")
                return output_file

        except Exception as e:
            print(f"  导出 {table_name} 失败: {e}")
            return None
        finally:
            if cursor:
                cursor.close()

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取表信息（列名和数据类型）"""
        if not self.connection:
            return {}

        cursor = None
        try:
            if self.mysql_client == 'mysql-connector':
                cursor = self.connection.cursor(dictionary=True)
            elif self.mysql_client == 'pymysql':
                import pymysql.cursors
                cursor = self.connection.cursor(pymysql.cursors.DictCursor)

            cursor.execute(f"SHOW COLUMNS FROM {table_name}")
            columns = cursor.fetchall()

            # 转换为更易读的格式
            column_info = []
            for col in columns:
                column_info.append({
                    'field': col['Field'],
                    'type': col['Type'],
                    'null': col['Null'],
                    'key': col['Key'],
                    'default': col['Default'],
                    'extra': col.get('Extra', '')
                })

            return {
                'table_name': table_name,
                'columns': column_info,
                'count': self.get_table_count(table_name)
            }

        except Exception as e:
            print(f"获取表 {table_name} 信息失败: {e}")
            return {}
        finally:
            if cursor:
                cursor.close()

    def get_table_count(self, table_name: str) -> int:
        """获取表行数"""
        if not self.connection:
            return 0

        cursor = None
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            print(f"获取表 {table_name} 行数失败: {e}")
            return 0
        finally:
            if cursor:
                cursor.close()

    def export_all_tables(self, table_list=None):
        """导出所有指定的表"""
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

            print(f"导出 {len(table_list)} 个表:")
            print("-" * 60)

            # 先收集表信息
            table_info = []
            for table_name in table_list:
                info = self.get_table_info(table_name)
                if info:
                    table_info.append(info)
                    print(f"  {table_name}: {info['count']} 行, {len(info['columns'])} 列")

            # 创建表信息汇总文件
            info_file = os.path.join(self.output_dir, "table_info.txt")
            with open(info_file, 'w', encoding='utf-8') as f:
                f.write("数据库表信息汇总\n")
                f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"数据库: {self.db_config['database']}\n")
                f.write("=" * 60 + "\n\n")

                for info in table_info:
                    f.write(f"表: {info['table_name']} ({info['count']} 行)\n")
                    f.write("-" * 40 + "\n")
                    for col in info['columns']:
                        null_str = "NULL" if col['null'] == 'YES' else "NOT NULL"
                        default_str = f"DEFAULT {col['default']}" if col['default'] is not None else ""
                        key_str = f"[{col['key']}]" if col['key'] else ""
                        f.write(f"  {col['field']:30s} {col['type']:20s} {null_str:12s} {default_str:20s} {key_str}\n")
                    f.write("\n")

            print(f"  表信息已保存到: {info_file}")

            # 导出每个表的数据
            print("\n导出表数据:")
            print("-" * 60)

            exported_files = []
            for table_name in table_list:
                csv_file = self.export_table_to_csv(table_name)
                if csv_file:
                    exported_files.append(csv_file)

            print("\n" + "=" * 60)
            print("导出完成!")
            print(f"导出目录: {self.output_dir}")
            print(f"导出的文件:")
            for file in exported_files:
                print(f"  {os.path.basename(file)}")
            print(f"表信息文件: table_info.txt")

            return True

        except Exception as e:
            print(f"导出过程中出错: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.disconnect_from_database()

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='数据库导出工具')
    parser.add_argument('--output-dir', '-o', type=str, default=None,
                       help='输出目录，默认: database_export_YYYYMMDD_HHMMSS')
    parser.add_argument('--table', '-t', type=str, nargs='+',
                       help='指定要导出的表名，多个表用空格分隔')

    args = parser.parse_args()

    # 创建导出器
    exporter = DatabaseExporter(output_dir=args.output_dir)

    # 导出表
    success = exporter.export_all_tables(args.table)

    # 返回退出码
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()