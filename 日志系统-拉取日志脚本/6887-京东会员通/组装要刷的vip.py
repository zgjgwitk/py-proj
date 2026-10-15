"""
组装要刷的 vip, 组装为Dict类型数据

读取指定 CSV 文件(filePath),将每一行数据组装成 dict.Add 形式的 txt 内容输出:
  csv 列 ["Old_CdpId"] -> OldCdpId 字段
  csv 列 ["BindVipId"] -> NewVipId 字段

输出 txt 格式:
  dict.Add("${OldCdpId}",${NewVipId});

约束:
  - Old_CdpId 不可重复,出现重复时仅保留第一条,后续重复行跳过并打印控制台日志
  - 每行 csv 对应一行 txt 数据

使用示例:
  python 组装要刷的vip.py --source ./keyfile/3_errorvip.csv
  python 组装要刷的vip.py                # 使用默认源文件路径
"""
import argparse
import csv
import os
import sys
import traceback


# ============ 配置区域 ============
# 默认源 CSV 文件名(省略 --source 时使用)
# 使用原始字符串避免 Windows 路径中的 \G 等被当作转义序列
DEFAULT_SOURCE_FILE_NAME = r"_仅需要刷cdpid的虚拟单_0.csv"

# 必填列名(若 CSV 中缺失则抛错)
COL_OLD_CDP_ID = "Old_CdpId"
COL_NEW_VIP_ID = "BindVipId"

# 输出 txt 后缀(在源文件名基础上追加)
OUTPUT_SUFFIX = "_dictAdd.txt"

# 必填列集合(用于校验 CSV 表头完整性)
REQUIRED_COLUMNS = (COL_OLD_CDP_ID, COL_NEW_VIP_ID)


def resolve_source_path(arg_path):
    """
    解析源 CSV 路径:
      - 命令行传入路径则优先使用(自动转绝对路径)
      - 否则使用脚本所在目录下的默认文件名
    """
    if arg_path:
        return os.path.abspath(arg_path)
    here = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, DEFAULT_SOURCE_FILE_NAME)
    return target


def build_output_path(source_path):
    """
    根据源 CSV 路径生成输出 txt 路径
    命名规则: <源文件名(去扩展名)> + OUTPUT_SUFFIX,放在源文件同目录下
    """
    directory = os.path.dirname(os.path.abspath(source_path))
    base, _ext = os.path.splitext(os.path.basename(source_path))
    return os.path.join(directory, f"{base}{OUTPUT_SUFFIX}")


def read_rows(source_path):
    """
    读取 CSV 文件全部行,返回 (header, data_rows)
    - header: list[str]
    - data_rows: list[list[str]](已剔除空行)
    - 自动处理 utf-8-sig(BOM),避免列名首字符变成 '﻿xxx'
    """
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"源 CSV 文件不存在: {source_path}")

    with open(source_path, "r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.reader(fp)
        all_rows = list(reader)

    if not all_rows:
        raise ValueError(f"源 CSV 文件为空: {source_path}")

    header = all_rows[0]
    # 过滤完全空白的行(防止末尾换行导致空行被当作数据)
    data_rows = [row for row in all_rows[1:] if any(cell.strip() != "" for cell in row)]
    return header, data_rows


def validate_header(header):
    """
    校验 CSV 表头是否包含必需列,缺失则抛错
    """
    missing = [col for col in REQUIRED_COLUMNS if col not in header]
    if missing:
        raise ValueError(
            f"CSV 表头缺少必需列: {missing};实际表头: {header}"
        )


def build_dict_add_line(old_cdp_id, new_vip_id):
    """
    生成单行 txt 内容
    格式: dict.Add("${OldCdpId}",${NewVipId});
    注: ${xxx} 仅为变量占位符说明,真实数据无大括号
    """
    return f'dict.Add("{old_cdp_id}",{new_vip_id});'


def assemble(source_path, output_path):
    """
    主流程:
      1. 读取 CSV
      2. 校验表头
      3. 逐行生成 dict.Add,遇到 Old_CdpId 重复时跳过并打印日志
      4. 写入 txt
    """
    header, data_rows = read_rows(source_path)
    validate_header(header)

    old_idx = header.index(COL_OLD_CDP_ID)
    new_idx = header.index(COL_NEW_VIP_ID)

    seen_old_ids = {}           # old_cdp_id -> 首次出现的行号(从 1 开始,便于日志阅读)
    output_lines = []           # 待写入 txt 的行
    total = len(data_rows)
    dup_skip = 0
    empty_skip = 0

    for row_no, row in enumerate(data_rows, start=1):
        # 防御性:行内列数不足时视为空字符串
        old_val = (row[old_idx].strip() if old_idx < len(row) else "")
        new_val = (row[new_idx].strip() if new_idx < len(row) else "")

        # 任一字段为空:跳过(不计入重复统计)
        if old_val == "" or new_val == "":
            empty_skip += 1
            print(f"[第 {row_no} 行] 跳过:必填字段为空 (Old_CdpId='{old_val}', BindVipId='{new_val}')")
            continue

        # Old_CdpId 去重:仅保留首次出现的行
        if old_val in seen_old_ids:
            dup_skip += 1
            first_line = seen_old_ids[old_val]
            print(
                f"[第 {row_no} 行] 跳过:Old_CdpId='{old_val}' 重复 "
                f"(首次出现于第 {first_line} 行)"
            )
            continue

        seen_old_ids[old_val] = row_no
        output_lines.append(build_dict_add_line(old_val, new_val))

    # 写入 txt(UTF-8,行尾使用 \n,避免 Windows 默认 \r\n 影响下游)
    with open(output_path, "w", encoding="utf-8", newline="\n") as fp:
        fp.write("\n".join(output_lines))
        # 若有内容,末尾补一个换行,符合常见文本文件习惯
        if output_lines:
            fp.write("\n")

    written = len(output_lines)
    print(
        f"处理完成:共 {total} 行,实际写入 {written} 行,"
        f"跳过重复 {dup_skip} 行,跳过空值 {empty_skip} 行"
    )
    print(f"输出文件: {output_path}")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="把 CSV 组装成 dict.Add 形式的 txt")
    parser.add_argument(
        "--source",
        default="",
        help="源 CSV 文件路径,省略时取脚本目录下 3_errorvip.csv",
    )
    parser.add_argument(
        "--output",
        default="",
        help="输出 txt 文件路径,省略时自动在源文件名后追加 _dictAdd.txt",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    source_path = resolve_source_path(args.source)
    output_path = args.output or build_output_path(source_path)

    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"源 CSV 文件不存在: {source_path}")

    print(f"读取源 CSV: {source_path}")
    assemble(source_path, output_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        print(f"\n!!! 脚本异常退出: {exc}")
        sys.exit(1)