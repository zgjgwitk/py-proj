# -*- coding: utf-8 -*-
"""
将多个 requestContent_YYYY-MM-DD_decrypted.csv 文件合并,
按 (brandId, decryptMobileNo) 联合 key 去重,
生成一个新的去重 csv 文件。
"""

import csv
import glob
import os
from typing import Dict, Dict  # noqa: F401  (保留 typing 提示)


# 输入目录
INPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# 输出文件路径
OUTPUT_FILE = os.path.join(INPUT_DIR, "requestContent_dedup.csv")

# 匹配模式:requestContent_2026-09-2*_decrypted.csv
PATTERN = os.path.join(INPUT_DIR, "requestContent_2026-09-2*_decrypted.csv")

# 联合 key 字段
KEY_FIELDS = ("brandId", "decryptMobileNo")


def build_key(row: Dict[str, str]) -> str:
    """根据 brandId 和 decryptMobileNo 构造联合 key。"""
    return f"{row.get('brandId', '')}\x1f{row.get('decryptMobileNo', '')}"


def main() -> None:
    csv_files = sorted(glob.glob(PATTERN))
    if not csv_files:
        print(f"未找到匹配的 CSV 文件,pattern={PATTERN}")
        return

    print(f"待处理文件数:{len(csv_files)}")
    for f in csv_files:
        print(f"  - {os.path.basename(f)}")

    # 用 dict 保序去重:key -> row
    dedup_map: Dict[str, Dict[str, str]] = {}

    total_rows = 0
    for path in csv_files:
        # utf-8-sig 自动跳过 BOM
        with open(path, "r", encoding="utf-8-sig", newline="") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                total_rows += 1
                key = build_key(row)
                # 首次出现保留,后续重复跳过
                if key not in dedup_map:
                    dedup_map[key] = row

    # 写出
    fieldnames = ["sessionId", "brandId", "requestContent", "decryptMobileNo"]
    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in dedup_map.values():
            writer.writerow(row)

    dup_count = total_rows - len(dedup_map)
    print("处理完成")
    print(f"  原始总行数:{total_rows}")
    print(f"  去重后行数:{len(dedup_map)}")
    print(f"  重复行数:{dup_count}")
    print(f"  输出文件:{OUTPUT_FILE}")


if __name__ == "__main__":
    main()