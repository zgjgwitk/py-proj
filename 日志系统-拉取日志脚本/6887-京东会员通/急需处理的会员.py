"""
急需处理的会员

从 CSV 中读取 BindVipId 列, 通过 CMDB MySQL 查询接口批量查询 6887 品牌的 ezp-crm.crm_jd_order_total_temp 表,
根据结果为每行数据打 TempErrType 标签:
  0 - 查询结果为空,或有多条但 TotalOrderPrice 都为 0
  1 - 查询结果有多条记录 且 至少一条 TotalOrderPrice > 0
  2 - 查询结果仅一条 且 TotalOrderPrice > 0
  -1 - 查询失败

输出: 在源文件同目录下生成新的 CSV,文件名追加 _tagged 后缀;不含 source_message 列
"""
import argparse
import csv
import json
import os
import time
import urllib.request

# ============ 配置区域 ============
# 源 CSV 文件目录
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))

# 固定要处理的源 CSV 文件名(只读取这一个文件,不扫描目录下其他 CSV)
SOURCE_FILE_NAME = "merged_file.csv"

# CMDB MySQL 查询接口地址
CMDB_QUERY_URL = "https://cmdb.ezrpro.com/api/mysql/query_mysql_table_data"

# 品牌 ID(京东会员通品牌)
BRAND_ID = 6887

# 品牌在 CMDB 中对应的子库 db_id
DB_ID = 4065

# 目标库名
DATABASE_NAME = "ezp-crm"

# 目标表名
TABLE_NAME = "crm_jd_order_total_temp"

# 每页返回条数(查询接口要求分页)
PAGE_LIMIT = 100

# 批量 IN 查询时,每批最多包含的 VipId 数量(避免 SQL 过长)
BATCH_SIZE = 50

# HTTP 请求超时(秒)
REQUEST_TIMEOUT = 30

# 单次请求失败后的重试次数
MAX_RETRY = 2

# 重试间隔(秒)
RETRY_SLEEP = 1.0

# ============ 认证 Cookie ============
COOKIE = "Hm_lvt_68fe85c2dd224790abf3b73237b05c77=1789524692,1789716485,1789886706,1789954839; HMACCOUNT=8444F8D3C42E99E3; opt.authorize=267dffc44a4b4c05a4378fd3ac539eaf; pcl_sid_cross=A6503583326942988831840F20812950; lite_type=0; pcl_brandid=186; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2210382813%22%2C%22%24device_id%22%3A%2219f63849600d2-0b19c3053941eb8-26011051-2073600-19f63849601126b%22%2C%22props%22%3A%7B%22%24latest_referrer%22%3A%22%22%2C%22%24latest_referrer_host%22%3A%22%22%7D%2C%22first_id%22%3A%2219f63849600d2-0b19c3053941eb8-26011051-2073600-19f63849601126b%22%7D; session=.eJw1jUFOwzAQRe8y6wiliZu0WbFDYtFtJVAVTe1JMhDbke2oSqueoVfgAJwAuA7qNXAJbN-8ef8E2qqxJw_VMwzjvmdZK5aBrUE31S0F2CWgpzrYVzJQQVaUqmmkECj2QqZLFHm5alSOcpmvCRtIwNmeNqgp2g8j-fCHfidmEJOjJwfVCWTHhvy___31dv28XD_e4w9p5D6yY4emfWHTHojvCf3kKMTL4OydtDqKrKDKynUCQ2fNrbLIRZoVxaJMVzAvmTn_dEs9xtSWGM7nHz-GVnk.arDlGA.R58DtdmEiC0UPq7vO3n7OsT3K5k; Hm_lpvt_68fe85c2dd224790abf3b73237b05c77=1789999218"

# 新增列名
NEW_COLUMN = "TempErrType"

# 标签值定义
TAG_MULTI_WITH_PRICE = 1  # 多条记录 且 至少一条 TotalOrderPrice > 0
TAG_SINGLE_WITH_PRICE = 2 # 单条记录 且 TotalOrderPrice > 0


def http_post_json(payload):
    """
    通用 POST JSON 请求封装,带重试
    返回: 响应 JSON 字典
    """
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Cookie": COOKIE,
        "origin": "https://cmdb.ezrpro.com",
    }
    last_err = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            req = urllib.request.Request(
                CMDB_QUERY_URL,
                data=data,
                method="POST",
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"  请求失败(第{attempt}次): {exc}")
            if attempt < MAX_RETRY:
                time.sleep(RETRY_SLEEP)
    raise last_err


def fetch_records_for_vip_ids(vip_ids):
    """
    批量查询 VipId 列表对应的所有记录
    返回: dict[vip_id] -> list[record]
    """
    if not vip_ids:
        return {}

    ids_str = ",".join(str(v) for v in vip_ids)
    # 增加 BrandId 条件:命中 BrandId 索引,避免无索引大表的全表扫描被 CMDB 拦截
    sql = (
        f"SELECT * FROM `{TABLE_NAME}` "
        f"WHERE BrandId = {BRAND_ID} AND VipId IN ({ids_str}) "
        f"ORDER BY VipId,CreateDate"
    )
    payload = {
        "is_first_query_table": False,
        "force": False,
        "db_id": DB_ID,
        "database_name": DATABASE_NAME,
        "table_name": TABLE_NAME,
        "sql": sql,
        "pageIndex": 1,
        "pageLimit": PAGE_LIMIT,
    }

    resp = http_post_json(payload)

    # 兼容多种返回结构
    data_node = resp.get("data") or {}
    rows = data_node.get("list") or data_node.get("rows") or []
    total = data_node.get("count") or data_node.get("total") or len(rows)

    # 若接口返回总数 > 当前 rows 数,需要分页继续拉取
    all_rows = list(rows)
    page_index = 1
    # 防御性:若 total 异常巨大(例如接口错误返回整表 count),设置上限,避免死循环
    max_pages = 50
    while len(all_rows) < total and page_index < max_pages:
        page_index += 1
        payload["pageIndex"] = page_index
        resp = http_post_json(payload)
        rows = (resp.get("data") or {}).get("list") or (resp.get("data") or {}).get("rows") or []
        if not rows:
            break
        all_rows.extend(rows)

    # 按 VipId 分组(键统一转为字符串,与 CSV 中的 BindVipId 类型一致)
    grouped = {}
    for record in all_rows:
        vip_id = record.get("VipId")
        if vip_id is None:
            continue
        grouped.setdefault(str(vip_id), []).append(record)
    return grouped


def classify_records(records):
    """
    根据查询结果计算 TempErrType 标签
    规则:
      - 无记录 → 0
      - 多条记录 且 至少一条 TotalOrderPrice > 0 → TAG_MULTI_WITH_PRICE(1)
      - 单条记录 且 TotalOrderPrice > 0 → TAG_SINGLE_WITH_PRICE(2)
      - 其他(多条但价格全为 0,或单条但价格为 0) → 0
    返回: int (0/1/2)
    """
    if not records:
        return 0

    # 兼容接口可能返回字符串/Decimal,统一转为 float 数值再比较
    def _to_float(value):
        if value is None or value == "":
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    has_price = any(_to_float(r.get("TotalOrderPrice")) > 0 for r in records)
    if not has_price:
        # 多条但价格全为 0 / 单条但价格为 0 都按 0 处理
        return 0

    if len(records) > 1:
        return TAG_MULTI_WITH_PRICE
    return TAG_SINGLE_WITH_PRICE


def chunks(items, size):
    """将列表切分为指定大小的批次"""
    return [items[i:i + size] for i in range(0, len(items), size)]


def build_output_path(source_path):
    """
    根据源 CSV 路径生成输出 CSV 路径
    在文件名后追加 _tagged,扩展名保持 .csv
    """
    base, ext = os.path.splitext(source_path)
    if ext.lower() != ".csv":
        return f"{source_path}_tagged.csv"
    return f"{base}_tagged.csv"


def resolve_source_path(arg_path):
    """
    解析源 CSV 路径:
      - 命令行传入路径则优先使用
      - 否则固定取 SOURCE_DIR 下的 merged_file.csv
    """
    if arg_path:
        return os.path.abspath(arg_path)
    target = os.path.join(SOURCE_DIR, SOURCE_FILE_NAME)
    if not os.path.isfile(target):
        raise FileNotFoundError(f"源 CSV 文件不存在: {target}")
    return target


def main():
    parser = argparse.ArgumentParser(description="为 CSV 数据打 TempErrType 标签")
    parser.add_argument(
        "--source",
        default="",
        help="源 CSV 文件路径,省略时取 SOURCE_DIR 下的 merged_file.csv",
    )
    parser.add_argument(
        "--output",
        default="",
        help="输出 CSV 文件路径,省略时自动在源文件名后追加 _tagged",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="强制处理全部行,忽略已存在的 TempErrType 值",
    )
    args = parser.parse_args()

    source_path = resolve_source_path(args.source)
    output_path = args.output or build_output_path(source_path)

    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"源 CSV 文件不存在: {source_path}")

    print(f"读取源 CSV: {source_path}")
    with open(source_path, "r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.reader(fp)
        rows_all = list(reader)

    if not rows_all:
        raise ValueError("源 CSV 文件为空")

    source_header = rows_all[0]
    if "BindVipId" not in source_header:
        raise ValueError("CSV 中未找到 BindVipId 列")

    # 输出列:排除 source_message,并丢弃已有的 TempErrType(将重新生成)
    dropped_columns = {"source_message"}
    keep_indexes = [
        i for i, col in enumerate(source_header)
        if col not in dropped_columns and col != NEW_COLUMN
    ]
    keep_columns = [source_header[i] for i in keep_indexes]
    # 输出表头追加 TempErrType 列
    if NEW_COLUMN not in keep_columns:
        keep_columns.append(NEW_COLUMN)
    temp_err_idx = len(keep_columns) - 1
    bind_vip_idx = keep_columns.index("BindVipId")

    # 重塑 rows_all:仅保留 keep_indexes 对应的列,行末预留 TempErrType
    reshaped_rows = []
    for row in rows_all[1:]:
        new_row = [row[i] if i < len(row) else "" for i in keep_indexes]
        while len(new_row) < len(keep_columns) - 1:
            new_row.append("")
        new_row.append("")
        reshaped_rows.append(new_row)
    rows_all = [keep_columns] + reshaped_rows
    header = keep_columns

    # 收集需要处理的行: vip_id -> [row_idx_in_rows_all, ...]
    vip_to_rows = {}
    total_rows = 0
    skipped_rows = 0
    empty_value_rows = 0

    # 数据从 rows_all[1:] 开始
    for i in range(1, len(rows_all)):
        total_rows += 1
        row = rows_all[i]
        # 补齐列数,避免索引越界
        while len(row) < len(header):
            row.append("")

        existing_tag = row[temp_err_idx].strip() if temp_err_idx < len(row) else ""

        if not args.all and existing_tag != "":
            skipped_rows += 1
            continue

        raw_vip = row[bind_vip_idx].strip() if bind_vip_idx < len(row) else ""
        if raw_vip == "":
            # 空值直接打 0
            row[temp_err_idx] = "0"
            empty_value_rows += 1
            continue
        # 规范化:统一为字符串(避免 123 vs "123" 不匹配)
        vip_to_rows.setdefault(raw_vip, []).append(i)

    unique_vips = list(vip_to_rows.keys())
    print(
        f"共 {total_rows} 行,跳过已处理 {skipped_rows} 行,"
        f"空值直接置 0 {empty_value_rows} 行,唯一 VipId {len(unique_vips)} 个"
    )

    # 批量查询 + 每批处理完立即写回 CSV
    tagged = 0
    failed_vips = []
    total_batches = (len(unique_vips) + BATCH_SIZE - 1) // BATCH_SIZE

    def flush_to_csv():
        """将当前 rows_all 写回输出 CSV"""
        with open(output_path, "w", encoding="utf-8-sig", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerows(rows_all)

    for batch_idx, batch in enumerate(chunks(unique_vips, BATCH_SIZE), start=1):
        print(f"[批次 {batch_idx}/{total_batches}] 查询 {len(batch)} 个 VipId ...")
        try:
            batch_map = fetch_records_for_vip_ids(batch)
        except Exception as exc:  # noqa: BLE001
            print(f"  批次 {batch_idx} 整体失败,跳过批次内全部 VipId: {exc}")
            failed_vips.extend(batch)
            # 标记这些行的 TempErrType 为 -1
            for vip in batch:
                for r in vip_to_rows.get(vip, []):
                    row = rows_all[r]
                    while len(row) < len(header):
                        row.append("")
                    row[temp_err_idx] = "-1"
            flush_to_csv()
            print(f"  [批次 {batch_idx}] 已写回 CSV")
            continue

        # 为不在结果集中的 VipId 写入 0(无记录)
        for vip in batch:
            if vip not in batch_map:
                batch_map[vip] = []

        # 打标签并写回行
        for vip_id in batch:
            records = batch_map.get(vip_id, [])
            tag = classify_records(records)
            tag_str = str(tag)
            target_rows = vip_to_rows.get(vip_id, [])
            for r in target_rows:
                row = rows_all[r]
                while len(row) < len(header):
                    row.append("")
                row[temp_err_idx] = tag_str
            if tag != 0:
                tagged += 1

        # 每批处理完立即保存一次,避免中途中断丢失进度
        try:
            flush_to_csv()
            print(f"  [批次 {batch_idx}] 已写回 CSV (累计打标签 {tagged} 行)")
        except Exception as exc:  # noqa: BLE001
            print(f"  [批次 {batch_idx}] 写回 CSV 失败: {exc}")
            # 不中断整体流程,继续下一批
            continue

    print(
        f"处理完成,共 {total_rows} 行(跳过已处理 {skipped_rows} 行),"
        f"其中 {tagged} 行被打上 TempErrType 标签,"
        f"批次失败跳过 {len(failed_vips)} 个 VipId"
    )
    print(f"输出文件: {output_path}")


if __name__ == "__main__":
    import sys as _sys
    import traceback
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        print(f"\n!!! 脚本异常退出: {exc}")
        _sys.exit(1)
