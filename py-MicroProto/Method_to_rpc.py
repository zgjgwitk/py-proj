# -* - coding: UTF-8 -* -
#! /usr/bin/python
# re介绍 https://zhuanlan.zhihu.com/p/68014839
# 功能: 将C# 的实体类转成契约的格式

import numpy as np
import pandas as pd # Excel
import re # 正则
import time

def loadFileString():
    f = open("py-MicroProto/code.txt","r",encoding='utf-8')             # 返回一个文件对象
    text = f.read()             # 调用文件的 readline()方法 
    # print(text)
    return text

# 过滤无效行数据
def cleanText(str):
    arr = str.split('\n')
    newArr = []

    for line in arr:
        newLine = line.strip()
        if (newLine.find('public ')==0) or (newLine.find('/// ')==0 and newLine != '/// <summary>' and newLine != '/// </summary>' and newLine != '' and newLine.find('/// <returns>')==-1 and newLine.find('/// </returns>')==-1 and newLine.find('/// <param')==-1 and newLine.find('/// </param')==-1):
            newLine=newLine.replace('///','//')
            newArr.append(newLine)
            #print(newLine)

    return newArr

# 拼字段    
def loadField(prop, desc):
    regexRule = r'public Task<(\w+)> (\w+)\s*\(\n?(\w+) request'
    pattern = re.compile(regexRule)
    mathcs = pattern.findall(prop)
    for func in mathcs:
        req = re.sub(r'Busi$','',func[2])
        resp = re.sub(r'Busi$','',func[0])
        print('rpc {_name}({_req}) returns ({_resp}) {{}}//{_desc}'.format(_name=func[1], _req=req, _resp=resp, _desc=desc))

# 主方法
def printFile():
    text = loadFileString()
    arrLines = cleanText(text)
    desc = ''
    for line in arrLines:
        if line.startswith('//'):
            desc += line.replace('//', '')
            continue
        
        prop = loadField(line, desc)
        desc = ''

if __name__ == '__main__':
    printFile()