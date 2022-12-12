# -* - coding: UTF-8 -* -
#! /usr/bin/python
# 功能: 将拼装的 es 加字段语句, 输出到 txt 文件中

import numpy as np
import pandas as pd
import time

def printConsole():
    result = 101
    for i in range(100):
        print('"Field%s":{"type": "integer"},' %(result + i))

    result = 201
    for i in range(100):
        print('"Field%s":{"type": "keyword"},' %(result + i))

def printFile():
    f = open('!writeFiles/log.txt','w')
    result = 101
    for i in range(100):
        f.writelines('"Field%s":{"type": "integer"},\n' %(result + i))

    result = 201
    for i in range(100):
        f.writelines('"Field%s":{"type": "keyword"},\n' %(result + i))
    
    f.close()

if __name__ == '__main__':
    printFile()