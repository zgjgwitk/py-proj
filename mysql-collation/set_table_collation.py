#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 修改表的字符集
import pymysql
import pandas as pd
import re
from urllib.parse import unquote
import datetime
import argparse
import configparser
import os
from typing import List, Dict, Tuple

def get_ezp_databases(connection, exclude_databases: List[str] = None) -> List[str]:
    """获取所有以'ezp-'开头的数据库，排除指定的数据库"""
    if exclude_databases is None:
        exclude_databases = []
    
    with connection.cursor() as cursor:
        cursor.execute("SHOW DATABASES")
        databases = cursor.fetchall()
        return [db[0] for db in databases if db[0].startswith('ezp-') and db[0] not in exclude_databases]

def check_and_modify_table_collation(connection, database, ignore_tables_dict: Dict[str, str] = None):
    """检查并修改数据库中表的字符集"""
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
            # 检查表的collation是否为'utf8mb4'开头
            if table_collation and table_collation != 'utf8mb4_general_ci':
                # 检查是否在忽略列表中
                if ignore_tables_dict is not None and ignore_tables_dict.get(f"{database}.{table_name}", '0') == '1':
                    print(f"忽略表: {database}.{table_name} 的修改")
                    continue
                else:
                    print(f"正在修改表: {database}.{table_name} 的字符集为 utf8mb4_general_ci")
                
                # 修改表的字符集
                alter_table_sql = f"ALTER TABLE `{table_name}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
                try:
                    cursor.execute(alter_table_sql)
                    results.append({
                        'database': database,
                        'table_name': table_name,
                        'old_collation': table_collation,
                        'new_collation': 'utf8mb4_general_ci',
                        'status': 'success'
                    })
                    print(f"成功修改表 {table_name} 的字符集")
                except Exception as e:
                    error_msg = str(e)
                    if "1118" in error_msg and "Row size too large" in error_msg:
                        status_msg = "failed: Row size too large (1118) - table has too many columns for utf8mb4 conversion"
                        print(f"表 {table_name} 转换失败: 行大小过大，转换失败")
                    elif "1071" in error_msg and "Specified key was too long" in error_msg:
                        status_msg = "failed: Key too long (1071) - index key length exceeds 767 bytes limit"
                        print(f"表 {table_name} 转换失败: 索引键长度超过767字节限制")
                    else:
                        status_msg = f'failed: {error_msg}'
                        print(f"修改表 {table_name} 字符集失败: {error_msg}")
                    
                    results.append({
                        'database': database,
                        'table_name': table_name,
                        'old_collation': table_collation,
                        'new_collation': 'utf8mb4_general_ci',
                        'status': status_msg
                    })
    
    return results

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='数据库排序规则检查器')
    parser.add_argument('--config', type=str, default='config.ini',
                       help='配置文件路径（默认：config.ini）')

    args = parser.parse_args()
    
    # 读取主配置文件
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
        databases = get_ezp_databases(connection, exclude_databases)
        print(f"找到 {len(databases)} 个数据库, 排除的数据库: {exclude_databases}")
        
        all_results = []
        
        # 遍历所有数据库
        for db in databases:
            print(f"正在处理数据库: {db}")
            results = check_and_modify_table_collation(connection, db, ignore_tables_dict)
            all_results.extend(results)
        
        # 将结果转换为DataFrame
        if all_results:
            print(f"共处理了 {len(all_results)} 张表")
            df = pd.DataFrame(all_results)
            
            # 保存为Excel文件
            output_file = "modify_table_collation_results_default.xlsx"
            if config.has_section('output'):
                output_file = config.get('output', 'modify_table_excel_file', fallback='modify_table_collation_results_default.xlsx')
            # 指定引擎以避免'No engine for filetype'错误
            df.to_excel(output_file, index=False, engine='openpyxl')
            print(f"结果已保存到: {output_file}")
        else:
            print("未找到需要修改字符集的表")
        
    except Exception as e:
        print(f"错误: {e}")
    finally:
        if 'connection' in locals() and connection:
            connection.close()
            finish_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"数据库连接已关闭 time: {finish_time}")

if __name__ == "__main__":
    main()