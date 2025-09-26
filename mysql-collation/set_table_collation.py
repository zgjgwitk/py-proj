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

def get_ezp_databases(connection):
    """获取所有以'ezp-'开头的数据库，排除'ezp-ed'和'ezp-base'"""
    with connection.cursor() as cursor:
        cursor.execute("SHOW DATABASES")
        databases = cursor.fetchall()
        return [db[0] for db in databases if db[0].startswith('ezp-') and db[0] not in ['ezp-ed', 'ezp-base']]

def check_and_modify_table_collation(connection, database):
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
            # 检查表的collation是否不为'utf8mb4'开头
            if table_collation and not table_collation.startswith('utf8mb4'):
                print(f"正在修改表: {table_name} 的字符集为 utf8mb4_unicode_ci")
                
                # 修改表的字符集
                alter_table_sql = f"ALTER TABLE `{table_name}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                try:
                    cursor.execute(alter_table_sql)
                    results.append({
                        'database': database,
                        'table_name': table_name,
                        'old_collation': table_collation,
                        'new_collation': 'utf8mb4_unicode_ci',
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
                        'new_collation': 'utf8mb4_unicode_ci',
                        'status': status_msg
                    })
    
    return results

def main():
    # MySQL连接字符串
    conn_str = "server=192.168.128.14;database=ezp-base;uid=root;pwd=G3T2D5U3Y1g9UYvc;Connection Timeout=5;Charset=utf8;Pooling=True;" # test
    # conn_str = "server=10.0.1.4;database=ezp-crm;uid=root;pwd=ezr20150228;Connection Timeout=5;Charset=utf8mb4;Pooling=True;AllowUserVariables=True;" #429
    # conn_str = "server=172.21.17.39;database=ezp-crm;uid=root;pwd=5o)CkCA)6Hd+nwHM;Connection Timeout=5;Charset=utf8mb4;Pooling=True;AllowUserVariables=True;" #186
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
        databases = get_ezp_databases(connection)
        print(f"找到 {len(databases)} 个数据库")
        
        all_results = []
        
        # 遍历所有数据库
        for db in databases:
            print(f"正在处理数据库: {db}")
            results = check_and_modify_table_collation(connection, db)
            all_results.extend(results)
        
        # 将结果转换为DataFrame
        if all_results:
            df = pd.DataFrame(all_results)
            
            # 保存为Excel文件
            output_file = 'collation_modify_results.xlsx'
            df.to_excel(output_file, index=False)
            print(f"结果已保存到: {output_file}")
            print(f"共处理了 {len(all_results)} 张表")
        else:
            print("未找到需要修改字符集的表")
        
    except Exception as e:
        print(f"错误: {e}")
    finally:
        if 'connection' in locals() and connection:
            connection.close()
            print("数据库连接已关闭")

if __name__ == "__main__":
    main()