# -* - coding: UTF-8 -* -
#! /usr/bin/python
# 功能: 解析execl, 组装成 json 对象

import pandas as pd
import sys
import os
import re  # 正则
import json

def showCommentArr(x):
    # 获取评论字段
    comment = x['评论']
    
    # 删除首尾的 引号
    if comment.startswith('"') and comment.endswith('"'):
        comment = comment[1:-1]

    # 将表格中的['评论']字段解析为 json
    # list_obj = json.loads(comment.replace('\\"', '"').replace('\\\\u', '\\u'))
    try:
        list_obj = json.loads(comment.replace('\\"', '"').replace('\\\\u', '\\u'))
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from comment: {comment}. Error: {e}")
        return '[]'
    
    # 提取'content'字段并组合成字符串数组
    content_list = []
    for item in list_obj:
        try:
            content = item.get('content', '')
            if content:
                # 确保 content 是 Unicode 字符串
                if isinstance(content, str):
                    content_list.append(content)
                else:
                    print(f"Unexpected type for content: {type(content)}")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON object: {item}. Error: {e}")

    # 将内容组合成 JSON 字符串数组
    content_json_str = json.dumps(content_list, ensure_ascii=False)

    return content_json_str

# 加载 Excel 文件
source_file = 'kos/!file/评论.xlsx'
data = pd.read_excel(source_file, engine='openpyxl')

# 删除 comment 字段为空的记录
data_cleaned = data.dropna(subset=['评论'])

# 添加新列 '评论数据精简'
data.insert(loc=2, column='CommentArr', value='[]')

# 给 CommentArr 字段赋值, axis=1 表示按行读取
data['CommentArr'] = data.apply(showCommentArr, axis=1)

# 使用完 '评论' 列后, 就删除掉, 因为数据太大了
data.drop(columns=['评论'], inplace=True)

# 将每行数据转换为 JSON 对象并写入文件
output_json_file = 'kos/!file/data_as_json.json'
data_json_list = data.to_dict(orient='records')

# 确保输出文件所在的目录存在
output_dir = os.path.dirname(output_json_file)
if output_dir and not os.path.exists(output_dir):
    os.makedirs(output_dir, exist_ok=True)

# 将 JSON 对象列表写入文件
with open(output_json_file, 'w', encoding='utf-8') as json_file:
    json.dump(data_json_list, json_file, ensure_ascii=False, indent=4)

print(f"每行数据已保存为 JSON 对象到 {output_json_file}")