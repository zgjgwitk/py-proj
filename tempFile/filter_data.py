#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def filter_and_deduplicate(input_file, output_file):
    """
    读取输入文件，去掉每行最后的数字，然后进行去重
    """
    unique_lines = set()
    
    # 读取文件并处理每一行
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                # 去掉行末的数字
                filtered_line = re.sub(r'\d+$', '', line)
                if filtered_line:  # 确保处理后的行不为空
                    unique_lines.add(filtered_line)
    
    # 将去重后的结果写入输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        for line in sorted(unique_lines):  # 按字母顺序排序
            f.write(line + '\n')
    
    return len(unique_lines)

if __name__ == "__main__":
    input_file = "temp-file.txt"
    output_file = "filtered_data.txt"
    
    print(f"正在处理文件: {input_file}")
    unique_count = filter_and_deduplicate(input_file, output_file)
    print(f"处理完成! 共找到 {unique_count} 个唯一项")
    print(f"结果已保存到: {output_file}")