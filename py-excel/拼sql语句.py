# -* - coding: UTF-8 -* -
#! /usr/bin/python
# 功能: 从 excel 中读取表格数据, 然后组装成SQL语句

import numpy as np
import pandas as pd
import time

# 加工数据的方法

# 文件路径
sourceFilePath = "C:/Users/PC/Desktop/sql.xlsx"
targetFilePath = "C:/Users/PC/Desktop/sql_new.xlsx"

def showSql(x):
    id = x['Id']
    brandid = x['BrandId']
    title = x['Title']
    time = x['Time']
    try:
        return '''INSERT INTO `ezp-canal`.`new_table` (`Id`, `BrandId`, `Title`, `Time`) 
    VALUES (%d, %d, "%s", "%s");''' % (id, brandid, title, time)
    except:
        print(x)


# 加载 excel 数据, 参数 sheet_name=0 表示 sheet 的序号, 从0开始
lists = pd.read_excel(sourceFilePath, 0)
tb = pd.DataFrame(data=lists)

# 创建新列 "SQL"
tb.insert(loc=tb.columns.size, column='SQL', value='')

# 给sql字段赋值, axis=1 表示按行读取
tb['SQL'] = tb.apply(showSql, axis=1)

# 重写原Excel-sheet
writer = pd.ExcelWriter(sourceFilePath)

# 处理好的 sql 写入新 excel
# tb.to_excel(targetFilePath, sheet_name='bluewhale_cc')  
writer.save()
