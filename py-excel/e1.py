# -* - coding: UTF-8 -* -
#! /usr/bin/python

import numpy as np
import pandas as pd

l = [0,1,7,9,np.NAN,None,1024,512]
# ⽆论是numpy中的NAN还是Python中的None在pandas中都以缺失数据NaN对待
s1 = pd.Series(data = l) # pandas⾃动添加索引
s2 = pd.Series(data = l,index = list('abcdefhi'),dtype='float32') # 指定⾏索引
# 传⼊字典创建，key⾏索引
s3 = pd.Series(data = {'a':99,'b':137,'c':149},name = 'Python_score')
display(s1,s2,s3)