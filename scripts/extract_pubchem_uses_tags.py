#!/usr/bin/env python
"""
PubChem用途标签提取与物质名称标准化脚本

功能：
1. 从MySQL数据库的products表读取化合物名称
2. 通过PubChem API获取化合物的CID
3. 使用PUG View API提取"Use and Manufacturing"分类下的"Uses"标签
4. 获取标准化名称（IUPAC名称或Preferred Name）
5. 将标签存入PubChemTag表，类别为'use_and_manufacturing'
6. 建立产品-标签关联并更新CID信息

安全特性：
- 遵守PubChem API频率限制（每秒不超过5次请求）
- 所有SQL查询使用参数化查询防止注入
- 完善的异常处理，单个化合物失败不影响整体处理
- 资源正确管理，连接和游标安全关闭
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
import requests
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# MySQL连接器将在PubChemUsesExtractor类中动态检测和导入

# 配置日志
def setup_logging(log_level=logging.INFO, log_file=None):
    """配置日志记录"""
    logger = logging.getLogger('pubchem_uses_extractor')
    logger.setLevel(log_level)

    # 清除现有处理器
    if logger.hasHandlers():
        logger.handlers.clear()

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件处理器（如果指定）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger

# 数据类定义
@dataclass
class CompoundInfo:
    """化合物信息"""
    product_id: int
    product_name: str
    existing_cid: Optional[int] = None

@dataclass
class ProcessingResult:
    """处理结果"""
    product_id: int
    product_name: str
    cid: Optional[int] = None
    standardized_name: Optional[str] = None
    uses_tags: Optional[str] = None
    success: bool = False
    error_message: Optional[str] = None
    processing_time: float = 0.0

class PubChemUsesExtractor:
    """PubChem用途标签提取器"""

    def __init__(self, db_config=None, api_delay=0.3, max_retries=3,
                 proxy=None, log_level=logging.INFO):
        """
        初始化提取器

        Args:
            db_config: 数据库连接配置字典
            api_delay: API调用延迟（秒），默认0.3秒满足PubChem速率限制
            max_retries: 最大重试次数
            proxy: 代理配置
            log_level: 日志级别
        """
        self.db_config = db_config or self._load_default_db_config()
        self.api_delay = max(api_delay, 0.2)  # 最低0.2秒，满足每秒5次限制
        self.max_retries = max_retries
        self.proxy = {'http': proxy, 'https': proxy} if proxy else None
        self.logger = setup_logging(log_level)

        # 检测MySQL客户端
        self.mysql_client = None
        self.mysql_available = False
        self._detect_mysql_client()

        # HTTP会话
        self.session = requests.Session()
        if self.proxy:
            self.session.proxies.update(self.proxy)

        # 数据库连接
        self.connection = None

        # 统计信息
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': None,
            'end_time': None
        }

    def _detect_mysql_client(self):
        """检测可用的MySQL客户端"""
        try:
            # 优先尝试mysql-connector-python
            import mysql.connector
            self.mysql_client = 'mysql-connector'
            self.mysql_available = True
            self.logger.info("检测到mysql-connector-python")
        except ImportError:
            try:
                # 备选：PyMySQL
                import pymysql
                # 将pymysql配置为MySQLdb兼容层（Django使用的方式）
                pymysql.install_as_MySQLdb()
                self.mysql_client = 'pymysql'
                self.mysql_available = True
                self.logger.info("检测到PyMySQL")
            except ImportError:
                self.mysql_client = None
                self.mysql_available = False
                self.logger.warning("未安装MySQL客户端库，请安装mysql-connector-python或pymysql")

    def _load_default_db_config(self) -> Dict[str, Any]:
        """加载默认数据库配置（从settings.py）"""
        # 尝试从环境变量或默认值加载
        config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'database': os.getenv('DB_NAME', 'demo1'),
            'user': os.getenv('DB_USER', '13892277786'),
            'password': os.getenv('DB_PASSWORD', 'ln20050924'),
            'port': int(os.getenv('DB_PORT', '3306')),
            'charset': 'utf8mb4'
        }
        return config

    def connect_to_database(self) -> bool:
        """连接到MySQL数据库"""
        if not self.mysql_available:
            self.logger.error("MySQL客户端库未安装，请安装mysql-connector-python或pymysql")
            return False

        try:
            if self.mysql_client == 'mysql-connector':
                import mysql.connector
                from mysql.connector import Error as MySQL_Error
                self.connection = mysql.connector.connect(**self.db_config)
                if self.connection.is_connected():
                    self.logger.info(f"成功连接到数据库: {self.db_config['database']} (使用mysql-connector-python)")
                    return True
            elif self.mysql_client == 'pymysql':
                import pymysql
                from pymysql import Error as MySQL_Error
                # PyMySQL连接参数略有不同
                conn_config = self.db_config.copy()
                # PyMySQL使用charset而不是character_set
                if 'charset' in conn_config:
                    conn_config['charset'] = conn_config.pop('charset')
                self.connection = pymysql.connect(**conn_config)
                self.logger.info(f"成功连接到数据库: {self.db_config['database']} (使用PyMySQL)")
                return True
            else:
                self.logger.error(f"未知的MySQL客户端: {self.mysql_client}")
                return False

            return False

        except Exception as e:
            self.logger.error(f"数据库连接错误: {e}")
            return False

    def _is_connected(self) -> bool:
        """检查数据库连接是否有效"""
        if not self.connection:
            return False

        if self.mysql_client == 'mysql-connector':
            return self.connection.is_connected()
        elif self.mysql_client == 'pymysql':
            # PyMySQL: 检查连接是否打开
            try:
                # 尝试执行一个简单查询来检查连接
                cursor = self.connection.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                return True
            except Exception:
                return False
        return False

    def disconnect_from_database(self):
        """断开数据库连接"""
        if self.connection and self._is_connected():
            self.connection.close()
            self.logger.info("数据库连接已关闭")

    def get_compound_names(self, limit=None, product_ids=None) -> List[CompoundInfo]:
        """
        从数据库获取化合物名称列表

        Args:
            limit: 限制返回数量
            product_ids: 指定产品ID列表

        Returns:
            化合物信息列表
        """
        if not self.connection or not self._is_connected():
            self.logger.error("数据库未连接")
            return []

        compounds = []
        cursor = None

        try:
            # 根据MySQL客户端类型创建游标
            if self.mysql_client == 'mysql-connector':
                cursor = self.connection.cursor(dictionary=True)
            elif self.mysql_client == 'pymysql':
                import pymysql.cursors
                cursor = self.connection.cursor(pymysql.cursors.DictCursor)
            else:
                self.logger.error(f"不支持的MySQL客户端: {self.mysql_client}")
                return []

            # 构建查询
            query = """
                SELECT p.product_id, p.product_name, ypd.pubchem_cid
                FROM products p
                LEFT JOIN yeast_pubchem_data ypd ON p.product_id = ypd.product_id
            """

            params = []

            if product_ids:
                placeholders = ', '.join(['%s'] * len(product_ids))
                query += f" WHERE p.product_id IN ({placeholders})"
                params.extend(product_ids)

            query += " ORDER BY p.product_id"

            if limit:
                query += " LIMIT %s"
                params.append(limit)

            # 执行查询
            cursor.execute(query, params)
            rows = cursor.fetchall()

            for row in rows:
                compound = CompoundInfo(
                    product_id=row['product_id'],
                    product_name=row['product_name'],
                    existing_cid=row['pubchem_cid']
                )
                compounds.append(compound)

            self.logger.info(f"从数据库获取到 {len(compounds)} 个化合物")

        except Exception as e:
            self.logger.error(f"查询化合物名称失败: {e}")
        finally:
            if cursor:
                cursor.close()

        return compounds

    def search_pubchem_cid(self, compound_name: str) -> Optional[int]:
        """
        通过化合物名称搜索PubChem CID

        Args:
            compound_name: 化合物名称

        Returns:
            CID或None
        """
        import urllib.parse

        # 编码化合物名称
        encoded_name = urllib.parse.quote(compound_name)
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded_name}/cids/JSON"

        for attempt in range(self.max_retries):
            try:
                # 遵守速率限制
                time.sleep(self.api_delay)

                self.logger.debug(f"搜索CID: {compound_name} (尝试 {attempt+1}/{self.max_retries})")
                response = self.session.get(url, verify=False, timeout=30)
                response.raise_for_status()

                data = response.json()
                cids = data.get('IdentifierList', {}).get('CID', [])

                if cids:
                    cid = cids[0]
                    self.logger.debug(f"找到CID: {cid} for {compound_name}")
                    return cid
                else:
                    self.logger.warning(f"未找到化合物 '{compound_name}' 的CID")
                    return None

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    # 化合物未找到，正常情况
                    self.logger.warning(f"化合物 '{compound_name}' 未找到 (HTTP 404)")
                    return None
                elif e.response.status_code in [429, 503]:
                    # 速率限制或服务不可用，重试
                    wait_time = 2 * (2 ** attempt)  # 指数退避
                    self.logger.warning(
                        f"HTTP {e.response.status_code}，等待{wait_time}秒后重试 "
                        f"(尝试 {attempt+1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"HTTP错误 {e.response.status_code}: {e}")
                    if attempt == self.max_retries - 1:
                        return None
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                self.logger.error(f"请求或解析错误: {e}")
                if attempt == self.max_retries - 1:
                    return None

        return None

    def get_uses_tags_from_pug_view(self, cid: int) -> Optional[List[str]]:
        """
        从PUG View API获取Uses标签

        Args:
            cid: PubChem CID

        Returns:
            用途标签列表或None
        """
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON?heading=Uses"

        for attempt in range(self.max_retries):
            try:
                # 遵守速率限制
                time.sleep(self.api_delay)

                self.logger.debug(f"获取Uses标签: CID={cid} (尝试 {attempt+1}/{self.max_retries})")
                response = self.session.get(url, verify=False, timeout=30)
                response.raise_for_status()

                data = response.json()
                tags = self._extract_uses_from_response(data)

                if tags:
                    self.logger.debug(f"提取到 {len(tags)} 个Uses标签")
                    return tags
                else:
                    self.logger.warning(f"CID {cid} 未找到Uses标签")
                    return []

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    # Uses信息未找到，正常情况
                    self.logger.warning(f"CID {cid} 未找到Uses信息 (HTTP 404)")
                    return []
                elif e.response.status_code in [429, 503]:
                    # 速率限制或服务不可用，重试
                    wait_time = 2 * (2 ** attempt)  # 指数退避
                    self.logger.warning(
                        f"HTTP {e.response.status_code}，等待{wait_time}秒后重试 "
                        f"(尝试 {attempt+1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"HTTP错误 {e.response.status_code}: {e}")
                    if attempt == self.max_retries - 1:
                        return None
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                self.logger.error(f"请求或解析错误: {e}")
                if attempt == self.max_retries - 1:
                    return None

        return None

    def _extract_uses_from_response(self, json_data: Dict) -> List[str]:
        """
        从PUG View API响应中提取Uses标签

        Args:
            json_data: JSON响应数据

        Returns:
            用途标签列表
        """
        tags = []

        try:
            # 递归搜索"Uses"部分
            self._recursive_find_strings(json_data, tags, 'Uses')

            # 如果没有找到，尝试其他可能的关键词
            if not tags:
                for keyword in ['Use', 'Application', 'Applications']:
                    self._recursive_find_strings(json_data, tags, keyword)

        except Exception as e:
            self.logger.warning(f"提取Uses标签时出错: {e}")

        return tags

    def _recursive_find_strings(self, data: Any, tags: List[str], target_keyword: str, depth: int = 0):
        """
        递归查找包含目标关键词的StringWithMarkup字符串

        Args:
            data: 当前数据节点
            tags: 标签列表
            target_keyword: 目标关键词
            depth: 当前递归深度
        """
        if depth > 10:  # 限制递归深度
            return

        if isinstance(data, dict):
            # 检查当前节点是否包含目标关键词
            if 'Name' in data and isinstance(data['Name'], str):
                if target_keyword.lower() in data['Name'].lower():
                    # 查找StringWithMarkup
                    self._extract_strings_from_markup(data, tags)

            # 递归处理所有值
            for key, value in data.items():
                # 特别处理StringWithMarkup
                if key == 'StringWithMarkup':
                    self._extract_strings_from_markup(value, tags)
                else:
                    self._recursive_find_strings(value, tags, target_keyword, depth + 1)

        elif isinstance(data, list):
            for item in data:
                self._recursive_find_strings(item, tags, target_keyword, depth + 1)

    def _extract_strings_from_markup(self, markup_data: Any, tags: List[str]):
        """
        从StringWithMarkup结构中提取字符串

        Args:
            markup_data: StringWithMarkup数据
            tags: 标签列表
        """
        try:
            if isinstance(markup_data, dict):
                if 'String' in markup_data:
                    string_value = markup_data['String']
                    if string_value and isinstance(string_value, str):
                        tags.append(string_value.strip())

            elif isinstance(markup_data, list):
                for item in markup_data:
                    self._extract_strings_from_markup(item, tags)

        except Exception as e:
            self.logger.debug(f"提取字符串时出错: {e}")

    def get_standardized_name(self, cid: int) -> Optional[str]:
        """
        获取标准化名称（IUPAC名称或Preferred Name）

        Args:
            cid: PubChem CID

        Returns:
            标准化名称或None
        """
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/IUPACName,Title/JSON"

        try:
            # 遵守速率限制
            time.sleep(self.api_delay)

            self.logger.debug(f"获取标准化名称: CID={cid}")
            response = self.session.get(url, verify=False, timeout=30)
            response.raise_for_status()

            data = response.json()

            # 解析响应
            properties = data.get('PropertyTable', {}).get('Properties', [])
            if properties:
                prop = properties[0]
                # 优先使用IUPAC名称，其次使用Title
                iupac_name = prop.get('IUPACName')
                title = prop.get('Title')

                standardized_name = iupac_name or title
                if standardized_name:
                    self.logger.debug(f"找到标准化名称: {standardized_name}")
                    return standardized_name

            self.logger.warning(f"CID {cid} 未找到标准化名称")
            return None

        except Exception as e:
            self.logger.warning(f"获取标准化名称失败: {e}")
            return None

    def clean_and_join_tags(self, tags_list: List[str]) -> str:
        """
        清洗标签并用分号拼接

        Args:
            tags_list: 原始标签列表

        Returns:
            清洗后并用分号拼接的标签字符串
        """
        if not tags_list:
            return ""

        # 清洗标签
        cleaned_tags = []
        for tag in tags_list:
            if not tag or not isinstance(tag, str):
                continue

            # 去除首尾空格
            tag = tag.strip()

            # 过滤空字符串和过短的标签
            if tag and len(tag) >= 3:
                cleaned_tags.append(tag)

        # 去重
        unique_tags = []
        seen = set()
        for tag in cleaned_tags:
            tag_lower = tag.lower()
            if tag_lower not in seen:
                seen.add(tag_lower)
                unique_tags.append(tag)

        # 用分号拼接
        return "; ".join(unique_tags)

    def save_tags_to_database(self, product_id: int, cid: int,
                             tags_string: str, standardized_name: Optional[str] = None) -> bool:
        """
        保存标签到数据库

        Args:
            product_id: 产品ID
            cid: PubChem CID
            tags_string: 用途标签字符串
            standardized_name: 标准化名称

        Returns:
            是否成功
        """
        if not self.connection or not self._is_connected():
            self.logger.error("数据库未连接")
            return False

        if not tags_string:
            self.logger.warning(f"产品 {product_id} 无标签可保存")
            return False

        # 截断标签字符串以适应数据库列长度（VARCHAR(255)）
        max_length = 255
        if len(tags_string) > max_length:
            self.logger.warning(f"标签字符串过长 ({len(tags_string)} 字符)，截断到 {max_length} 字符")
            tags_string = tags_string[:max_length]

        cursor = None
        success = False

        try:
            cursor = self.connection.cursor()

            # 开始事务（根据MySQL客户端类型）
            if self.mysql_client == 'mysql-connector':
                self.connection.start_transaction()
            elif self.mysql_client == 'pymysql':
                # PyMySQL: 开始事务
                self.connection.begin()
            else:
                self.logger.error(f"不支持的MySQL客户端: {self.mysql_client}")
                return False

            # 1. 插入或更新PubChemTag
            tag_query = """
                INSERT INTO pubchem_tags (tag_name, tag_category, pubchem_classification)
                VALUES (%s, 'use_and_manufacturing', 'Uses')
                ON DUPLICATE KEY UPDATE tag_id = LAST_INSERT_ID(tag_id)
            """
            cursor.execute(tag_query, (tags_string,))
            tag_id = cursor.lastrowid

            # 2. 创建产品-标签关联
            association_query = """
                INSERT INTO product_pubchem_tags
                (product_id, pubchem_tag_id, confidence_score, source)
                VALUES (%s, %s, 1.0, 'pug_view_api')
                ON DUPLICATE KEY UPDATE
                confidence_score = VALUES(confidence_score),
                source = VALUES(source)
            """
            cursor.execute(association_query, (product_id, tag_id))

            # 3. 更新或插入PubChem数据
            pubchem_data_query = """
                INSERT INTO yeast_pubchem_data
                (product_id, pubchem_cid, iupac_name, sync_failed, last_sync_success)
                VALUES (%s, %s, %s, 0, NOW())
                ON DUPLICATE KEY UPDATE
                pubchem_cid = VALUES(pubchem_cid),
                iupac_name = VALUES(iupac_name),
                sync_failed = VALUES(sync_failed),
                last_sync_success = VALUES(last_sync_success)
            """
            cursor.execute(pubchem_data_query, (product_id, cid, standardized_name))

            # 提交事务
            self.connection.commit()

            self.logger.info(f"成功保存产品 {product_id} 的标签: {tags_string[:50]}...")
            success = True

        except Exception as e:
            # 回滚事务
            if self.connection:
                self.connection.rollback()
            self.logger.error(f"保存标签到数据库失败: {e}")
            success = False
        finally:
            if cursor:
                cursor.close()

        return success

    def process_compound(self, compound: CompoundInfo) -> ProcessingResult:
        """
        处理单个化合物的完整流程

        Args:
            compound: 化合物信息

        Returns:
            处理结果
        """
        start_time = time.time()
        result = ProcessingResult(
            product_id=compound.product_id,
            product_name=compound.product_name,
            success=False
        )

        try:
            self.logger.info(f"处理化合物: {compound.product_name} (ID: {compound.product_id})")

            # 1. 获取CID（优先使用现有CID）
            cid = compound.existing_cid
            if not cid:
                cid = self.search_pubchem_cid(compound.product_name)

            if not cid:
                result.error_message = "未找到CID"
                self.logger.warning(f"化合物 {compound.product_name} 未找到CID")
                return result

            result.cid = cid

            # 2. 获取Uses标签
            tags_list = self.get_uses_tags_from_pug_view(cid)
            if tags_list is None:  # 表示出错，不是空列表
                result.error_message = "获取Uses标签失败"
                return result

            # 3. 清洗和拼接标签
            tags_string = self.clean_and_join_tags(tags_list)
            result.uses_tags = tags_string

            # 4. 获取标准化名称
            standardized_name = self.get_standardized_name(cid)
            result.standardized_name = standardized_name

            # 5. 保存到数据库
            success = self.save_tags_to_database(
                compound.product_id, cid, tags_string, standardized_name
            )

            if success:
                result.success = True
                self.logger.info(f"成功处理化合物: {compound.product_name}")
            else:
                result.error_message = "保存到数据库失败"

        except Exception as e:
            result.error_message = str(e)
            self.logger.error(f"处理化合物 {compound.product_name} 时出错: {e}")

        result.processing_time = time.time() - start_time
        return result

    def process_batch(self, compounds: List[CompoundInfo],
                     dry_run: bool = False) -> List[ProcessingResult]:
        """
        批量处理化合物列表

        Args:
            compounds: 化合物列表
            dry_run: 试运行模式，不实际更新数据库

        Returns:
            处理结果列表
        """
        results = []
        total = len(compounds)

        self.logger.info(f"开始批量处理 {total} 个化合物")

        for i, compound in enumerate(compounds, 1):
            self.logger.info(f"进度: {i}/{total} ({i/total*100:.1f}%)")

            if dry_run:
                # 试运行模式，只模拟不实际更新
                self.logger.info(f"[试运行] 处理化合物: {compound.product_name}")
                result = ProcessingResult(
                    product_id=compound.product_id,
                    product_name=compound.product_name,
                    success=True
                )
                results.append(result)
                continue

            # 实际处理
            result = self.process_compound(compound)
            results.append(result)

            # 更新统计
            self.stats['total_processed'] += 1
            if result.success:
                self.stats['successful'] += 1
            else:
                self.stats['failed'] += 1

            # 显示进度
            success_rate = (self.stats['successful'] / i * 100) if i > 0 else 0
            self.logger.info(f"当前成功率: {success_rate:.1f}%")

        return results

    def print_statistics(self):
        """打印处理统计信息"""
        total = self.stats['total_processed']
        successful = self.stats['successful']
        failed = self.stats['failed']

        if total == 0:
            self.logger.info("未处理任何化合物")
            return

        success_rate = (successful / total * 100) if total > 0 else 0

        self.logger.info("=" * 60)
        self.logger.info("处理统计")
        self.logger.info("=" * 60)
        self.logger.info(f"总共处理: {total}")
        self.logger.info(f"成功: {successful} ({success_rate:.1f}%)")
        self.logger.info(f"失败: {failed} ({100 - success_rate:.1f}%)")
        self.logger.info(f"跳过: {self.stats['skipped']}")

        if self.stats['start_time'] and self.stats['end_time']:
            duration = self.stats['end_time'] - self.stats['start_time']
            self.logger.info(f"总耗时: {duration:.1f}秒")
            if successful > 0:
                self.logger.info(f"平均每个化合物: {duration/successful:.1f}秒")

    def run(self, limit=None, product_ids=None, batch_size=100,
            dry_run=False) -> bool:
        """
        主运行方法

        Args:
            limit: 限制处理数量
            product_ids: 指定产品ID列表
            batch_size: 批量大小
            dry_run: 试运行模式

        Returns:
            是否成功
        """
        self.stats['start_time'] = time.time()

        # 连接数据库（dry_run模式也需要连接以读取化合物列表）
        if not self.connect_to_database():
            self.logger.error("无法连接数据库，退出")
            return False

        try:
            # 获取化合物列表
            compounds = self.get_compound_names(limit, product_ids)
            if not compounds:
                self.logger.warning("未找到任何化合物")
                return False

            # 批量处理（分批处理避免内存占用过大）
            batch_results = []
            for i in range(0, len(compounds), batch_size):
                batch = compounds[i:i + batch_size]
                self.logger.info(f"处理批次: {i//batch_size + 1}/{(len(compounds) + batch_size - 1)//batch_size}")
                batch_result = self.process_batch(batch, dry_run)
                batch_results.extend(batch_result)

            results = batch_results

            # 打印详细结果
            self.print_statistics()

            # 保存结果到文件（可选）
            self._save_results_to_file(results)

            return True

        except Exception as e:
            self.logger.error(f"运行过程中出错: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # 总是断开数据库连接（dry_run模式也需要断开）
            self.disconnect_from_database()
            self.stats['end_time'] = time.time()

    def _save_results_to_file(self, results: List[ProcessingResult]):
        """保存处理结果到文件"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"pubchem_uses_extraction_{timestamp}.json"

            # 转换为可序列化的字典
            results_dict = []
            for result in results:
                result_dict = {
                    'product_id': result.product_id,
                    'product_name': result.product_name,
                    'cid': result.cid,
                    'standardized_name': result.standardized_name,
                    'uses_tags': result.uses_tags,
                    'success': result.success,
                    'error_message': result.error_message,
                    'processing_time': result.processing_time
                }
                results_dict.append(result_dict)

            # 添加统计信息
            output = {
                'timestamp': datetime.now().isoformat(),
                'statistics': self.stats.copy(),
                'results': results_dict
            }

            # 写入文件
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            self.logger.info(f"结果已保存到文件: {filename}")

        except Exception as e:
            self.logger.warning(f"保存结果到文件失败: {e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='PubChem用途标签提取与物质名称标准化脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 处理前10个化合物
  python extract_pubchem_uses_tags.py --limit 10

  # 处理指定ID的化合物
  python extract_pubchem_uses_tags.py --product-ids 1 2 3 5 8

  # 试运行模式
  python extract_pubchem_uses_tags.py --limit 5 --dry-run

  # 使用代理并增加延迟
  python extract_pubchem_uses_tags.py --proxy http://127.0.0.1:7890 --delay 0.5
        """
    )

    parser.add_argument('--limit', type=int,
                       help='限制处理数量')
    parser.add_argument('--product-ids', type=int, nargs='+',
                       help='指定产品ID列表')
    parser.add_argument('--delay', type=float, default=0.3,
                       help='API调用延迟（秒），默认0.3秒满足PubChem速率限制')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='最大重试次数，默认3')
    parser.add_argument('--proxy', type=str,
                       help='HTTP代理地址，例如：http://127.0.0.1:7890')
    parser.add_argument('--dry-run', action='store_true',
                       help='试运行模式，不实际更新数据库')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='日志级别，默认INFO')
    parser.add_argument('--log-file', type=str,
                       help='日志文件路径')

    args = parser.parse_args()

    # 设置日志级别
    log_level = getattr(logging, args.log_level.upper())

    # 创建提取器
    extractor = PubChemUsesExtractor(
        api_delay=args.delay,
        max_retries=args.max_retries,
        proxy=args.proxy,
        log_level=log_level
    )

    # 运行
    success = extractor.run(
        limit=args.limit,
        product_ids=args.product_ids,
        dry_run=args.dry_run
    )

    # 根据结果返回退出码
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()