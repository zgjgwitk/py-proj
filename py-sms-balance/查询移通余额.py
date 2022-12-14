# -* - coding: UTF-8 -* -
#! /usr/bin/python
# 功能: 根据账号密码查询移通的余额

from http import cookies
import numpy as np
import pandas as pd # Excel
import re # 正则
import time
import requests
import xml.dom.minidom

def reqYT(x):
    name = x['acc']
    pwd = x['pwd']
    brandId = x['id']
    url = 'http://quota.10690007.com/query2/getquota.xml?name={_name}&pwd={_pwd}'.format(_name=name, _pwd=pwd)
    # print(url)
    r = requests.request('get', url)
    time.sleep(0.05)
    val = explainXml(r.text)
    print('brandId:{_bid},val:{_val}'.format(_bid=brandId,_val=val))
    return val

def explainXml(x):
    # 第1个参数为输入源，返回一个ElementTree对象
    dom = xml.dom.minidom.parseString(x)
    # 通过元素树(ElementTree)得到根结点
    #得到文档元素对象
    root = dom.documentElement
    # 查看标签
    # print(root.nodeName)
    itemCode = root.getElementsByTagName('result')
    # print(itemlist[0].firstChild.data)
    code = itemCode[0].firstChild.data
    if code == '000':
        itemBalance = root.getElementsByTagName('total')
        balance = itemBalance[0].firstChild.data
        return balance
    else:
        return 'Error'

# 读取excel数据
def loadExcelRows():
    sheetIndex = 0 # 选择好需要读取的sheet 序值, 从0开始
    lists = pd.read_excel("D:/Work_Doc/1.xlsx", sheetIndex)
    tb = pd.DataFrame(data=lists)
    return tb

# 主方法
def main():
    tb = loadExcelRows()
    tb1 = tb.loc[(tb['pwd'] != ''), [
        'id', 'name', 'acc', 'pwd', 'bal']]  # 过滤数据, 筛选字段

    tb1['bal'] = tb1.apply(reqYT, axis=1)  # 给sql字段赋值, axis=1 表示按行读取
    tb1.to_excel('D:/Work_Doc/balance.xlsx',
        sheet_name='bal')  # 处理好的 sql 写入新 excel

if __name__ == '__main__':
    main()