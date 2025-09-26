# -* - coding: UTF-8 -* -
#! /usr/bin/python
# 功能: 解析excel, 组装 bulk 语句

import numpy as np
import pandas as pd


def showEsSql(x):
    vipid = x['id']
    mobileNo = x['mobileNo']
    id = x['_id']
    print('{ "update" : { "_index" : "esmsgsms2409", "_type" : "_doc", "_id":"%s" } }\n{ "doc" : {"toUser" : %s} }' % (id, vipid))

# 加载 excel sheet表, 参数 sheet_name=1 表示 sheet 的序号, 从0开始
lists = pd.read_excel("py-es/bulk.xls", 0)
tb = pd.DataFrame(data=lists)

tb.apply(showEsSql, axis=1)