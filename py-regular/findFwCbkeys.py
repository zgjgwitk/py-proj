# -* - coding: UTF-8 -* -
#! /usr/bin/python
# re介绍 https://zhuanlan.zhihu.com/p/68014839
# 功能: 解析日志中的 fw & commonBusi 操作的 Raphael key

import numpy as np
import pandas as pd # Excel
import re # 正则
import time

# 读文件
def loadFileString():
    # with能自动关闭文件对象
    with open('py-regular/code.txt', mode='r',encoding='utf-8') as f:
        line = f.readline()
        while line:
            printRaphaelKey(line.strip())
            line = f.readline()

# 拼字段
def printRaphaelKey(line):
    regexRule = r'(\$N\=\>\S*\<\=\$)(\$K\=\>\S*\<\=\$)'
    pattern = re.compile(regexRule)
    mathcs = pattern.findall(line)
    for func in mathcs:
        print('{_name},{_key}'.format(_name=func[0].replace('$N=>','').replace('<=$',''), _key=func[1].replace('$K=>','').replace('<=$','')))

# 主方法
def printFile():
    loadFileString()

if __name__ == '__main__':
    printFile()