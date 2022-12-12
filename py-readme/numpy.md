[引用地址](https://blog.csdn.net/qq_42759120/article/details/125130389?spm=1001.2014.3001.5501)

Numpy库是Python进行科学计算的基础库，它是一个由多维数组对象组成，包含数学运算、逻辑运算、形状操作、排序、选择、I/O、离散傅里叶变换、基本线性代数、基本统计运算、随机模拟等功能。

说明文档：[NumPy 介绍 | NumPy 中文](https://www.numpy.org.cn/user/setting-up.html#%E4%BB%80%E4%B9%88%E6%98%AF-numpy)

如果本文没有介绍到的，或者有不会的，看不懂的，可以百度，或查看说明文档。

### 0.numpy读取文件

NumPy的文件读/写主要有二进制的文件读/写和文件列表形式的数据读/写两种形式。NumPy还提供了许多从文件读取数据并将其转换为数组的方法。

#### 0.1文本文件的读写

结构化、纯数值型的数据，并且主要用于矩阵计算、数据建模的，使用Numpy的loadtxt更方便。

``` python
import numpy as np
# 1.savetxt函数：可将数组写到以某种分隔符隔开的文本文件中
# np.savetxt(fname, X, fmt='%.18e', delimiter=' ', newline='\n',header='',footer='', comments='# ')
# fname：文件名，可以是.gz 或.bz2 的压缩文件
# X：存入文件的数组（一维数组或者二维数组）,只能处理 1维和2维数组。可以用于CSV格式文本文件
# fmt：写入文件的格式，如：%d，%.2f，%.18e，默认值是%.18e 可选项
# delimiter: 分隔符，通常情况是str可选
# header:将在文件开头写入的字符串
# footer:将在文件尾部写入的字符串
# comments： 将附加到header和footer字符串的字符串，以将其标记为注释。
# encoding:用于编码输出文件的编码。
arr = np.arange(0,12).reshape(4,-1)
np.savetxt("arr.csv", arr, fmt="%d", delimiter=",")#fmt ="%d"为指定保存为整数。arr.txt文件也可以
#写入的时候指定逗号分割，则读取的时候也要指定逗号分割
 
# 2.loadtxt函数：读取文件
# loadtxt(fname, dtype=float, comments='#', delimiter=None,converters=None, skiprows=0,
#       usecols=None, unpack=False,ndmin=0, encoding='bytes', max_rows=None, *, like=None)
# filename：文件名；
# dtype：数据类型（可选），表示文件字符串以什么数据类型读入数组中，默认为float；
# comment: 如果行的开头为#就会跳过该行
# delimiter：分隔字符串，写入参数后，默认为将任何空格都改为逗号；
# converters： 对读取的数据进行预处理
# skiprows：跳过前N行，一般跳过第一行表头；
# usecols：读取指定的列、索引、元组类型；
# unpack：默认为False。如果True，读入属性将分别写入不同的数组变量，False读入数据只写入一个数组变量；
# encoding：对读取的文件进行预编码
#写入的时候指定逗号分割，则读取的时候也要指定逗号分割
loaded_data = np.loadtxt("arr.csv",delimiter=",")# arr.txt文件也可以。csv一定时逗号分隔符
#读取失败，查看csv文件中是不是有字符，需要指定dtype或者设置skiprows
print('读取的数组为：',loaded_data)
t1 = np.loadtxt("arr.csv", dtype=str, delimiter=",", skiprows=1, usecols=[0,2])
# 使用逗号分隔，输出除第一行以外其他行的第一二三列数据；
print(t1)
 
# 3.genfromtxt函数：读取二进制文件
# genfromtxt函数和loadtxt函数相似，不过它面向的是结构化数组和缺失数据。
# 它通常使用的参数有3个，即存放数据的文件名参数fname、用于分隔的字符参数delimiter和是否含有列标题参数names。
arr = np.array([['0','','2'], ['3','4',''], ['','7','8'], ['9','10','11']])
np.savetxt("arr.csv", arr, fmt='%s', delimiter=",")
print(arr)
# [['0' '' '2']
#  ['3' '4' '']
#  ['' '7' '8']
#  ['9' '10' '11']]
filling_values1 = (111, 222, 333)
t2 =np.genfromtxt("arr.csv", delimiter=',', filling_values=filling_values1)
print(t2)
# [[  0. 222.   2.]
#  [  3.   4. 333.]
#  [111.   7.   8.]
#  [  9.  10.  11.]]
```

#### 0.2二进制文件的读写

对于二进制的数据处理，使用Numpy的load和fromfile方法更为合适。

``` python
import numpy as np  #导入NumPy库
# 1.save函数：将一个numpy数组保存为二进制文件,以二进制的格式保存数据。
# save函数的语法格式为：numpy.save(file, arr, allow_pickle=True, fix_imports=True)。
# 参数file:为要保存的文件的名称，需要指定文件保存的路径，如果未设置，则保存到默认路径下面；
# 参数arr:为需要保存的数组。其文件的扩展名.npy是系统自动添加的。
arr1 = np.arange(9).reshape(3,3)  #创建一个数组
np.save("save_arr",arr1)  #保存数组
# 2.savez函数：将多个numpy数组保存为二进制文件
# 如果将多个数组保存到一个文件中，可以使用savez函数，其文件的扩展名为.npz。
# savez函数的语法格式为：numpy.savez(file, *args, **kwds)。
# file：要保存的文件，扩展名为.npz，如果文件路径末尾没有扩展名.npz，该扩展名会被自动加上。
# args: 要保存的数组，可以使用关键字参数为数组起一个名字，非关键字参数传递的数组会自动起名为 arr_0, arr_1, …　。
# kwds: 要保存的数组使用关键字名称。
arr2 = np.arange(0,1.0,0.5)
np.savez('savez_arr',arr1,kwds=arr2)    #kwds是保存文件的名称
#可以找到保存的文件，解压打开看看
 
# 3.load函数：读取二进制文件
# load函数的格式为：numpy.load(file, mmap_mode=None, allow_pickle=True, fix_imports=True, encoding=’ASCII’)
# npy文件读取的结果为numpy数组对象ndarray。
# npz文件读取的结果为类字典对象，如果在savez函数中未指定键时，自动使用 arr_0, arr_1, …等键名称。
# mmap_mode: {None, ‘r+’, ‘r’, ‘w+’, ‘c’};：读取文件的方式。
# allow_pickle=True：允许加载存储在.npy文件中的pickled对象数组。
# fix_imports=True：若为True，pickle将尝试将旧的python2名称映射到python3中使用的新名称。
# encoding='ASCII'：制定编码格式，默认为“ASCII”。
 
loaded_data = np.load("save_arr.npy")  #读取含有单个数组的文件
print('读取的数组为：\n',loaded_data)
 
loaded_data1 = np.load("savez_arr.npz")  #读取含有多个数组的文件
print('读取的数组1为：',loaded_data1['arr_0'])
print('读取的数组2为：',loaded_data1['kwds'])
```

 fromfile方法可以读取简单的文本数据或二进制数据，数据来源于tofile方法保存的二进制数据。读取数据时需要用户指定元素类型，并对数组的形状进行适当的修改。

``` python
import numpy as np
x = np.arange(9).reshape(3,3)
x.tofile('test.bin')
np.fromfile('test.bin',dtype=np.int)
# out:array([0, 1, 2, 3, 4, 5, 6, 7, 8])
```

### 1.数组的创建

``` python
import numpy as np
# 1.数组的创建
a=np.array([1,2,3],dtype=int) #创建一维数组，可指定元素类型
b=np.array([[1,2,3],[4,5,6]]) #创建二维数组
print(a)# [1 2 3]
print(b)
# [[1 2 3]
#  [4 5 6]]
a=np.arange(10)#默认从0开始
print(a)#[0 1 2 3 4 5 6 7 8 9]
a=np.arange(1,10)#左闭右开区间
print(a)#[1 2 3 4 5 6 7 8 9]
a=np.arange(1,10,2)#指定步幅为2
print(a)#[1 3 5 7 9]
a=np.linspace(1, 2, 5)#指定起止值，创建指定个数的等差一维数组
print(a)#[1.   1.25 1.5  1.75 2.  ]
 
a = np.zeros(3)	#创建一个只包含0的数组，列数为3，行数缺省为1
a=np.zeros((2,3))#创建一个m行n列的全0数组
print(a)
# [[0. 0. 0.]
#  [0. 0. 0.]]
a=np.ones((2,3))#创建一个m行n列的全1数组
print(a)
# [[1. 1. 1.]
#  [1. 1. 1.]]
 
z = np.empty(4)	#在内存中创建一个空数组，以备之后填入数据。
print(z)	#[2.95792101e-272 1.02380627e-306 3.96786093e-301 8.71907139e-301] 好像是随机创建的内容，没用
 
z = np.identity(2)#使用np.identity或者np.eye函数,创建单位矩阵
print(z)
# [[1. 0.]
#  [0. 1.]]
 
# 使用np.array函数，Python的列表，元组等也能转换为Numpy数组
a = np.array([10, 20]) # 使用列表构建数组
print(a)#[10 20]
b = np.array((10, 20), dtype=float) # 使用元组构建数组
print(b)#[10. 20.]
c = np.array([[1, 2], [3, 4]]) # 使用列表嵌套列表构建数组
print(c)
# [[1 2]
#  [3 4]]
 
# np.random.rand(m,n)或者np.random.random((m,n)
# 创建m行n列，由0-1的随机数构成的数组，注意后者传入的参数是一个元组
a=np.random.rand(2,3)#(3)也可以，行数缺省为1
print(a)
a=np.random.random((2,3))#((3))也可以，行数缺省为1
print(a)
# [[0.39640904 0.70625911 0.41037923]
#  [0.65263409 0.63491374 0.66204204]]
a = np.random.randint(0,3,(2,3))  #创建2行3列的二维数组，范围在[0-3)之间
print(a)
a=np.random.rand(2,3,4)#3维矩阵
print(a)
# [[[0.11838695 0.22200378 0.71420386 0.50389581]
#   [0.3725528  0.28242966 0.31213826 0.05534031]
#   [0.53484771 0.69017367 0.67676519 0.17627573]]
#
#  [[0.65290297 0.8464174  0.76181375 0.98847299]
#   [0.91528719 0.61851361 0.90388327 0.30164545]
#   [0.52912919 0.86626941 0.25378109 0.83821525]]]
```

### 2.数组间的增删改

``` python
import numpy as np
a = np.arange(9)
b = np.arange(3)
c=np.append(a,b)    #追加数据
print(c)#[0 1 2 3 4 5 6 7 8 0 1 2]
a=np.insert(a,1,5)  #插入数据
print(a)#[0 5 1 2 3 4 5 6 7 8]
b=np.delete(b,[0,1])#删除数据,也可以只删除一个数据
print(b)#[2]
 
a=np.insert(a,[1,2],5)  #插入数据，在原数组的2个位置插入同一个数据
print(a)#[0 5 5 5 1 2 3 4 5 6 7 8]
a=np.insert(a,[1,2],[5,6])  #插入数据，在原数组的2个位置插入2个不同的数据
print(a)#[0 5 5 6 5 5 1 2 3 4 5 6 7 8]
```

### 3.数组的堆叠和拆分

``` python
import numpy as np
#3.数组的堆叠和拆分
a=np.array([0,1,2,3])#单独的[0,1,2,3]是列表
b=np.array([10,11,12,13])
c=np.vstack((a,b))#行堆叠,a和b数组的个数要一样
print(c)
# [[ 0  1  2  3]
#  [10 11 12 13]]
a=np.array([0,1,2,3])
b=np.array([10,11,12])
c=np.hstack((a,b))#列堆叠,a和b数组的个数可以不一样
print(c)#[ 0  1  2  3 10 11 12]
 
# 拆分
a=np.array([[0,1,2],
   [3,4,5],
   [6,7,8]])
b=np.vsplit(a,3)#按行拆分成3等分
print(b)#[array([[0, 1, 2]]), array([[3, 4, 5]]), array([[6, 7, 8]])]
b,c,d=np.vsplit(a,3)
print(c)#[[3 4 5]]
 
b=np.vsplit(a,(2,)) #从第2行后面进行拆分
print(b)
# [array([[0, 1, 2],
#        [3, 4, 5]]), array([[6, 7, 8]])]
b,c=np.vsplit(a,(2,))
print(b)
# [[0 1 2]
#  [3 4 5]]
b=np.hsplit(a,3) #按列拆分成3等
print(b)
# [array([[0],
#        [3],
#        [6]]), array([[1],
#        [4],
#        [7]]), array([[2],
#        [5],
#        [8]])]
 
a=np.array([[0,1,2,10],
   [3,4,5,10],
   [6,7,8,10]])
 
b=np.hsplit(a,(1,3)) #分别从第二列和第3列后进行拆
print(b)
# [array([[0],
#        [3],
#        [6]]), array([[1, 2],
#        [4, 5],
#        [7, 8]]), array([[10],
#        [10],
#        [10]])]
```

### 4.运算

``` python
import numpy as np
# 4.运算
a = np.array([1,2,7,8])
b = np.array([5,6,3,2])
print(a + 10)# 对每个元素添加一个标量：[11 12 17 18]
print(a * 10)# 对每个元素乘一个标量：[10 20 70 80]
print(a+b)#[ 6  8 10 10]
print(a-b)#[-4 -4  4  6]
print(a*b)#[ 5 12 21 16]
print(a/b)#[0.2        0.33333333 2.33333333 4.        ]
print(a//b)#除后结果向下取整：[0 0 2 4]
print(a%b)#[1 2 1 0]
print(a**b)#代表乘方:[  1  64 343  64]
# 比较运算：==，<,<=,>,>=,!= 数组中每个元素都进行相应比较，返回bool值组成的数组
print(a==2)#[False  True False False]
# 逻辑运算：逻辑与（&）,逻辑或（|）
print((a>3)&(a<10))#[False False  True  True]
print(a @ b)# 两个矩阵相乘:54
```

### 5.索引和切片

``` python
import numpy as np
#5.索引和切片
#一维数组
a = np.arange(10)
print(a)#[0 1 2 3 4 5 6 7 8 9]
print(a[0])#0
print(a[-1])#索引倒数第i个元素：9
print(a[0:8])#x[m:n],m到n-1的数据：[0 1 2 3 4 5 6 7]
print(a[0:8:2])#指定步幅为i：[0 2 4 6]
print(a[::-1])#反转数组：[9 8 7 6 5 4 3 2 1 0]
# 多维数组
z = np.array([[1, 2], [3, 4]])
print(z)
# [[1 2]
#  [3 4]]
print(z[0])#第一行：[1 2]
print(z[0, :])#第一行：[1 2]
print(z[:, 1])#第二列：[2 4]
print(z[0:2, 0])#前2行第1个数：[1 3]
print(z[0,0])#第1行第1个数：1
 
#索引数组
#单个索引数组
a = np.linspace(2,20,10,dtype=int)
print(a)#[ 2  4  6  8 10 12 14 16 18 20]
print(a[[1,2,3,4]])##传入列表索引和一维数组索引等效:[ 4  6  8 10]
print(a[np.array([1,2,3,4])])# #索引数组为一维数组：[ 4  6  8 10]
print(a[np.array([[1,2],[3,4]])])
##索引数组为二维数组：[[1,2],[3,4]]，那么x[[[1,2],[3,4]]] 结果为[[x[1],x[2]],[x[3],x[4]]]
# [[ 4  6]
#  [ 8 10]]
 
a=np.array([[1,2],[3,4]])
b=np.array([[1,1],[0,1]])
print(a[b])#[[第2行，第2行],[第1行，第2行]]
# [[[3 4]
#   [3 4]]
#
#  [[1 2]
#   [3 4]]]
 
# 多个索引数组： 为多个维度提供索引，每个维度的索引数组必须具有相同的形状。
a = np.arange(16).reshape(4,4)
i = np.array([[0,1],[2,3]])
j = np.array([[2,1],[3,3]])
print(a)
# [[ 0  1  2  3]
#  [ 4  5  6  7]
#  [ 8  9 10 11]
#  [12 13 14 15]]
print(a[i,:])#[[第1行，第2行][第3行，第4行]]
# [[[ 0  1  2  3]
#   [ 4  5  6  7]]
#
#  [[ 8  9 10 11]
#   [12 13 14 15]]]
print(a[i,[2]])#[[第1行第3个，第2行第3个][第3行第3个，第4行第3个]]
# [[ 2  6]
#  [10 14]]
print(a[i,[2,1]])#[[第1行第3个，第2行第2个][第3行第3个，第4行第2个]]
# [[ 2  5]
#  [10 13]]
print(a[i,j])#[[第1行第3个，第2行第2个][第3行第4个，第4行第4个]]
# [[ 2  5]
#  [11 15]]
# print(a[np.array([[0,1],[2,3]]),np.array([[2,1],[3,3]])])
#从输出结果中可以看出，其实就是上一行中第1个array和第2个array中一一对应，每一个代表a[x,y]对应的数据
#   [[a[0][2],a[1][1]]
#   [a[2][3],a[3][3]]]
 
a = np.indices((2,3)) #创建一个3维数组
print(a)
# [[[0 0 0]
#   [1 1 1]]
#
#  [[0 1 2]
#   [0 1 2]]]
print(a[np.array([0,1]),np.array([0,1])] )#对前两个维度进行索引，结果相当于np.array([a[0][0],a[1][1]])
# [[0 0 0]
#  [0 1 2]]
print(a[np.array([0,1]),np.array([0,1]),np.array([1,2])] )#对3个维度分别索引,结果相当于np.array(a[0][0][1],a[1][1][2])
# [0 2]
 
#索引数组和整数相结合:将整数理解为和索引数组等长的以该整数为元素的数组
 
a = np.array([[1,2,3],[2,3,4],[3,4,5]])
print(a)
# [[1 2 3]
#  [2 3 4]
#  [3 4 5]]
print(a[np.array([1,2]),2])#[4 5]
print(a[np.array([1,2]),np.array([2,2])])#[4 5]
print(a[1,np.array([1,2])])#[3 4]
print(a[[1,1],np.array([1,2])])#[3 4]
# 布尔索引:与原始数组具有相同形状的布尔数组:在获取元素的时候，只返回索引值为True的元素所组成的数组，其它元素舍弃
a = np.array([[1,2,3],[2,3,4],[3,4,5]])
b = a > 3
print(b)
# [[False False False]
#  [False False  True]
#  [False  True  True]]
print(a[b]) #返回a中大于3的元素所组成的数组
# [4 4 5]
a[b] = 0 #赋值，只对索引数组中元素为True的位置进行赋值
print(a)
# [[1 2 3]
#  [2 3 0]
#  [3 0 0]]
# 对于数组的每个维度，给出一个一维布尔数组以及想要的切片。 请注意，一维布尔数组的长度必须与要切片的尺寸（或轴）的长度一致
a = np.arange(15).reshape((3,5))
print(a)
# [[ 0  1  2  3  4]
#  [ 5  6  7  8  9]
#  [10 11 12 13 14]]
b1 = np.array([True,False,True])
b2 = np.array([True, False, True, False, True])
print(a[b1,:])# 布尔类型的数据也可用于提取元素
# [[ 0  1  2  3  4]
#  [10 11 12 13 14]]
print(a[:,b2])
# [[ 0  2  4]
#  [ 5  7  9]
#  [10 12 14]]
z=np.arange(5)
d = np.array([0, 1, 1, 0, 0], dtype=bool)#也可以这样强制转换一下
print(d)#[False  True  True False False]
print(z[d])#[1 2]
# 当数组有多维时，选取一部分可以使用 ... 替代多个 : : :，如下面的语句等价：
a = np.arange(24).reshape((2, 3, 4))
print(a[1, ...])#...可以放前面也可以放后面
print(a[1, :, :])
# [[12 13 14 15]
#  [16 17 18 19]
#  [20 21 22 23]]
```

### 6.常用属性

``` python
import numpy as np
# 6.常用属性
a = np.arange(15).reshape((3,5))
print(a)
# [[ 0  1  2  3  4]
#  [ 5  6  7  8  9]
#  [10 11 12 13 14]]
print(a.ndim)#数组的轴（维度）的个数:2
print(a.shape)#数组的维度,对于m行n列的矩阵数组，返回的是(m,n):(3, 5)
print(a.size)#数组中所有元素的个数，等于shape的元素的乘积:15
print(a.dtype)#数组中元素类型的对象:int32
print(a.dtype.name)#数组中元素类型名称:int32
print(a.itemsize)#数组中每个元素的字节大小，比如元素类型为int64的数组，每个元素的字节大小为64/8=8个字节:4
 
print(a.T)#转置操作，不修改原数组:
print(np.transpose(a))两种方法都是转置矩阵
# [[ 0  5 10]
#  [ 1  6 11]
#  [ 2  7 12]
#  [ 3  8 13]
#  [ 4  9 14]]
 
a = np.arange(15)
print(type(a)) # <class 'numpy.ndarray'>
# 常见的数据类型包括：1. float64: 64 位浮点型数字，2. int64: 64 位整数型数字，3. bool: 8 位 True 或者 False。通常来说，默认的数据类型为float64。
print(type(a[0]))#<class 'numpy.int32'>
print(a.shape)#(15,)只有1行，所以只显示个数
print(a.data)#包含实际数组元素的缓冲区地址:<memory at 0x0000014BF739D240>
print(a.flat)#数组元素的透代器:<numpy.flatiter object at 0x0000014BF6C7F9C0>
```

### 7.常用方法

``` python
import numpy as np
#7.常用方法：在9.补充里面还有一些补充函数
a = np.arange(15) #创建一个一维数组
print(a)#[ 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14]
print(a.tolist()) #转成python列表形式 :[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
a.astype(float)#转换数组元素类型为float类型:
print(a.astype(float))#[ 0.  1.  2.  3.  4.  5.  6.  7.  8.  9. 10. 11. 12. 13. 14.]
#修改数组形状:reshape不会修改原数组,resize会修改原数组
b = a.reshape(3,5) #修改数组为3行5列的二维数组
#b = a.reshape(3,-1) -1是模糊控制的意思，固定另一个，自行确定-1所在的行或列
print(b)
# [[ 0  1  2  3  4]
#  [ 5  6  7  8  9]
#  [10 11 12 13 14]]
print(a) #reshape后，没有修改原数组:[ 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14]
a.resize(3,5) #resize修改了原数组
print(a)
# [[ 0  1  2  3  4]
#  [ 5  6  7  8  9]
#  [10 11 12 13 14]]
 
a = np.array((4, 3, 2, 1))
print(a)
print("sort =",a.sort())   # 对数组a进行排序，
print("sort =",a.sort(axis=0))#按列进行排序，axis=1按行进行排序
print("sum =",a.sum())  # 对数组a进行求和
print("mean =",a.mean())   # 求出数组a的均值
print("max =",a.max())   # 求出数组a的最大值
print("min =",a.min())   # 求出数组a的最小值
print("argmax =",a.argmax())   # 返回最大元素的索引
print("argmin =",a.argmin())   # 返回最小元素的索引
print("cumsum =",a.cumsum())   # 对每个元素累积求和：[ 1  3  6 10]
print("cumprod =",a.cumprod())    # 对每个元素累积求积：[ 1  2  6 24]
print("var =",a.var())  # 求数组a的方差
print("std =", a.std())   # 求数组a的标准差
a.shape = (2, 2)#a=a.reshape(2,2)
print(a)
# [[1 2]
#  [3 4]]
print(a.max(axis=1))   # axis=1，按行求最大(小)值 [2 4]
print(a.max(axis=0))   # axis=0，按列求最大(小)值 [3 4]
print(a.argmax(axis=1))# axis=1，按行求最大(小)值所对应的索引值 [1 1]
print(a.argmax(axis=0))# axis=1，按列求最大(小)值所对应的索引值 [1 1]
 
#将数组降维成一维数组：ravel和flatten都不会修改原数组
b=a.ravel() #降维成一维数组:[1 2 3 4]
b=a.flatten() #降维成一维数组:#ravel（）和flatten（）都没有修改原数组
print(b)#[1 2 3 4]
 
# Numpy数组中也存在深拷贝和浅拷贝的区别:
# 深拷贝即再内存中新建一个数据副本，两个数组内存地址不同，可以分别修改，浅拷贝即不在内存中新建地址，仅仅引用之前的地址，两个数组内存地址相同，只能同时修改
c = np.copy(b)	# 深拷贝
c[0] = 0
print(b)#[1 2 3 4]
print(c)#[0 2 3 4]
c = b		# 浅拷贝
c = b.view()# 浅拷贝
c[0] = 0
print(b)#[0 2 3 4]
```

### 8.结构化数组

#### 8.1具体用法

``` python
import numpy as np
# 8.结构化数组
# 字典有两个关键字: names, formats，关键字的名称不可改变，每个关键字对应的值都是一个列表。
persontype = np.dtype({
    'names': ['name', 'age', 'weight'],
    'formats': ['S32', 'i', 'f']})
# names定义结构中的每个字段名，而formats则定义每个字段的类型:
# S32 : 32个字节的字符串类型，由于结构中的每个元素的大小必须固定，因此需要指定字符串的长度
# i: 32bit的整数类型，相当于np.int32
# f: 32bit的单精度浮 点数类型，相当于np.float32
 
students = np.array([("zhangsan", 32, 75),("wangwu", 28, 85,), ("wangmazi", 29, 65)],dtype=persontype)
ages = students[:]['age']
print(np.mean(ages))#29.666666666666668
print(students.dtype)#[('name', 'S32'), ('age', '<i4'), ('weight', '<f4')]
print(students.shape)#(3,)
print(students)#[(b'zhangsan', 32, 75.) (b'wangwu', 28, 85.) (b'wangmazi', 29, 65.)]
```

#### 8.2结构化数据类型创建的4种方法

``` python
import numpy as np
# 结构化数据类型创建
# 结构化数据类型主要由字段名称、数据类型、偏移量三部分组成。
# 方法1：元组列表形式
a=np.dtype([("address","S5"),("family","U10",(2,2))])
print(a)#[('address', 'S5'), ('family', '<U10', (2, 2))]
# 每一个元组表示一个字段的，形式如(name,datatype,shape)
# 元组中的shape 字段是可选字段，datatype可以定义为任何类型
 
# 方法2：以逗号分隔
a=np.dtype("i8,S4,(5,3)f4")
print(a)#[('f0', '<i8'), ('f1', 'S4'), ('f2', '<f4', (5, 3))]
# 字段中name系统自动生成如：f0,f1等形式,字段中的偏离量系统自动确认
 
# 方法3：以字典形式表示各参数
# 以Python 字典 key-value 形式定义每个字段参数类型
a=np.dtype({"names":["name","age"],"formats":["S6","i4"]})
print(a)#[('name', 'S6'), ('age', '<i4')]
a=np.dtype({"names":["name","age"],"formats":["S6","i4"],"offsets":[2,3],"itemsize":12})
print(a)#{'names': ['name', 'age'], 'formats': ['S6', '<i4'], 'offsets': [2, 3], 'itemsize': 12}
# 字典形式定义字段形式如：{"name":[],"formats":[],"offsetd":[],"itemsize"：}
# name 代表：长度相同的字段名称列表
# formats 代表： dtype基本格式列表
# offsets: 偏移量列表，可选字段。
# itemsize： 描述dtype总大小，可选字段
# 字典形式表示字段内容，可以允许控制字段偏离量和itemsize大小
 
# 方法4：以字典形式表示字段名称
a=np.dtype({"name":("S6",0),"age":("i8",1)})
# dtype({'names':['name','age'], 'formats':['S6','<i8'], 'offsets':[0,1], 'itemsize':9})
print(a)#{'names': ['name', 'age'], 'formats': ['S6', '<i8'], 'offsets': [0, 1], 'itemsize': 9}
```

#### 8.3numpy 支持的数据类型

数据类型|内置码|意义
:- | :- | :-
int8    |i1|字节（-128 to 127）
int16   |i2|整数,16位字节
int32   |i4|整数,32位字节
int64   |i8|整数,64位字节
float16 |f2|浮点型，16位字节
float32 |f4|浮点型，32位字节
float64 |f8|浮点型，64位字节
bool_   |b |布尔类型
Unicode |U |Unicode编码
String  |S |字符串

### 9.补充

#### 9.1补充函数

函数|说明
:- | :-
np.full(shape,val)|根据shape生成一个数组，每个元素值都是val
np.eye(n)|创建一个正方的n*n单位矩阵，对角线为1，其余为0
np.ones_like(a)|根据数组a的形状生成一个全1数组
np.zeros_like(a)|根据数组a的形状生成一个全0数组
np.full_like(a,val)|根据数组a的形状生成一个数组，每个元素值都是val
np.concatenate()|将两个或多个数组合并成一个新的数组
np.swapaxes(ax1,ax2)|将数组n个维度中两个维度进行调换
np.abs(x) np.fabs(x)|计算数组各元素的绝对值
np.sqrt(x)|计算数组各元素的平方根
np.square(x)|计算数组各元素的平方
np.log(x) np.log10(x) np.log2(x)|计算数组各元素的自然对数(e)、10底对数和2底对数
np.ceil(x) np.floor(x)|ceil:计算数组各元素大于或等于每个元素的最小值<br />floor:计算数组各元素小于或等于每个元素的最大值
np.rint(x)|计算数组各元素的四舍五入值
np.modf(x)|将数组各元素的小数和整数部分以两个独立数组形式返回
np.cos(x) np.cosh(x) np.sin(x) np.sinh(x) np.tan(x) np.tanh(x)|计算数组各元素的普通型和双曲型三角函数
np.exp(x)|计算数组各元素的指数值
np.sign(x)|计算数组各元素的符号值，1(+), 0, ‐1(‐)
np.maximum(x,y) np.fmax() np.minimum(x,y)np.fmin()|元素级的最大值/最小值计算
np.mod(x,y)|元素级的模运算
np.copysign(x,y)|将数组y中各元素值的符号赋值给数组x对应元素
np.abs(x)|计算基于元素的整形，浮点或复数的绝对值。
np.dot(a,b),np.dot(b,a)<br />a.dot(b),b.dot(a)|dot返回的是2个数组的点积，如果是一维数组，则是两数组的内积，如果是二维数组，则是矩阵积，dot（a,b）和dot(b,a)的结果不一样,dot（a,b）和a.dot(b)结果一样
np.median(a)|求数组a的中位数
np.corrcoef(a)|皮尔逊积矩相关系数（）

#### 9.2.np.random的随机函数

函数|说明
:- | :-
rand(d0,d1,..,dn)|根据d0‐dn创建随机数数组，浮点数，[0,1)，均匀分布
randn(d0,d1,..,dn)|根据d0‐dn创建随机数数组，标准正态分布
randint(low[,high,shape])|根据shape创建随机整数或整数数组，范围是[low, high)
seed(s)|随机数种子，s是给定的种子值
函数|说明
shuffle(a)|根据数组a的第1轴进行随排列，改变数组x
permutation(a)|根据数组a的第1轴产生一个新的乱序数组，不改变数组x
choice(a[,size,replace,p])|从一维数组a中以概率p抽取元素，形成size形状新数组 replace表示是否可以重用元素，默认为False
函数|说明
uniform(low,high,size)|产生具有均匀分布的数组,low起始值,high结束值,size形状
normal(loc,scale,size)|产生具有正态分布的数组,loc均值,scale标准差,size形状
poisson(lam,size)|产生具有泊松分布的数组,lam随机事件发生率,size形状

#### 9.3补充

函数|说明
:- | :-
sum(a, axis=None)|根据给定轴axis计算数组a相关元素之和，axis整数或元组
mean(a, axis=None)|根据给定轴axis计算数组a相关元素的期望，axis整数或元组
average(a,axis=None,weights=None)|根据给定轴axis计算数组a相关元素的加权平均值
std(a, axis=None)|根据给定轴axis计算数组a相关元素的标准差
var(a, axis=None)|根据给定轴axis计算数组a相关元素的方差
unravel_index(index, shape)|根据shape将一维下标index转换成多维下标
ptp(a)|计算数组a中元素最大值与最小值的差
median(a)|计算数组a中元素的中位数（中值）
np.gradient(f)|计算数组f中元素的梯度，当f为多维时，返回每个维度梯度

#### 9.4 函数indices

``` python
import numpy as np
# np.indices的作用就是返回一个给定形状数组的序号网格数组，可以用于提取数组元素或对数组进行切片使用。
x = np.arange(20).reshape((5, 4))
dense_grid = np.indices((2, 3))  # 返回一个2x3网格序列,密集分布，每个行号和列号一一对应，表示一个位置的元素。
sparse_grid = np.indices((2, 3), sparse=True)  # 返回一个松散排布的2x3网格的行分布和列分布元组,行号和列号不是一一对应，一个行号对应多个列号。
 
print("x:\n", x)
print("x.shape:", x.shape)
 
print("================================")
 
print("dense_grid:\n", dense_grid)
print("================================")
print("行序号:\n", dense_grid[0])
print()
print("列序号:\n ", dense_grid[1])
print("\n")
print("切片效果:\n", x[dense_grid[0], dense_grid[1]])  # 等效于x[:2,:3]切片效果
 
print("================================")
print("sparse_grid:\n", sparse_grid)
print("================================")
 
print("切片效果: \n", x[sparse_grid])  # 等效于x[:2,:3]切片效果
```