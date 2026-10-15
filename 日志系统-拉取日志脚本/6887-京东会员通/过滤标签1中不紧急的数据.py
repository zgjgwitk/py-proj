"""
过滤标签1中不紧急的数据

输入 CSV(tofilter_flag1.csv)TempErrType 取值(由"急需处理的会员.py"产出):
  - 1: 标记为需要进一步过滤的会员

输出 CSV TempErrType 取值(本脚本写入):
  - 10: 匹配成功——oldData.TotalOrderPrice == newData.TotalOrderPrice
  - 20: 匹配失败——oldData.TotalOrderPrice != newData.TotalOrderPrice
  - 0:  数据缺失无法对比(CustomerIdentity 空 / 旧 CdpId 无记录 / 新 CdpId 无记录)
  - -1: 单行分析过程中异常
  - -2: 整批查询失败(sql1 或 sql2 整批接口调用失败)

业务语义:
  10 → 不紧急,无需处理
  20 → 紧急,需处理

从 CSV(tofilter_flag1.csv)中读取 BindVipId、Old_CdpId 列,
通过 CMDB MySQL 查询接口在 6887 品牌的 ezp-crm 库中**批量**执行两条 SQL:
  sql1: crm_vip_info_third_party_bind 取 CustomerIdentity
        WHERE BrandId=6887 AND ThirdPartyId=1 AND VipId IN (...全部BindVipId...)
  sql2: crm_jd_order_total_temp 取 VipId IN (...全部BindVipId...)
         OR CdpId IN (...全部Old_CdpId去重值...)
        按 VipId, CreateDate 排序

对每行做对比分析:
  - 取 ListData2 中 CdpId=Old_CdpId 的最后一条 oldData
  - 取 ListData2 中 VipId=BindVipId 且 CdpId=CustomerIdentity 的第一条 newData
  - 若 oldData.TotalOrderPrice == newData.TotalOrderPrice 则打标签 10(不紧急)
  - 若 oldData.TotalOrderPrice != newData.TotalOrderPrice 则打标签 20(紧急)
  - 数据缺失无法对比则打标签 0

所有处理后的行都会写入输出 CSV(含 10/20/0,以及行级失败 -1、整批失败 -2)。
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
SOURCE_FILE_NAME = "tofilter_flag1.csv"

# CMDB MySQL 查询接口地址
CMDB_QUERY_URL = "https://cmdb.ezrpro.com/api/mysql/query_mysql_table_data"

# 品牌 ID(京东会员通品牌)
BRAND_ID = 6887

# 品牌在 CMDB 中对应的子库 db_id
DB_ID = 4065

# 目标库名
DATABASE_NAME = "ezp-crm"

# sql1 目标表名
TABLE_BIND = "crm_vip_info_third_party_bind"

# sql2 目标表名
TABLE_ORDER = "crm_jd_order_total_temp"

# 京东会员通的 ThirdPartyId 固定值
THIRD_PARTY_ID = 1

# 每页返回条数(查询接口要求分页)
PAGE_LIMIT = 100  # 批量查询场景下放大单页条数,减少分页次数

# sql1 IN 列表每批最大 BindVipId 数量(避免 SQL 过长)
BIND_BATCH_SIZE = 100

# sql2 CdpId IN 列表每批最大 Old_CdpId 数量
CDP_BATCH_SIZE = 100

# HTTP 请求超时(秒)
REQUEST_TIMEOUT = 60  # 批量数据量大,延长超时

# 单次请求失败后的重试次数
MAX_RETRY = 3

# 重试间隔(秒)
RETRY_SLEEP = 1.0

# 防御性:若 total 异常巨大,设置最大分页上限
MAX_PAGES = 50

# ============ 认证 Cookie ============
COOKIE = "Hm_lvt_68fe85c2dd224790abf3b73237b05c77=1789524692,1789716485,1789886706,1789954839; HMACCOUNT=8444F8D3C42E99E3; opt.authorize=267dffc44a4b4c05a4378fd3ac539eaf; pcl_sid_cross=A6503583326942988831840F20812950; lite_type=0; pcl_brandid=186; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2210382813%22%2C%22%24device_id%22%3A%2219f63849600d2-0b19c3053941eb8-26011051-2073600-19f63849601126b%22%2C%22props%22%3A%7B%22%24latest_referrer%22%3A%22%22%2C%22latest_referrer_host%22%3A%22%22%7D%2C%22first_id%22%3A%2219f63849600d2-0b19c3053941eb8-26011051-2073600-19f63849601126b%22%7D; session=.eJw1jUFOwzAQRe8y6wiliZu0WbFDYtFtJVAVTe1JMhDbke2oSqueoVfgAJwAuA7qNXAJbN-8ef8E2qqxJw_VMwzjvmdZK5aBrUE31S0F2CWgpzrYVzJQQVaUqmmkECj2QqZLFHm5alSOcpmvCRtIwNmeNqgp2g8j-fCHfidmEJOjJwfVCWTHhvy___31dv28XD_e4w9p5D6yY4emfWHTHojvCf3kKMTL4OydtDqKrKDKynUCQ2fNrbLIRZoVxaJMVzAvmTn_dEs9xtSWGM7nHz-GVnk.arDlGA.R58DtdmEiC0UPq7vO3n7OsT3K5k; Hm_lpvt_68fe85c2dd224790abf3b73237b05c77=1789999218"

# 新增/更新列名
NEW_COLUMN = "TempErrType"

# 标签值定义
TAG_EQUAL = 10           # oldData.TotalOrderPrice == newData.TotalOrderPrice(价格相等,无需处理)
TAG_NOT_EQUAL = 20       # oldData.TotalOrderPrice != newData.TotalOrderPrice(价格不等,需处理)
TAG_NO_DATA = 0          # 数据缺失无法对比(CustomerIdentity 空 / 旧 CdpId 无记录 / 新 CdpId 无记录)
TAG_ROW_FAILED = -1      # 单行分析过程中异常
TAG_BATCH_FAILED = -2    # 整批查询失败,本批所有行均无结果


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


def fetch_all_rows(sql, table_name):
    """
    执行 SQL 并分页拉取全部结果
    返回: list[dict]
    """
    payload = {
        "is_first_query_table": False,
        "force": False,
        "db_id": DB_ID,
        "database_name": DATABASE_NAME,
        "table_name": table_name,
        "sql": sql,
        "pageIndex": 1,
        "pageLimit": PAGE_LIMIT,
    }

    resp = http_post_json(payload)

    # 兼容多种返回结构
    data_node = resp.get("data") or {}
    rows = data_node.get("list") or data_node.get("rows") or []
    total = data_node.get("count") or data_node.get("total") or len(rows)

    all_rows = list(rows)
    page_index = 1
    while len(all_rows) < total and page_index < MAX_PAGES:
        page_index += 1
        payload["pageIndex"] = page_index
        resp = http_post_json(payload)
        rows = (resp.get("data") or {}).get("list") or (resp.get("data") or {}).get("rows") or []
        if not rows:
            break
        all_rows.extend(rows)

    return all_rows


def to_float(value):
    """统一转为 float 数值"""
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def chunks(items, size):
    """将列表切分为指定大小的批次"""
    return [items[i:i + size] for i in range(0, len(items), size)]


def build_output_path(source_path):
    """
    根据源 CSV 路径生成输出 CSV 路径
    在文件名后追加 _flag10,扩展名保持 .csv
    """
    base, ext = os.path.splitext(source_path)
    if ext.lower() != ".csv":
        return f"{source_path}_flag10.csv"
    return f"{base}_flag10.csv"


def resolve_source_path(arg_path):
    """
    解析源 CSV 路径:
      - 命令行传入路径则优先使用
      - 否则固定取 SOURCE_DIR 下的 SOURCE_FILE_NAME
    """
    if arg_path:
        return os.path.abspath(arg_path)
    target = os.path.join(SOURCE_DIR, SOURCE_FILE_NAME)
    if not os.path.isfile(target):
        raise FileNotFoundError(f"源 CSV 文件不存在: {target}")
    return target


def batch_fetch_bind_records(bind_vip_ids):
    """
    批量执行 sql1: VipId IN (...) 查 crm_vip_info_third_party_bind
    返回: dict[bind_vip_id(str) -> CustomerIdentity(str) 或 None]
    """
    cache = {str(v): None for v in bind_vip_ids}
    if not bind_vip_ids:
        return cache

    # 去重但保留稳定顺序
    seen = set()
    unique_ids = []
    for v in bind_vip_ids:
        key = str(v)
        if key not in seen:
            seen.add(key)
            unique_ids.append(v)

    total_batches = (len(unique_ids) + BIND_BATCH_SIZE - 1) // BIND_BATCH_SIZE
    for batch_idx, batch in enumerate(chunks(unique_ids, BIND_BATCH_SIZE), start=1):
        ids_str = ",".join(str(v) for v in batch)
        sql = (
            f"SELECT VipId, CustomerIdentity FROM `{TABLE_BIND}` "
            f"WHERE BrandId={BRAND_ID} AND ThirdPartyId={THIRD_PARTY_ID} "
            f"AND VipId IN ({ids_str})"
        )
        print(f"  [sql1 批次 {batch_idx}/{total_batches}] 查询 {len(batch)} 个 VipId ...")
        try:
            rows = fetch_all_rows(sql, TABLE_BIND)
        except Exception as exc:  # noqa: BLE001
            print(f"  sql1 批次 {batch_idx} 失败: {exc}")
            continue
        for r in rows:
            vip_key = str(r.get("VipId"))
            cache[vip_key] = r.get("CustomerIdentity")
    return cache


def batch_fetch_order_records(bind_vip_ids, old_cdp_ids):
    """
    批量执行 sql2: VipId IN (...) OR CdpId IN (...)
    返回: list[dict] 已按 VipId,CreateDate 排序
    """
    # 去重 Old_CdpId
    seen = set()
    unique_cdps = []
    for c in old_cdp_ids:
        if c not in seen:
            seen.add(c)
            unique_cdps.append(c)

    # sql2 的两个条件分别拆批: BindVipId 用整数 IN, Old_CdpId 用字符串 IN
    # 避免单条 SQL 同时持有大批量 BindVipId + CdpId 导致 SQL 过长
    # 策略:分别按批次查,再合并 + 排序
    # 但 CdpId 条件的数据可能与 VipId 条件的数据存在重叠(同一行同时满足),需去重
    all_rows = []

    # --- 按 BindVipId 批查 ---
    seen_vip_cdp_pairs = set()  # 用于去重(VipId, CdpId, CreateDate)三元组

    if bind_vip_ids:
        total_batches = (len(bind_vip_ids) + BIND_BATCH_SIZE - 1) // BIND_BATCH_SIZE
        for batch_idx, batch in enumerate(chunks(bind_vip_ids, BIND_BATCH_SIZE), start=1):
            ids_str = ",".join(str(v) for v in batch)
            sql = (
                f"SELECT VipId, CdpId, CreateDate, TotalOrderPrice FROM `{TABLE_ORDER}` "
                f"WHERE BrandId={BRAND_ID} AND VipId IN ({ids_str}) "
                f"ORDER BY VipId,CreateDate"
            )
            print(f"  [sql2-VipId 批次 {batch_idx}/{total_batches}] 查询 {len(batch)} 个 VipId ...")
            try:
                rows = fetch_all_rows(sql, TABLE_ORDER)
            except Exception as exc:  # noqa: BLE001
                print(f"  sql2-VipId 批次 {batch_idx} 失败: {exc}")
                continue
            for r in rows:
                key = (str(r.get("VipId")), str(r.get("CdpId")), str(r.get("CreateDate")))
                if key in seen_vip_cdp_pairs:
                    continue
                seen_vip_cdp_pairs.add(key)
                all_rows.append(r)

    # --- 按 Old_CdpId 批查 ---
    if unique_cdps:
        total_batches = (len(unique_cdps) + CDP_BATCH_SIZE - 1) // CDP_BATCH_SIZE
        for batch_idx, batch in enumerate(chunks(unique_cdps, CDP_BATCH_SIZE), start=1):
            # 对字符串值做单引号转义
            cdps_str = ",".join(f"'{str(c).replace(chr(39), chr(39) * 2)}'" for c in batch)
            sql = (
                f"SELECT VipId, CdpId, CreateDate, TotalOrderPrice FROM `{TABLE_ORDER}` "
                f"WHERE BrandId={BRAND_ID} AND CdpId IN ({cdps_str}) "
                f"ORDER BY VipId,CreateDate"
            )
            print(f"  [sql2-CdpId 批次 {batch_idx}/{total_batches}] 查询 {len(batch)} 个 CdpId ...")
            try:
                rows = fetch_all_rows(sql, TABLE_ORDER)
            except Exception as exc:  # noqa: BLE001
                print(f"  sql2-CdpId 批次 {batch_idx} 失败: {exc}")
                continue
            for r in rows:
                key = (str(r.get("VipId")), str(r.get("CdpId")), str(r.get("CreateDate")))
                if key in seen_vip_cdp_pairs:
                    continue
                seen_vip_cdp_pairs.add(key)
                all_rows.append(r)

    # 接口可能未在 SQL 内排序,这里统一按 VipId, CreateDate 排一次(防御性)
    def _sort_key(r):
        return (str(r.get("VipId") or ""), str(r.get("CreateDate") or ""))

    all_rows.sort(key=_sort_key)
    return all_rows


def build_lookup(list_data_2):
    """
    将 sql2 结果集预构为索引,加速单行分析:
      by_cdp[str(Old_CdpId)] -> list[record]  (按出现顺序,即 VipId,CreateDate 顺序)
    返回: dict
    """
    by_cdp = {}
    for r in list_data_2:
        cdp = r.get("CdpId")
        if cdp is None:
            continue
        by_cdp.setdefault(str(cdp), []).append(r)
    return by_cdp


def analyze_row(bind_vip_id, old_cdp_id, customer_identity, by_cdp):
    """
    对单行数据执行对比逻辑(查询已由批量预取完成)
    返回: int (TAG_EQUAL / TAG_NOT_EQUAL / TAG_NO_DATA)
      - TAG_EQUAL(10):    oldData.TotalOrderPrice == newData.TotalOrderPrice
      - TAG_NOT_EQUAL(20): oldData.TotalOrderPrice != newData.TotalOrderPrice
      - TAG_NO_DATA(0):   数据缺失无法对比
    """
    if not customer_identity:
        return TAG_NO_DATA

    old_cdp_records = by_cdp.get(str(old_cdp_id), [])
    if not old_cdp_records:
        return TAG_NO_DATA
    old_data = old_cdp_records[-1]  # ListData2 中 CdpId=Old_CdpId 的最后一条

    # 新数据: ListData2 中 VipId=BindVipId 且 CdpId=customer_identity 的第一条
    new_data = None
    bind_vip_str = str(bind_vip_id)
    cust_id_str = str(customer_identity)
    for r in old_cdp_records:
        if str(r.get("VipId")) == bind_vip_str and str(r.get("CdpId")) == cust_id_str:
            new_data = r
            break
    if new_data is None:
        # 若上面遍历同 CdpId 分组没找到,退回到全量扫描(理论上不会发生,但防御性保留)
        for r in by_cdp.get(cust_id_str, []):
            if str(r.get("VipId")) == bind_vip_str:
                new_data = r
                break
    if new_data is None:
        return TAG_NO_DATA

    # 对比价格
    old_price = to_float(old_data.get("TotalOrderPrice"))
    new_price = to_float(new_data.get("TotalOrderPrice"))
    if old_price == new_price:
        return TAG_EQUAL
    return TAG_NOT_EQUAL


# 每批从 CSV 读取的最大行数(每批做一次 sql1 + sql2 批量查询,然后处理)
CSV_BATCH_SIZE = 100


def process_one_batch(batch_rows, bind_idx, cdp_idx, out_header, temp_err_idx):
    """
    处理一个批次:
      1) 收集本批 BindVipId / Old_CdpId
      2) 批量查 sql1 + sql2
      3) 逐行分析,为每行打 TempErrType 并就地修改 batch_rows
    返回: (整批是否成功: bool,)
      - 成功: batch_rows 中每行均已被填上 TempErrType(成功=10/0,行级异常=-1)
      - 失败: 整批 sql 查询异常,主流程会用 -2 标记每行
    """
    if not batch_rows:
        return True

    # 提取本批有效行 + 收集 VipId / CdpId
    bind_vip_ids = []
    old_cdp_ids = []
    for r in batch_rows:
        while len(r) < len(out_header) - 1:
            r.append("")
        bind_vip_ids.append(r[bind_idx].strip())
        old_cdp_ids.append(r[cdp_idx].strip())

    # 批量查 sql1(sql1 整体失败 → 整批失败,所有行打 TAG_BATCH_FAILED)
    try:
        customer_identity_cache = batch_fetch_bind_records(bind_vip_ids)
    except Exception as exc:  # noqa: BLE001
        print(f"  sql1 整批查询失败: {exc}")
        return False

    # 批量查 sql2(sql2 整体失败 → 整批失败,所有行打 TAG_BATCH_FAILED)
    try:
        list_data_2 = batch_fetch_order_records(bind_vip_ids, old_cdp_ids)
    except Exception as exc:  # noqa: BLE001
        print(f"  sql2 整批查询失败: {exc}")
        return False

    by_cdp = build_lookup(list_data_2)

    # 逐行分析(单行异常不影响其他行,该行打 TAG_ROW_FAILED)
    for r in batch_rows:
        bind_vip_id = r[bind_idx].strip()
        old_cdp_id = r[cdp_idx].strip()
        customer_identity = customer_identity_cache.get(bind_vip_id)
        try:
            tag = analyze_row(bind_vip_id, old_cdp_id, customer_identity, by_cdp)
        except Exception as exc:  # noqa: BLE001
            print(f"  行分析失败 (BindVipId={bind_vip_id}): {exc}")
            tag = TAG_ROW_FAILED

        while len(r) < len(out_header):
            r.append("")
        r[temp_err_idx] = str(tag)
    return True


def write_rows(output_path, rows):
    """将一批行追加写入输出 CSV"""
    with open(output_path, "a", encoding="utf-8-sig", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerows(rows)


def finalize_batch_rows(batch_rows, temp_err_idx, out_header, tag):
    """把整批行的 TempErrType 置为指定 tag,并补齐列宽"""
    for r in batch_rows:
        while len(r) < len(out_header):
            r.append("")
        r[temp_err_idx] = str(tag)


def main():
    parser = argparse.ArgumentParser(description="过滤标签1中不紧急的数据(CSV 行批次流式处理)")
    parser.add_argument(
        "--source",
        default="",
        help="源 CSV 文件路径,省略时取 SOURCE_DIR 下的 tofilter_flag1.csv",
    )
    parser.add_argument(
        "--output",
        default="",
        help="输出 CSV 文件路径,省略时自动在源文件名后追加 _flag10",
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

    header = rows_all[0]
    if "BindVipId" not in header:
        raise ValueError("CSV 中未找到 BindVipId 列")
    if "Old_CdpId" not in header:
        raise ValueError("CSV 中未找到 Old_CdpId 列")

    bind_idx = header.index("BindVipId")
    cdp_idx = header.index("Old_CdpId")

    # 输出表头:沿用源表头
    out_header = list(header)
    if NEW_COLUMN not in out_header:
        out_header.append(NEW_COLUMN)
    temp_err_idx = out_header.index(NEW_COLUMN)

    # 先写表头(覆盖模式,确保每次运行产物干净)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(out_header)

    # 流式按批处理:每 CSV_BATCH_SIZE 行为一批
    total_rows = len(rows_all) - 1
    skipped_empty = 0
    processed = 0
    matched_total = 0
    not_equal_total = 0
    total_batches = (total_rows + CSV_BATCH_SIZE - 1) // CSV_BATCH_SIZE

    # 按批切分 rows_all[1:]
    batch_start = 1
    while batch_start < len(rows_all):
        batch_end = min(batch_start + CSV_BATCH_SIZE, len(rows_all))
        raw_batch = rows_all[batch_start:batch_end]

        batch_idx = (batch_start - 1) // CSV_BATCH_SIZE + 1
        print(f"\n[CSV 批次 {batch_idx}/{total_batches}] 处理源 CSV 第 {batch_start}-{batch_end - 1} 行")

        # 过滤空值,并复制出独立行(避免后续修改污染源列表)
        batch_rows = []
        for r in raw_batch:
            while len(r) < len(header):
                r.append("")
            bind_val = r[bind_idx].strip()
            cdp_val = r[cdp_idx].strip()
            if bind_val == "" or cdp_val == "":
                skipped_empty += 1
                continue
            batch_rows.append(list(r))

        if not batch_rows:
            batch_start = batch_end
            continue

        # 始终确保本批每行都会被写盘(无论成功失败)
        batch_ok = False
        try:
            batch_ok = process_one_batch(
                batch_rows, bind_idx, cdp_idx, out_header, temp_err_idx
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  [CSV 批次 {batch_idx}] 整体异常: {exc}")

        if not batch_ok:
            # 整批失败:把本批每行的 TempErrType 置为 TAG_BATCH_FAILED,再写盘
            finalize_batch_rows(batch_rows, temp_err_idx, out_header, TAG_BATCH_FAILED)

        # 写盘本批所有行
        write_rows(output_path, batch_rows)

        processed += len(batch_rows)
        matched_in_batch = sum(
            1 for r in batch_rows
            if len(r) > temp_err_idx and r[temp_err_idx] == str(TAG_EQUAL)
        )
        not_equal_in_batch = sum(
            1 for r in batch_rows
            if len(r) > temp_err_idx and r[temp_err_idx] == str(TAG_NOT_EQUAL)
        )
        no_data_in_batch = sum(
            1 for r in batch_rows
            if len(r) > temp_err_idx and r[temp_err_idx] == str(TAG_NO_DATA)
        )
        row_failed = sum(
            1 for r in batch_rows
            if len(r) > temp_err_idx and r[temp_err_idx] == str(TAG_ROW_FAILED)
        )
        batch_failed = sum(
            1 for r in batch_rows
            if len(r) > temp_err_idx and r[temp_err_idx] == str(TAG_BATCH_FAILED)
        )
        matched_total += matched_in_batch
        not_equal_total += not_equal_in_batch
        print(
            f"  [CSV 批次 {batch_idx}] 写入 {len(batch_rows)} 行 "
            f"(相等10={matched_in_batch}, 不等20={not_equal_in_batch}, "
            f"缺数据0={no_data_in_batch}, 行级失败={row_failed}, 整批失败={batch_failed})"
        )

        batch_start = batch_end

    print(
        f"\n处理完成: 共 {total_rows} 行,跳过空值 {skipped_empty} 行,"
        f"处理 {processed} 行,匹配(标签=10) {matched_total} 行,"
        f"价格不等(标签=20) {not_equal_total} 行"
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