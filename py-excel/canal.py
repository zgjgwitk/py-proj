# -* - coding: UTF-8 -* -
#! /usr/bin/python
# 参考资料 <pandas> https://www.cnblogs.com/t-dashuai/p/15404501.html

import numpy as np
import pandas as pd
import time


def showSql(x):
    # print(x['JobType'],x['TableName'],x['Sql'],sep=',')
    jobType = x['JobType']
    tbName = x['TableName']
    groupId = jobType
    if jobType == 'BigDataIntegrationPush':
        groupId = 'BigDataIntegrationPush'
    elif jobType == 'CDPUnionPush':
        groupId = 'CDPUnionPush'
    return ('INSERT INTO `ezp-canal`.`canal_table_consumer` (`TableName`, `ConsumerGroupId`, `GreyBrandId`, `CreateTime`, `UpdateTime`, `ForwardCount`, `Status`) VALUES ("%s", "%s", 0, "%s", NULL, NULL, 1);' % (tbName, groupId, now))


# 加载 excel sheet表, 参数 sheet_name=1 表示 sheet 的序号, 从0开始
lists = pd.read_excel("D:/Work_Doc/canal.xls", 1)
tb = pd.DataFrame(data=lists)

# for x in tb:
#     print(x)

tb1 = tb.loc[(tb['JobType'] == 'OpenApiUnionPush'), [
    'JobType', 'TableName']]  # 过滤数据, 筛选字段
tb1 = tb1.sort_values(by=['JobType'])  # 排序
# print(tb1['JobType'].count())
tb1.insert(loc=2, column='Sql', value='1')  # 添加新列 'sql'
now = time.strftime("%Y-%m-%d %X", time.localtime())  # 全局时间
tb1['Sql'] = tb1.apply(showSql, axis=1)  # 给sql字段赋值, axis=1 表示按行读取
tb2 = tb1.loc[:, ['Sql', 'TableName']]  # 去掉 'JobType' 字段, 因为去重用不到这个字段
tb2.drop_duplicates(inplace=True)  # 在源数据上去重
tb2.to_excel('D:/Work_Doc/excel_to_python.xlsx',
             sheet_name='bluewhale_cc')  # 处理好的 sql 写入新 excel
# print(tb2['Sql'])


# df2.duplicated()#检查重复值 以Boolean形式进行输出展示
# df2.duplicated().sum()#打印有多少重复值
# df2[df2.duplicated()]#打印重复值
# df2[df2.duplicated()==False]#打印非重复值
# df2.drop_duplicates()#删除重复值(此操作并不是在数据源本身进行删除操作)
# df2.drop_duplicates(inplace=True)#删除重复值(此操作是在数据源本身进行删除操作)
