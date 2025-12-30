"""
SQL IN条件格式化工具
从input.txt读取数据，输出到output.txt

输入格式：每行一个字符串
输出格式：SQL IN子句格式，每个值用单引号包围并换行显示
"""

import os

_is_use_double_quote = False

def format_sql_in_condition(data_list):
    """
    将字符串列表格式化为SQL IN子句格式
    
    Args:
        data_list (list): 字符串列表
        
    Returns:
        str: 格式化后的SQL IN条件字符串
    """
    if not isinstance(data_list, list):
        raise TypeError("输入必须是列表类型")
    
    # 为每个元素添加引号并用逗号分隔
    if _is_use_double_quote:
        formatted_items = [f'"{item}"' for item in data_list]
    else:
        formatted_items = [f"'{item}'" for item in data_list]
    formatted_items = [f"'{item}'" for item in data_list]
    return ',\n '.join(formatted_items)

def read_input_file(filename="input.txt"):
    """
    从文件读取输入数据
    
    Args:
        filename (str): 输入文件名
        
    Returns:
        list: 字符串列表
    """
    print(f"查看当前目录: {os.path.dirname(os.path.abspath(__file__))}")
    if not os.path.exists(filename):
        raise FileNotFoundError(f"输入文件 {filename} 不存在")
    
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 过滤掉空行和只包含空白字符的行
    return [line.strip() for line in lines if line.strip()]

def write_output_file(content, filename="output.txt"):
    """
    将内容写入输出文件
    
    Args:
        content (str): 要写入的内容
        filename (str): 输出文件名
    """
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"结果已保存到 {filename}")

def main():
    """主函数"""
    input_file = "ezr-sql-maker/组装sql-string-in条件/input.txt"
    output_file = "ezr-sql-maker/组装sql-string-in条件/output.txt"
    
    print("=" * 60)
    print("SQL IN条件格式化工具")
    print("=" * 60)
    
    try:
        # 从文件读取数据
        input_data = read_input_file(input_file)
        
        if not input_data:
            print("警告: 输入文件为空")
            return
            
        print(f"从 {input_file} 读取到 {len(input_data)} 行数据:")
        # for i, item in enumerate(input_data, 1):
        #     print(f"  {i}. {item}")
        
        # 格式化为SQL IN条件
        result = format_sql_in_condition(input_data)
        
        print("\n格式化后的SQL IN条件:")
        # print(result)
        
        # 写入输出文件
        write_output_file(result, output_file)
        
        print(f"\n处理完成！")
        
    except FileNotFoundError as e:
        print(f"错误: {e}")
        print("请确保在当前目录下有 input.txt 文件")
    except Exception as e:
        print(f"处理过程中发生错误: {e}")

if __name__ == "__main__":
    main()