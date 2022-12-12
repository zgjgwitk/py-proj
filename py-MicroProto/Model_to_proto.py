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
    regexRule = r'\{[\s\S]+?\}'
    text = re.sub(regexRule, '', str) # 去掉 { get; set; }
    arr = text.split('\n')
    newArr = []

    for line in arr:
        newLine = line.strip()
        if newLine != 'set' and newLine != '}' and newLine != '[Ignore]' and newLine != '/// <summary>' and newLine != '/// </summary>' and newLine != '' and newLine.find('private ')==-1 and newLine.find('#region ')==-1 and newLine.find('#endregion')==-1 and newLine.find('[EncryptPropAttrbute(')==-1 and newLine.find('[Description(')==-1:
            newLine=newLine.replace('public ','').replace('///','//').replace('}','')
            newArr.append(newLine)

    return newArr

# 拼字段    
def loadField(prop, desc, idx):
    if '<int>' in prop:
        prop = prop.replace('<int>', '<int32>')
    elif '<decimal>' in prop:
        prop = prop.replace('<decimal>', '<double>')
    elif '<float>' in prop:
        prop = prop.replace('<float>', '<double>')
    elif '<long>' in prop:
        prop = prop.replace('<long>', '<int64>')
    elif '<Int64>' in prop:
        prop = prop.replace('<Int64>', '<int64>')
    elif '<Int16>' in prop:
        prop = prop.replace('<Int16>', '<int32>')
    elif '<short>' in prop:
        prop = prop.replace('<short>', '<int32>')
    elif '<DateTime>' in prop:
        prop = prop.replace('<short>', '<int32>')

    if 'int ' in prop:
        prop = prop.replace('int ', 'int32 ')
    elif 'decimal ' in prop:
        prop = prop.replace('decimal ', 'double ')
    elif 'float ' in prop:
        prop = prop.replace('float ', 'double ')
    elif 'long ' in prop:
        prop = prop.replace('long ', 'int64 ')
    elif 'Int64 ' in prop:
        prop = prop.replace('Int64 ', 'int64 ')
    elif 'Int16 ' in prop:
        prop = prop.replace('Int16 ', 'int32 ')
    elif 'short ' in prop:
        prop = prop.replace('short ', 'int32 ')
    elif 'DateTime ' in prop:
        desc = '[DateTime]'+desc
        prop = prop.replace('DateTime ', 'int64 ')
    elif 'DateTime? ' in prop:
        desc = '[DateTime?]'+desc
        prop = prop.replace('DateTime? ', 'string ')
    elif 'int? ' in prop:
        desc = '[int?]'+desc
        prop = prop.replace('int? ', 'string ')
    elif 'decimal? ' in prop:
        desc = '[decimal?]'+desc
        prop = prop.replace('decimal? ', 'string ')
    elif 'float? ' in prop:
        desc = '[float?]'+desc
        prop = prop.replace('float? ', 'string ')
    elif 'long? ' in prop:
        desc = '[long?]'+desc
        prop = prop.replace('long? ', 'string ')
    elif 'Int64? ' in prop:
        desc = '[Int64?]'+desc
        prop = prop.replace('Int64? ', 'string ')
    elif 'Int16? ' in prop:
        desc = '[Int16?]'+desc
        prop = prop.replace('Int16? ', 'string ')
    elif 'short? ' in prop:
        desc = '[short?]'+desc
        prop = prop.replace('short? ', 'string ')

    if 'List<' in prop:
        prop = prop.replace('List<', 'repeated ').replace('> ', ' ')

    return ('{_prop}={_idx};//{_desc}'.format(_prop=prop,_idx=idx,_desc=desc))

# 主方法
def printFile():
    text = loadFileString()
    arrLines = cleanText(text)
    idx = 0
    desc = ''
    for line in arrLines:
        if line.startswith('//'):
            if line.find('private ')>-1:
                desc = ''
                continue
            if line.find('public ')>-1:
                desc = ''
                continue
            desc += line.replace('//', '')
            continue

        idx+=1
        prop = loadField(line, desc, idx)
        desc = ''
        print(prop)


if __name__ == '__main__':
    printFile()