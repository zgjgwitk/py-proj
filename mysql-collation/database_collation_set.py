#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 字段的字符集检查与修改
import pymysql
import pandas as pd
import re
from typing import List, Dict, Tuple
from urllib.parse import unquote
import datetime
import argparse
import configparser
import os

def get_ezp_databases(connection, exclude_databases: List[str] = None) -> List[str]:
    """获取所有以'ezp-'开头的数据库，排除指定的数据库"""
    if exclude_databases is None:
        exclude_databases = []
    
    with connection.cursor() as cursor:
        cursor.execute("SHOW DATABASES")
        databases = cursor.fetchall()
        return [db[0] for db in databases if db[0].startswith('ezp-') and db[0] not in exclude_databases]

def get_tables_in_database(connection, database: str) -> Dict[str, str]:
    """获取指定数据库中的所有表"""
    try:
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
        return {table[0]: table[1] for table in tables}
    except Exception as e:
        print(f"获取数据库 {database} 的表信息时发生错误: {e}")
        print(f"错误类型: {type(e).__name__}")
        if hasattr(e, 'args'):
            print(f"错误参数: {e.args}")
        return {}

def get_table_fields_with_collation(connection, database: str, table: str) -> List[Dict]:
    """获取表中所有字段及其排序规则"""
    try:
        cursor = connection.cursor()
        sql = f"SHOW FULL COLUMNS FROM `{database}`.`{table}`"
        cursor.execute(sql)
        
        fields_info = []
        for field in cursor.fetchall():
            field_name = field[0]
            field_type = field[1]
            collation = field[2]
            
            # 清理字段类型，移除默认值等额外信息
            # 例如："varchar(255)" -> "varchar(255)", "int(11) DEFAULT NULL" -> "int(11)"
            field_type_clean = field_type.split(' DEFAULT ')[0].split(' COMMENT ')[0].strip()
            
            fields_info.append({
                'database': database,
                'table': table,
                'field_name': field_name,
                'field_type': field_type_clean,
                'collation': collation
            })
        
        cursor.close()
        return fields_info
    except Exception as e:
        print(f"获取表 {database}.{table} 字段信息时发生错误: {e}")
        print(f"错误类型: {type(e).__name__}")
        if hasattr(e, 'args'):
            print(f"错误参数: {e.args}")
        print(f"执行的SQL: {sql}")
        return []

def get_table_structure(connection, database: str, table_name: str) -> str:
    """获取表的完整结构信息"""
    try:
        cursor = connection.cursor()
        sql = f"SHOW CREATE TABLE `{database}`.`{table_name}`"
        cursor.execute(sql)
        result = cursor.fetchone()
        cursor.close()
        
        if result and len(result) >= 2:
            return result[1]  # 返回CREATE TABLE语句
        return ""
    except Exception as e:
        print(f"获取表 {database}.{table_name} 结构时发生错误: {e}")
        print(f"错误类型: {type(e).__name__}")
        if hasattr(e, 'args'):
            print(f"错误参数: {e.args}")
        print(f"执行的SQL: {sql}")
        return ""

def check_database_collation(database_cfg: Dict[str, str], dry_run: bool = True, exclude_databases: List[str] = None, ignore_tables_dict: Dict[str, str] = None) -> List[Dict]:
    """检查数据库中所有ezp-开头的库的字段排序规则，直接执行更新语句并记录结果
    
    Args:
        database_cfg: 数据库连接配置
        dry_run: 是否模拟执行，为True时只生成SQL但不实际执行
        exclude_databases: 需要排除的数据库列表
    """
    
    # 连接到MySQL
    connection = pymysql.connect(
        host=database_cfg['server'],
        user=database_cfg['username'],
        password=database_cfg['password'],
        charset=database_cfg['charset'],
        connect_timeout=database_cfg['connect_timeout']
    )
    print(f"正在检查数据库host: {database_cfg['server']}")
    if dry_run:
        print("模拟执行模式：只生成SQL语句，不实际执行修改")
    
    table_results = []

    try:
        # 获取所有ezp-开头的数据库
        ezp_databases = get_ezp_databases(connection, exclude_databases)
        print(f"找到 {len(ezp_databases)} 个数据库, 排除的数据库: {exclude_databases}")
        
        for database in ezp_databases:
            print(f"正在检查数据库: {database}")
            
            # 获取数据库中的所有表
            tables = get_tables_in_database(connection, database)
            
            for table_name, table_collation in tables.items():
                # 检查表的字符集是否为utf8mb4开头
                if table_collation and table_collation != 'utf8mb4_general_ci':
                    # 检查是否在忽略列表中
                    if ignore_tables_dict and ignore_tables_dict.get(f"{database}.{table_name}", '0') == '1':
                        print(f"忽略表: {database}.{table_name} 的修改")
                        continue

                    # 获取表中所有字段的排序规则
                    fields_info = get_table_fields_with_collation(connection, database, table_name)
                    
                    table_invalid_fields = []
                    executed_sqls = []
                    
                    # 收集需要修改的字段信息
                    modify_columns = []
                    
                    for field_info in fields_info:
                        # 检查排序规则是否为utf8mb4_general_ci
                        if field_info['collation'] and field_info['collation'] != 'utf8mb4_general_ci':
                            table_invalid_fields.append(field_info)
                            print(f"发现不符合的字段: {database}.{table_name}.{field_info['field_name']} - 排序规则: {field_info['collation']}")
                            
                            # 收集需要修改的字段信息
                            modify_columns.append(f" MODIFY `{field_info['field_name']}` {field_info['field_type']}")
                    
                    # 如果有需要修改的字段
                    if modify_columns:
                        # 生成合并的ALTER TABLE语句
                        sql = f"ALTER TABLE `{database}`.`{table_name}` " + ", \n    ".join(modify_columns) + ";"
                        
                        try:
                            if dry_run:
                                # 模拟执行模式：只记录SQL，不实际执行
                                executed_sqls.append({
                                    'sql': sql,
                                    'status': '模拟执行',
                                    'message': '模拟执行模式，未实际执行SQL'
                                })
                                print(f"模拟执行模式：生成SQL语句但不执行 - {database}.{table_name}")
                            else:
                                # 实际执行模式：执行SQL语句
                                cursor = connection.cursor()
                                cursor.execute(sql)
                                connection.commit()
                                cursor.close()
                                
                                executed_sqls.append({
                                    'sql': sql,
                                    'status': '成功',
                                    'message': '执行成功'
                                })
                                print(f"成功修改表 {database}.{table_name} 的字段排序规则")
                                
                        except Exception as e:
                            executed_sqls.append({
                                'sql': sql,
                                'status': '失败',
                                'message': str(e)
                            })
                            print(f"修改表 {database}.{table_name} 的字段排序规则时发生错误: {e}")
                    
                    # 将表级别的结果添加到总结果中
                    if modify_columns:
                        # 获取表的完整结构信息（修改前）
                        table_structure_before = get_table_structure(connection, database, table_name)
                        table_results.append({
                            'database': database,
                            'table': table_name,
                            'table_collation': table_collation,
                            'table_structure_before': table_structure_before,  # 保存修改前的表结构
                            'invalid_fields': table_invalid_fields,
                            'invalid_fields_count': len(table_invalid_fields),
                            'executed_sqls': executed_sqls
                        })
    
    finally:
        connection.close()
    
    return table_results

def export_to_excel(table_results: List[Dict], output_file: str):
    """将不符合条件的字段按照表维度导出到Excel文件"""
    try:
        if table_results:
            # 创建表级别的汇总数据
            table_summary_data = []
            field_detail_data = []
            sql_execution_data = []
            table_structure_data = []
            
            for table_result in table_results:
                # 只保存需要修改的表信息
                if table_result['invalid_fields_count'] > 0:
                    # 表级别汇总信息
                    table_summary_data.append({
                        '数据库': table_result['database'],
                        '表名': table_result['table'],
                        '表排序规则': table_result['table_collation'],
                        '不符合字段数量': table_result['invalid_fields_count']
                    })
                    
                    # 表结构信息
                    table_structure_data.append({
                        '数据库': table_result['database'],
                        '表名': table_result['table'],
                        '修改前表结构': table_result.get('table_structure_before', '')
                    })
                    
                    # 字段详细信息
                    for field_info in table_result['invalid_fields']:
                        field_detail_data.append({
                            '数据库': table_result['database'],
                            '表名': table_result['table'],
                            '字段名': field_info['field_name'],
                            '字段类型': field_info['field_type'],
                            '当前排序规则': field_info['collation'],
                            '目标排序规则': 'utf8mb4_general_ci'
                        })
                    
                    # SQL执行结果信息
                    for i, sql_result in enumerate(table_result['executed_sqls']):
                        sql_execution_data.append({
                            '数据库': table_result['database'],
                            '表名': table_result['table'],
                            '序号': i + 1,
                            'SQL修改语句': sql_result['sql'],
                            '执行状态': sql_result['status'],
                            '执行结果': sql_result['message']
                        })
            
            # 使用ExcelWriter创建多sheet的Excel文件
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Sheet1: 表级别汇总
                if table_summary_data:
                    df_summary = pd.DataFrame(table_summary_data)
                    df_summary.to_excel(writer, sheet_name='表汇总', index=False)
                
                # Sheet2: 字段详细信息
                if field_detail_data:
                    df_fields = pd.DataFrame(field_detail_data)
                    df_fields.to_excel(writer, sheet_name='字段详情', index=False)
                
                # Sheet3: SQL执行结果
                if sql_execution_data:
                    df_sql = pd.DataFrame(sql_execution_data)
                    df_sql.to_excel(writer, sheet_name='SQL执行结果', index=False)
                
                # Sheet4: 表结构信息
                if table_structure_data:
                    df_structure = pd.DataFrame(table_structure_data)
                    df_structure.to_excel(writer, sheet_name='表结构信息', index=False)
            
            print(f"已导出 {len(table_results)} 个表的数据到 {output_file}")
            print(f"- 表汇总: {len(table_summary_data)} 条记录")
            print(f"- 字段详情: {len(field_detail_data)} 条记录")
            print(f"- SQL执行结果: {len(sql_execution_data)} 条记录")
            print(f"- 表结构信息: {len(table_structure_data)} 条记录")
        else:
            print("未发现不符合排序规则的字段")
    except Exception as e:
        print(f"导出Excel文件时发生错误: {e}")
        raise

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
    
    # 获取配置中的模拟执行设置
    dry_run = False
    if config.has_section('settings'):
        if config.has_option('settings', 'dry_run'):
            dry_run = config.getboolean('settings', 'dry_run')

    # 从配置文件读取数据库连接配置
    if not config.has_section('database'):
        print("错误：配置文件中缺少[database]配置段")
        return

    database_cfg = {
        'server': config.get('database', 'server', fallback='localhost'),
        'database': config.get('database', 'database', fallback=''),
        'username': config.get('database', 'username', fallback='root'),
        'password': config.get('database', 'password', fallback=''),
        'connection_timeout': int(config.get('database', 'connection_timeout', fallback='5')),
        'charset': config.get('database', 'charset', fallback='utf8'),
        'pooling': config.get('database', 'pooling', fallback='True')
    }
    
    # 读取排除数据库列表
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

    # 输出文件名
    output_file = "modify_field_results_default.xlsx"
    if config.has_section('output'):
        output_file = config.get('output', 'modify_field_excel_file', fallback='modify_field_results_default.xlsx')
    
    try:
        # 检查数据库排序规则
        start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"程序开始运行！time: {start_time}")
        table_results = check_database_collation(database_cfg, dry_run=dry_run, exclude_databases=exclude_databases, ignore_tables_dict=ignore_tables_dict)
        
        # 导出到Excel
        excel_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"导出到Excel！time: {excel_time}")
        export_to_excel(table_results, output_file)
        
        finish_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"检查完成！time: {finish_time}")
        
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    main()
