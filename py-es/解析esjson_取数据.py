# -* - coding: UTF-8 -* -
#! /usr/bin/python
# 功能: 解析es返回的json,取出对应字段的数据,按照需要的格式输出到控制台

import re # 正则
import json # json

# 读文件
def loadFileString():
    # with能自动关闭文件对象
    with open('py-es/esjson.txt', mode='r',encoding='utf-8') as json_file:
        data = json.load(json_file)
    return data

# 拼字段
def printData(list):
    for item in list:
        print('{_mobile},{_id}'.format(_id=item["_source"]["id"], _mobile=item["_source"]["toClient"]))

# 主方法
def printFile():
    jsonData = loadFileString()
    printData(jsonData)

if __name__ == '__main__':
    printFile()