# -* - coding: UTF-8 -* -
#! /usr/bin/python
# 功能: 解析es返回的json,取出对应字段的数据,按照需要的格式输出到控制台

import sys
import os
import re  # 正则
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common.filehelper import extract_content_and_write_to_file, read_txt_to_json_list

# 主方法
def printFile():
    source_file = 'py-json/!files/xhs_comments.txt'
    target_file = 'py-json/!files/xhs_comments_result.txt'
    # 使用已有的方法读取JSON文件
    json_list = read_txt_to_json_list(source_file)
    for list_obj in json_list:
        extract_content_and_write_to_file(list_obj, target_file)

if __name__ == '__main__':
    printFile()