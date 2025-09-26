#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 字段的字符集检查
import pymysql
import pandas as pd
import re
from urllib.parse import unquote
import datetime
import argparse
import configparser
import os
from typing import List, Dict, Tuple

def get_all_databases(connection, exclude_databases: List[str] = None) -> List[str]:
    """获取所有以'ezp-'开头的数据库"""
    if exclude_databases is None:
        exclude_databases = []
    with connection.cursor() as cursor:
        cursor.execute("SHOW DATABASES")
        return [db[0] for db in cursor.fetchall() if db[0].startswith('ezp-') and db[0] not in exclude_databases]

def check_table_collation(connection, database, ignore_tables_dict: Dict[str, str] = None):
    """检查数据库中表的字符集"""
    results = []
    
    # 切换到指定数据库
    connection.select_db(database)
    
    with connection.cursor() as cursor:
        # 获取所有表的collation信息
        cursor.execute("""
            SELECT 
                TABLE_NAME, 
                TABLE_COLLATION 
            FROM 
                information_schema.TABLES 
            WHERE 
                TABLE_SCHEMA = %s
        """, (database,))
        
        tables = cursor.fetchall()
        
        for table_name, table_collation in tables:
            # 检查表的collation是否不为'utf8mb4_general_ci'
            if table_collation and table_collation != 'utf8mb4_general_ci':
                # 检查是否在忽略列表中
                if ignore_tables_dict and ignore_tables_dict.get(f"{database}.{table_name}", '0') == '1':
                    print(f"忽略表: {database}.{table_name} 的修改")
                    continue
                else:
                    print(f"正在检查表: {database}.{table_name} 的字段")
                try:
                    cursor = connection.cursor()
                    sql = f"SHOW FULL COLUMNS FROM `{database}`.`{table_name}`"
                    cursor.execute(sql)
                    
                    for field in cursor.fetchall():
                        field_name = field[0]
                        field_type = field[1]
                        field_collation = field[2]
                        
                        # 清理字段类型，移除默认值等额外信息
                        # 例如："varchar(255)" -> "varchar(255)", "int(11) DEFAULT NULL" -> "int(11)"
                        field_type_clean = field_type.split(' DEFAULT ')[0].split(' COMMENT ')[0].strip()
                        
                        # 检查字段的collation是否不为'utf8mb4_general_ci'
                        if field_collation and field_collation != 'utf8mb4_general_ci':
                            results.append({
                                'database': database,
                                'table_name': table_name,
                                'table_collation': table_collation,
                                'column_name': field_name,
                                'column_type': field_type_clean,
                                'column_collation': field_collation
                            })
                    
                    cursor.close()
                except Exception as e:
                    print(f"获取表 {database}.{table} 字段信息时发生错误: {e}")
                    print(f"错误类型: {type(e).__name__}")
                    if hasattr(e, 'args'):
                        print(f"错误参数: {e.args}")
                    print(f"执行的SQL: {sql}")
            else:
                print(f"正在检查表: {table_name} 的字段, 字符集为: {table_collation}")
                results.append({
                    'database': database,
                    'table_name': table_name,
                    'table_collation': table_collation,
                    'column_name': '',
                    'column_type': '',
                    'column_collation': ''
                })
    return results

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='数据库排序规则检查器')
    parser.add_argument('--config', type=str, default='config.ini',
                       help='配置文件路径（默认：config.ini）')

    args = parser.parse_args()
    
    # 读取配置文件
    config = configparser.ConfigParser()
    with open(args.config, 'r', encoding='utf-8') as f:
        config.read_file(f)
    
    # 读取数据库连接配置文件 - add(dbconn.ini)
    db_config = configparser.ConfigParser()
    db_config_path = 'dbconn.ini'
    if os.path.exists(db_config_path):
        with open(db_config_path, 'r', encoding='utf-8') as f:
            db_config.read_file(f)
        # 将db_config中的配置合并到config中
        for section in db_config.sections():
            if not config.has_section(section):
                config.add_section(section)
            for key, value in db_config.items(section):
                config.set(section, key, value)

    # 从配置文件读取数据库连接配置
    if not config.has_section('database'):
        print("错误：配置文件中缺少[database]配置段")
        return
    server = config.get('database', 'server', fallback='localhost')
    database = config.get('database', 'database', fallback='')
    username = config.get('database', 'username', fallback='root')
    password = config.get('database', 'password', fallback='')
    connection_timeout = int(config.get('database', 'connection_timeout', fallback='5'))
    charset = config.get('database', 'charset', fallback='utf8')
    pooling = config.get('database', 'pooling', fallback='True')
    
    # 从配置文件读取排除数据库列表
    exclude_databases = []
    if config.has_option('settings', 'exclude_databases'):
        exclude_databases_str = config.get('settings', 'exclude_databases', fallback='')
        if exclude_databases_str:
            # 移除可能存在的反斜杠和空格，然后分割并创建列表
            cleaned_str = exclude_databases_str.replace('\\', '').replace('\n', '').strip()
            exclude_databases = [db.strip() for db in cleaned_str.split(',') if db.strip()]
    else:
        print("未配置排除的数据库列表")
    
    # 从配置文件中读取需要忽略的表
    ignore_tables_dict = {}
    if config.has_option('settings', 'ignore_tables'):
        ignore_tables_str = config.get('settings', 'ignore_tables', fallback='')
        if ignore_tables_str:
            # 移除可能存在的反斜杠和空格，然后分割并创建字典
            cleaned_str = ignore_tables_str.replace('\\', '').replace('\n', '').strip()
            ignore_tables_dict = {table.strip(): '1' for table in cleaned_str.split(',') if table.strip()}
    else:
        print("未配置忽略的表列表")
    try:
        # 建立数据库连接
        connection = pymysql.connect(
            host=server,
            user=username,
            password=password,
            charset=charset,
            connect_timeout=connection_timeout
        )
        start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"成功连接到MySQL服务器: {server}, time: {start_time}")
        
        # 获取所有数据库
        databases = get_all_databases(connection, exclude_databases)
        print(f"找到 {len(databases)} 个数据库, 排除的数据库: {exclude_databases}")
        
        all_results = []
        
        # 遍历所有数据库
        for db in databases:
            print(f"正在检查数据库: {db}")
            results = check_table_collation(connection, db, ignore_tables_dict)
            all_results.extend(results)
        
        # 将结果转换为DataFrame
        if all_results:
            print(f"共找到 {len(all_results)} 条记录")
            df = pd.DataFrame(all_results)
            
            # 输出文件名
            output_file = "check_field_results_default.xlsx"
            if config.has_section('output'):
                output_file = config.get('output', 'check_field_excel_file', fallback='check_field_results_default.xlsx')
    
            # 保存为Excel文件
            df.to_excel(output_file, index=False, engine='openpyxl')
            print(f"结果已保存到: {output_file}")
        else:
            print("未找到符合条件的表和字段")
        
    except Exception as e:
        print(f"错误: {e}")
    finally:
        if 'connection' in locals() and connection:
            connection.close()
            finish_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"数据库连接已关闭！time: {finish_time}")

if __name__ == "__main__":
    main()