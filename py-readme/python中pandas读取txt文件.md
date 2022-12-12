# 语法：pandas.read_table()

#### 参数：

filepath_or_buffer 文件路径或者输入对象
 sep 分隔符，默认为制表符
 names 读取哪些列以及读取列的顺序，默认按顺序读取所有列
 engine 文件路径包含中文的时候，需要设置engine = ‘python’
 encoding 文件编码，默认使用计算机操作系统的文字编码
 na_values 指定空值，例如可指定null,NULL,NA,None等为空值

#### 常见错误：设置不全

``` python
    import pandas
    data = pandas.read_table('D/anaconda/数据分析/文本.txt',
    engine='python')
    print(data)
```

#### 补全代码

``` python
    import pandas
    data = pandas.read_table('D/anadondas/数据分析/文本.txt',
    sep = ',' ,#指定分隔符','，默认为制表符
    names = ['names','age'],#设置列名，默认将第一行数据作为列名
    engine = 'python',
    encoding = 'utf8'#指定编码格式)
    print(data)
```
