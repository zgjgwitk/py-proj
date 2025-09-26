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
        if (newLine.find('public ')==0) or (newLine.find('/// ')==0 and newLine != '/// <summary>' and newLine != '/// </summary>' and newLine != '' and newLine.find('/// <returns>')==-1 and newLine.find('/// </returns>')==-1 and newLine.find('/// <param')==-1 and newLine.find('/// </param')==-1 and newLine.find('#')==-1 and newLine.find('{')==-1 and newLine.find('}')==-1):
            newLine=newLine.replace('///','//')
            newArr.append(newLine)
            #print(newLine)

    return newArr

# 拼字段    
def loadField(prop, desc):
    regexRule = r'public (async)? Task<(\w+)> (\w+)\s*\(\n?(\w+) request'
    pattern = re.compile(regexRule)
    mathcs = pattern.findall(prop)
    msgClassString = ''
    for func in mathcs:
        req = re.sub(r'Busi$','',func[3])
        resp = re.sub(r'Busi$','',func[1])
        print('rpc {_name}({_req}) returns ({_resp}) {{}}//{_desc}'.format(_name=func[2], _req=req, _resp=resp, _desc=desc))
        
        msgClassString += '//{_desc}-请求实体\n'.format(_desc=desc)
        msgClassString += 'message {_req} {{\n}}\n'.format(_req=req)
        msgClassString += '//{_desc}-响应实体\n'.format(_desc=desc)
        msgClassString += 'message {_resp} {{\n'.format(_resp=resp)
        msgClassString += '    bool IsError=1;// 是否错误\n'
        msgClassString += '    int32 ErrorCode=2;// 错误编码\n'
        msgClassString += '    string ErrorMsg=3;// 错误信息\n'
        msgClassString += '}\n'
    
    return msgClassString + '\n'

# 主方法
def printFile():
    text = loadFileString()
    arrLines = cleanText(text)
    desc = ''
    allmsgClass = ''
    for line in arrLines:
        if line.startswith('//'):
            desc += line.replace('//', '')
            continue
        
        allmsgClass += loadField(line, desc)
        desc = ''
    print('\n')
    print(allmsgClass)

if __name__ == '__main__':
    printFile()