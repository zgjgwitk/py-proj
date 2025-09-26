#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pymysql
import pandas as pd
import re
from urllib.parse import unquote

def parse_connection_string(conn_str):
    """解析MySQL连接字符串"""
    params = {}
    # 分割连接字符串
    parts = conn_str.split(';')
    for part in parts:
        if '=' in part:
            key, value = part.split('=', 1)
            params[key.lower()] = value
    
    # 解码密码（如果有URL编码）
    if 'pwd' in params:
        params['pwd'] = unquote(params['pwd'])
    
    return {
        'host': params.get('server', ''),
        'user': params.get('uid', ''),
        'password': params.get('pwd', ''),
        'db': params.get('database', ''),
        'charset': params.get('charset', 'utf8'),
        'connect_timeout': int(params.get('connection timeout', 5))
    }

def get_all_databases(connection):
    """获取所有以'ezp-'开头的数据库"""
    with connection.cursor() as cursor:
        cursor.execute("SHOW DATABASES")
        return [db[0] for db in cursor.fetchall() if db[0].startswith('ezp-')]

def check_table_collation(connection, database):
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
            # 检查表的collation是否包含'utf8_'
            if table_collation and not table_collation.startswith('utf8mb4'):
                print(f"正在检查表: {table_name} 的字段")
                # 获取表的字段collation信息
                cursor.execute("""
                    SELECT 
                        COLUMN_NAME, 
                        COLUMN_TYPE, 
                        COLLATION_NAME 
                    FROM 
                        information_schema.COLUMNS 
                    WHERE 
                        TABLE_SCHEMA = %s 
                        AND TABLE_NAME = %s 
                        AND DATA_TYPE IN ('varchar', 'char', 'text', 'enum', 'set', 'tinytext', 'mediumtext', 'longtext')
                """, (database, table_name))
                
                columns = cursor.fetchall()
                
                for column_name, column_type, column_collation in columns:
                    # 检查字段的collation是否不为'utf8mb4'开头
                    if column_collation and not column_collation.startswith('utf8mb4'):
                        results.append({
                            'database': database,
                            'table_name': table_name,
                            'table_collation': table_collation,
                            'column_name': column_name,
                            'column_type': column_type,
                            'column_collation': column_collation
                        })
    
    return results

def main():
    # MySQL连接字符串
    conn_str = "server=192.168.128.14;database=ezp-base;uid=ezwrite;pwd=33KlsXareQbsbrfhq2eJ;Connection Timeout=5;Charset=utf8;Pooling=True;" # test
    # conn_str = "server=172.21.17.39;database=ezp-crm;uid=ezread;pwd=T0_gC56u+3f@y5M1;Connection Timeout=5;Charset=utf8mb4;Pooling=True;AllowUserVariables=True;" #186
    # 解析连接字符串
    conn_params = parse_connection_string(conn_str)
    
    try:
        # 建立数据库连接
        connection = pymysql.connect(
            host=conn_params['host'],
            user=conn_params['user'],
            password=conn_params['password'],
            charset=conn_params['charset'],
            connect_timeout=conn_params['connect_timeout']
        )
        
        print(f"成功连接到MySQL服务器: {conn_params['host']}")
        
        # 获取所有数据库
        databases = get_all_databases(connection)
        print(f"找到 {len(databases)} 个数据库")
        
        all_results = []
        
        # 遍历所有数据库
        for db in databases:
            print(f"正在检查数据库: {db}")
            results = check_table_collation(connection, db)
            all_results.extend(results)
        
        # 将结果转换为DataFrame
        if all_results:
            df = pd.DataFrame(all_results)
            
            # 保存为Excel文件
            output_file = 'collation_check_results.xlsx'
            df.to_excel(output_file, index=False)
            print(f"结果已保存到: {output_file}")
            print(f"共找到 {len(all_results)} 条记录")
        else:
            print("未找到符合条件的表和字段")
        
    except Exception as e:
        print(f"错误: {e}")
    finally:
        if 'connection' in locals() and connection:
            connection.close()
            print("数据库连接已关闭")

if __name__ == "__main__":
    main()