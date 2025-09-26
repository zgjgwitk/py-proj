# -* - coding: UTF-8 -* -
#! /usr/bin/python
# 功能: 处理文件的相关帮助类

import json # json
import os

# 读文件转为json
def loadFileToJson():
    """
    读文件转为json。
    
    参数:
    
    返回:
    data: JSON对象
    """
    # with能自动关闭文件对象
    with open('py-json/json_file.json', mode='r',encoding='utf-8') as json_file:
        data = json.load(json_file)
    return data

def read_txt_to_json_list(file_path):
    """
    读取txt文件并将每一行转换为JSON对象。
    
    参数:
    file_path (str): txt文件的路径
    
    返回:
    list: 包含每个JSON对象的列表
    """
    json_list = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            try:
                json_obj = json.loads(line.strip())
                json_list.append(json_obj)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from line: {line.strip()}. Error: {e}")
    return json_list

def extract_content_and_write_to_file(list_obj, output_file_path):
    """
    从JSON文件中提取'content'字段的值，并按行写入到输出文件中。
    
    参数:
    json_list (str): 包含每个JSON对象的列表
    output_file_path (str): 输出文本文件的路径
    
    返回:
    None
    """
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

    # 确保输出文件所在的目录存在
    output_dir = os.path.dirname(output_file_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # 将内容组合成 JSON 字符串数组
    content_json_str = json.dumps(content_list, ensure_ascii=False)
    
    # 提取'content'字段并写入文件
    with open(output_file_path, 'a', encoding='utf-8') as output_file:
        output_file.write(content_json_str + '\n')

# 示例调用
# extract_content_and_write_to_file('py-json/json_file.json', 'py-json/json_result.txt')