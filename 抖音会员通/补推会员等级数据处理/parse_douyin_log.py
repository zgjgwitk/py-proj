import csv
import json
import argparse
import os
import logging
import re
from typing import Dict, List, Optional, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 默认要执行的文件名
default_input = "level-4-log"

class DouyinLogParser:
    """
    抖音会员通日志解析器
    """
    def __init__(self, input_name: str, work_dir: str):
        self.input_name = input_name
        self.work_dir = work_dir
        # 处理文件名，如果用户输入带了 .csv 后缀则去掉，避免重复
        base_name = input_name[:-4] if input_name.lower().endswith('.csv') else input_name
        
        self.input_file = os.path.join(work_dir, f"{base_name}.csv")
        self.output_json_file = os.path.join(work_dir, f"out_{base_name}.txt")
        self.output_dict_file = os.path.join(work_dir, f"dict_{base_name}.txt")

    def extract_json_from_line(self, line_content: str) -> Optional[Dict[str, Any]]:
        """
        从行文本中提取并解析 JSON 数据
        """
        try:
            # 查找 param_json: 的位置
            keyword = "param_json:"
            start_index = line_content.find(keyword)
            
            if start_index == -1:
                logger.warning(f"行中未找到 '{keyword}': {line_content[:50]}...")
                return None
            
            # 截取 param_json: 之后的内容
            json_part = line_content[start_index + len(keyword):]
            
            # 查找 JSON 的结束位置 (最后一个 '}')
            end_index = json_part.rfind('}')
            
            if end_index == -1:
                logger.warning(f"行中未找到 JSON 结束符: {line_content[:50]}...")
                return None
            
            # 提取 JSON 字符串
            json_str = json_part[:end_index+1]
            
            # 解析 JSON
            return json.loads(json_str)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e} - 内容片段: {line_content[:50]}...")
            return None
        except Exception as e:
            logger.error(f"处理行时发生未知错误: {e}")
            return None

    def parse_line(self, line_content: str) -> Optional[Dict[str, Any]]:
        """
        解析单行内容，提取所需字段
        """
        data = self.extract_json_from_line(line_content)
        if not data:
            return None

        try:
            mobile = str(data.get("mobile", ""))
            mask_mobile = str(data.get("mask_mobile", ""))
            level = data.get("level")
            open_id = data.get("open_id")

            # 必需字段检查 (根据需求，open_id 和 level 似乎是必需的用于 dict 输出)
            if open_id is None:
                logger.warning("缺少 open_id 字段")
                # 即使缺少 open_id，可能仍需要输出其他信息？
                # 这里的策略是：如果没有 open_id，dict 输出会受影响，但 json 输出可能仍有价值
                # 但为了数据完整性，暂且继续
            
            result = {
                "level": level,
                "mobile": mobile,
                "mask_mobile": mask_mobile,
                "open_id": open_id
            }
            return result
            
        except Exception as e:
            logger.error(f"字段提取失败: {e}")
            return None

    def process(self):
        """
        主处理流程
        """
        logger.info(f"开始处理文件: {self.input_file}")
        
        if not os.path.exists(self.input_file):
            logger.error(f"文件不存在: {self.input_file}")
            return

        parsed_results = []
        dict_results = {}
        seen_open_ids = set()

        try:
            # 读取 CSV 文件
            # 假设没有 header，或者第一行就是数据。通常日志文件没有 header。
            # 如果 CSV 格式复杂（包含换行符等），csv 模块能处理。
            # 这里为了简单和防御性，我们把每一行当作一个字符串处理，
            # 因为用户说 "csv每行第一个元素就是一个需要处理的字符串"
            
            with open(self.input_file, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                for row_idx, row in enumerate(reader, 1):
                    if not row:
                        continue
                    
                    # 取第一个元素
                    line_content = row[0]
                    
                    # 解析
                    result = self.parse_line(line_content)
                    
                    if result:
                        # 提取 open_id 用于去重
                        open_id = result.get("open_id")
                        
                        # 根据 open_id 去重
                        if open_id:
                            if open_id in seen_open_ids:
                                # logger.debug(f"重复的 open_id，跳过: {open_id}")
                                continue
                            seen_open_ids.add(open_id)
                        
                        # 构建 JSON 输出格式: {"level": level, "mobile": mobile, "mask_mobile": mask_mobile, "open_id": open_id}
                        parsed_results.append(result)
                        # 构建 dict 输出格式: {open_id: level}
                        if open_id is not None and result.get("level") is not None:
                             dict_results[open_id] = result["level"]

            # 写入 out 文件
            logger.info(f"正在写入结果到: {self.output_json_file}")
            with open(self.output_json_file, 'w', encoding='utf-8') as f:
                for item in parsed_results:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')

            # 写入 dict 文件
            logger.info(f"正在写入字典结果到: {self.output_dict_file}")
            with open(self.output_dict_file, 'w', encoding='utf-8') as f:
                # 需求格式: [{key:value}, {key:value}]
                # json.dump 默认就是这个格式
                # indent=2 使输出格式化，便于阅读
                json.dump(dict_results, f, ensure_ascii=False, indent=2)

            logger.info("处理完成")

        except Exception as e:
            logger.critical(f"程序执行严重错误: {e}")
            raise

def main():
    # 使用原始字符串 r"" 避免转义问题
    default_dir = r"D:\Github\py-proj\抖音会员通\补推会员等级数据处理\files"
    
    parser = argparse.ArgumentParser(description="抖音会员通日志解析工具")
    # nargs='?' 表示参数可选，const和default指定默认值
    parser.add_argument("input_name", nargs='?', default=default_input, help=f"输入文件名 (默认为 {default_input})")
    parser.add_argument("--dir", default=default_dir, help=f"工作目录 (默认为 {default_dir})")
    
    args = parser.parse_args()
    
    # 检查目录是否存在，如果不存在则回退到当前目录
    if not os.path.exists(args.dir):
        logger.warning(f"指定目录不存在: {args.dir}，尝试使用当前目录")
        work_dir = os.getcwd()
    else:
        work_dir = os.path.abspath(args.dir)
    
    logger.info(f"工作目录: {work_dir}")
    logger.info(f"处理文件: {args.input_name}")
    
    parser_tool = DouyinLogParser(args.input_name, work_dir)
    parser_tool.process()

if __name__ == "__main__":
    main()
