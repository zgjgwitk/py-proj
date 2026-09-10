"""
创蓝短信补回调结果脚本 - 根据 CSV/Excel 日统计补足回调状态 (按天循环)

功能:
1. 从 CSV 或 Excel 文件读取每日目标 (成功/失败/未知数)
2. 从文件名提取 ES 索引名 (日统计yyyy-MM.csv -> esmsgsmsYYMM)
3. 按天循环, 每天独立执行: 统计 -> 校验 -> 搜索 -> 批量更新 -> 复核
4. 使用 if_seq_no + if_primary_term 乐观锁, 防止 ES 副本同步延迟导致的重复更新
5. 单天失败不中断整体, 记录后继续下一天, 最后打印所有天汇总

字段映射:
- resStatus=3: 成功 -> resStatusCode=SUCCESS, resStatusMsg=发送成功
- resStatus=4: 失败 -> resStatusCode=500, resStatusMsg=发送失败
- resStatus=1: 未知, 保留不动 (目标数量之外的部分)
"""

import os
import re
import time

import pandas as pd
from elasticsearch import Elasticsearch

# ============== 脚本配置 ==============
ES_HOST = "http://192.168.12.124:88/@qcloud:base.es.biz-172.21.65.197:9200/"  # ES 地址
# ES_HOST_Q1 = "http://192.168.12.124:88/@q1cloud:base.es.biz-10.10.0.8:9200/"  # ES-Q1 地址
# ES_HOST_DEV = "http://192.168.128.142:9200/"  # ES-dev 地址
# ES_HOST_QCLOUD = "http://192.168.12.124:88/@qcloud:base.es.biz-172.21.65.197:9200/"  # ES-q云 地址
BRAND_ID = 132
SMS_CHAN = 20  # 创蓝渠道, 固定 20
# SERVICE_TYPES = [5]  # 文本短信: [1, 2], 视频短信: [5]
SERVICE_TYPES = [1, 2]  # 文本短信: [1, 2], 视频短信: [5]
SERVICE_TYPE1_ACCOUNT = "N445091_N6682443"  # serviceType=1 对应的日报账号
SERVICE_TYPE2_ACCOUNT = "M245138_M6771238"  # serviceType=2 对应的日报账号，请按实际情况配置
EXCEL_FILE = r"D:\Github\py-proj\创蓝短信补回调\file\日统计26-01.csv"  # 配置文件，支持 CSV/XLS/XLSX

# 执行控制
DRY_RUN = False  # True=所有天都只打印计划, False=所有天都真实执行
BATCH_SIZE = 500  # search_after 每批查询条数
BATCH_WAIT_SEC = 1  # 批次间等待秒数, 降低 ES 压力
MAX_UPDATE_LIMIT = 50000  # 单天最多更新数量, 防止配置填错导致大批量误更新
CONFIRM_WAIT_SEC = 5  # DRY_RUN=False 时, 真实执行前等待秒数, 给用户取消的机会

# 状态码常量
STATUS_UNKNOWN = 1
STATUS_SUBMIT_FAILED = 2  # 提交失败, 不在统计范围内
STATUS_SUCCESS = 3
STATUS_FAILED = 4

# 更新模板
UPDATE_DOC_SUCCESS = {
    "resStatus": STATUS_SUCCESS,
    "resStatusCode": "SUCCESS",
    "resStatusMsg": "发送成功",
}
UPDATE_DOC_FAILED = {
    "resStatus": STATUS_FAILED,
    "resStatusCode": "500",
    "resStatusMsg": "发送失败",
}


def connect_es() -> Elasticsearch:
    """连接 ES"""
    return Elasticsearch([ES_HOST], timeout=30, max_retries=3, retry_on_timeout=True)


def extract_es_index_from_filename(file_path: str) -> str:
    """
    从文件名提取 ES 索引名

    例:
        日统计2025-09.csv -> esmsgsms2509
        日统计26-01.csv -> esmsgsms2601
    """
    file_name = os.path.basename(file_path)
    match = re.search(r"(?<!\d)(\d{2}|\d{4})-(\d{2})(?!\d)", file_name)
    if not match:
        raise ValueError(f"文件名 {file_name} 不包含 yyyy-MM 或 yy-MM 格式的年月, 无法提取索引名")
    year, month = match.group(1), match.group(2)
    return f"esmsgsms{year[-2:]}{month}"


def load_excel_config(file_path: str) -> list[dict]:
    """
    读取 CSV/Excel 配置, 返回每日配置列表

    Returns:
        [
            {
                "date": "2025-09-30",
                "req_time_day": 20250930,
                "success": 41705,
                "failed": 2478,
                "unknown": 515,
                "total": 44698,
            },
            ...
        ]

    跳过规则:
        - 必要列缺失 -> 抛错
        - 日期为空 -> 跳过
        - 发送总数为 0 -> 跳过 (无意义)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"配置文件不存在: {file_path}")

    suffix = os.path.splitext(file_path)[1].lower()
    if suffix == ".csv":
        # utf-8-sig 同时兼容普通 UTF-8 和带 BOM 的 CSV；部分 Windows
        # 导出文件使用 GB18030，因此解码失败时自动回退。
        try:
            df = pd.read_csv(file_path, dtype=str, encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, dtype=str, encoding="gb18030")
    elif suffix in (".xls", ".xlsx"):
        df = pd.read_excel(file_path, dtype=str)
    else:
        raise ValueError(f"不支持的配置文件格式: {suffix or '无扩展名'}，仅支持 CSV/XLS/XLSX")
    df.columns = [str(c).strip() for c in df.columns]  # 去除列名首尾空白

    required = ["日期", "成功数", "失败数", "未知数"]
    if any(service_type in (1, 2) for service_type in SERVICE_TYPES):
        required.append("账号")
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"配置文件缺少必要列: {missing}")

    configs = []
    for idx, row in df.iterrows():
        date_str = str(row["日期"]).strip() if not pd.isna(row["日期"]) else ""
        if not date_str or date_str == "nan":
            print(f"  [跳过] 第 {idx + 1} 行日期为空")
            continue

        # 解析数字 (容错: Excel 数字可能是 "0", "0.0", "0.0000" 等)
        try:
            success = int(float(str(row["成功数"])))
            failed = int(float(str(row["失败数"])))
            unknown = int(float(str(row["未知数"])))
        except (ValueError, TypeError) as e:
            print(f"  [跳过] 第 {idx + 1} 行 ({date_str}) 数字解析失败: {e}")
            continue

        total = success + failed + unknown
        if total == 0:
            print(f"  [跳过] 第 {idx + 1} 行 ({date_str}) 发送总数为 0")
            continue

        # 日期转 yyyyMMdd int: 2025-09-30 -> 20250930
        try:
            req_time_day = int(date_str.replace("-", "").replace("/", ""))
        except ValueError:
            print(f"  [跳过] 第 {idx + 1} 行日期格式无法解析: {date_str}")
            continue

        account = str(row["账号"]).strip() if "账号" in df.columns and not pd.isna(row["账号"]) else ""
        configs.append({
            "account": account,
            "date": date_str,
            "req_time_day": req_time_day,
            "success": success,
            "failed": failed,
            "unknown": unknown,
            "total": total,
        })

    if not configs:
        raise ValueError(f"配置文件中没有有效数据行: {file_path}")

    return configs


def build_base_filter(service_type: int, req_time_day: int | None = None) -> dict:
    """
    构造所有 ES 查询共享的 bool 过滤对象: brandId + smsChan + serviceType + (可选) reqTimeDay

    排除 resStatus=2 (提交失败, 不在统计范围内)

    Returns:
        bool 查询 dict, 形如 {"bool": {"filter": [...], "must_not": [...]}}
        调用方通过 dict 合并添加额外的 resStatus 过滤
    """
    filters = [
        {"term": {"brandId": BRAND_ID}},
        {"term": {"smsChan": SMS_CHAN}},
        {"term": {"serviceType": service_type}},
    ]
    if req_time_day is not None:
        filters.append({"term": {"reqTimeDay": req_time_day}})
    return {
        "bool": {
            "filter": filters,
            "must_not": [{"term": {"resStatus": STATUS_SUBMIT_FAILED}}],
        }
    }


def count_by_res_status(
    es: Elasticsearch,
    es_index: str,
    service_type: int,
    req_time_day: int | None = None,
) -> dict:
    """
    按 brandId + smsChan + serviceType + (可选) reqTimeDay 统计各 resStatus 的文档数量

    Returns:
        {
            "total": int,         # 总数
            "success": int,       # resStatus=3
            "failed": int,        # resStatus=4
            "unknown": int,       # resStatus=1
            "other": int,         # 其他状态
        }
    """
    base_query = build_base_filter(service_type, req_time_day)  # bool 查询 dict

    def search_count(query: dict) -> int:
        """执行 size=0 计数查询, 返回 total.value"""
        resp = es.search(
            index=es_index, size=0, track_total_hits=True, body={"query": query}
        )
        return resp["hits"]["total"]["value"]

    # 总数查询: 直接用 base_query
    total = search_count(base_query)

    # resStatus=3 成功: 在 base_query 的 filter 上追加 resStatus
    success_query = {
        "bool": {
            **base_query["bool"],
            "filter": base_query["bool"]["filter"] + [{"term": {"resStatus": STATUS_SUCCESS}}],
        }
    }
    success = search_count(success_query)

    # resStatus=4 失败
    failed_query = {
        "bool": {
            **base_query["bool"],
            "filter": base_query["bool"]["filter"] + [{"term": {"resStatus": STATUS_FAILED}}],
        }
    }
    failed = search_count(failed_query)

    # resStatus=1 未知
    unknown_query = {
        "bool": {
            **base_query["bool"],
            "filter": base_query["bool"]["filter"] + [{"term": {"resStatus": STATUS_UNKNOWN}}],
        }
    }
    unknown = search_count(unknown_query)

    # 其他状态: 不在 (1, 2, 3, 4) 范围
    other_query = {
        "bool": {
            **base_query["bool"],
            "must_not": base_query["bool"]["must_not"] + [
                {"terms": {"resStatus": [STATUS_UNKNOWN, STATUS_SUCCESS, STATUS_FAILED]}}
            ],
        }
    }
    other = search_count(other_query)

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "unknown": unknown,
        "other": other,
    }


def validate_before_update(
    stats: dict,
    target_success: int,
    target_failed: int,
    target_unknown: int,
    max_update_limit: int,
) -> tuple:
    """
    更新前校验, 返回 (need_success, need_failed) 表示需要补的数量

    校验规则 (见方案文档第 2 节):
    1. 当前总数 < target_total -> 退出
    2. 当前成功数 > target_success -> 退出 (不做反向修正)
    3. 当前失败数 > target_failed -> 退出
    4. 当前未知数 < need_update_total + target_unknown -> 退出
    5. need_update_total > max_update_limit -> 退出
    """
    target_total = target_success + target_failed + target_unknown

    if stats["total"] < target_total:
        raise SystemExit(
            f"当前总数 {stats['total']} < 目标总数 {target_total}, 退出"
        )

    if stats["success"] > target_success:
        raise SystemExit(
            f"当前成功数 {stats['success']} > 目标成功数 {target_success}, "
            f"脚本只从未知改成功, 不做反向修正, 退出"
        )

    if stats["failed"] > target_failed:
        raise SystemExit(
            f"当前失败数 {stats['failed']} > 目标失败数 {target_failed}, "
            f"脚本只从未知改失败, 不做反向修正, 退出"
        )

    need_success = target_success - stats["success"]
    need_failed = target_failed - stats["failed"]
    need_update_total = need_success + need_failed

    if stats["unknown"] < need_update_total + target_unknown:
        raise SystemExit(
            f"当前未知数 {stats['unknown']} < "
            f"待更新数 {need_update_total} + 目标未知数 {target_unknown}, "
            f"保证更新后能保留 {target_unknown} 条未知, 退出"
        )

    if need_update_total > max_update_limit:
        raise SystemExit(
            f"待更新总数 {need_update_total} > MAX_UPDATE_LIMIT {max_update_limit}, "
            f"请调整配置或拆分批次, 退出"
        )

    return need_success, need_failed


def search_unknown_docs(
    es: Elasticsearch,
    es_index: str,
    service_type: int,
    limit: int,
    req_time_day: int | None = None,
):
    """
    使用 search_after 分页查询 resStatus=1 的文档, 按 reqTime ASC, _id ASC 排序

    Args:
        limit: 最多取多少条

    Yields:
        (doc_id, seq_no, primary_term) 的生成器
    """
    base_query = build_base_filter(service_type, req_time_day)
    query = {
        "bool": {
            **base_query["bool"],
            "filter": base_query["bool"]["filter"] + [{"term": {"resStatus": STATUS_UNKNOWN}}],
        }
    }

    search_after = None
    remaining = limit

    while remaining > 0:
        size = min(BATCH_SIZE, remaining)
        body = {
            "query": query,
            "size": size,
            "_source": ["resStatus", "reqTime"],  # 只取必要字段, 避免 body 大字段撑爆响应
            "seq_no_primary_term": True,  # 启用 _seq_no + _primary_term, 配合乐观锁
            "sort": [
                {"reqTime": "asc"},
                {"_id": "asc"},
            ],
        }
        if search_after is not None:
            body["search_after"] = search_after

        resp = es.search(index=es_index, body=body)
        hits = resp["hits"]["hits"]
        if not hits:
            break

        for hit in hits:
            yield hit["_id"], hit["_seq_no"], hit["_primary_term"]

        search_after = hits[-1]["sort"]
        remaining -= len(hits)

        if len(hits) < size:
            # 已经查完
            break


def bulk_update_docs(es: Elasticsearch, es_index: str, actions: list) -> dict:
    """
    批量更新, 使用 if_seq_no + if_primary_term 做乐观锁

    Args:
        actions: [(doc_id, seq_no, primary_term, doc), ...]

    Returns:
        {
            "updated": int,         # 实际更新成功数
            "conflict": int,        # 版本冲突 (脚本期望范围内的跳过)
            "failed": int,          # 其他失败
        }
    """
    if not actions:
        return {"updated": 0, "conflict": 0, "failed": 0}

    bulk_body = []
    for doc_id, seq_no, primary_term, doc in actions:
        bulk_body.append(
            {
                "update": {
                    "_index": es_index,
                    "_id": doc_id,
                    "if_seq_no": seq_no,
                    "if_primary_term": primary_term,
                }
            }
        )
        bulk_body.append({"doc": doc})

    result = es.bulk(body=bulk_body)

    updated = 0
    conflict = 0
    failed = 0
    for item in result.get("items", []):
        update_info = item.get("update", {})
        # 解析 status 字段, 409 表示版本冲突
        status = update_info.get("status", 0)
        if status == 200 or status == 201:
            updated += 1
        elif status == 409:
            conflict += 1
        else:
            failed += 1
            error = update_info.get("error", {})
            print(f"  [更新失败] doc_id={update_info.get('_id')}, status={status}, error={error}")

    return {"updated": updated, "conflict": conflict, "failed": failed}


def print_stats(title: str, stats: dict) -> None:
    """打印统计信息"""
    print(f"\n--- {title} ---")
    print(f"  总数:        {stats['total']}")
    print(f"  成功(3):     {stats['success']}")
    print(f"  失败(4):     {stats['failed']}")
    print(f"  未知(1):     {stats['unknown']}")
    print(f"  其他:        {stats['other']}")


def print_comparison(
    before: dict,
    after: dict,
    target_success: int,
    target_failed: int,
    target_unknown: int,
) -> None:
    """打印更新前后对比表"""
    target_total = target_success + target_failed + target_unknown
    print("\n" + "=" * 70)
    print(f"{'项目':<20}{'目标数量':>12}{'更新前':>12}{'更新后':>12}{'差异':>12}")
    print("-" * 70)

    rows = [
        ("成功 resStatus=3", target_success, before["success"], after["success"]),
        ("失败 resStatus=4", target_failed, before["failed"], after["failed"]),
        ("未知 resStatus=1", target_unknown, before["unknown"], after["unknown"]),
        ("总数", target_total, before["total"], after["total"]),
    ]
    for name, target, b, a in rows:
        diff = a - b
        print(f"{name:<20}{target:>12}{b:>12}{a:>12}{diff:>+12}")

    print("=" * 70)

    # 标记异常
    if after["success"] != target_success:
        print(f"[异常] 更新后成功数 {after['success']} != 目标 {target_success}")
    if after["failed"] != target_failed:
        print(f"[异常] 更新后失败数 {after['failed']} != 目标 {target_failed}")
    if after["unknown"] != target_unknown:
        print(f"[异常] 更新后未知数 {after['unknown']} != 目标 {target_unknown}")


def process_one_day(
    es: Elasticsearch,
    es_index: str,
    service_type: int,
    cfg: dict,
    dry_run: bool,
    batch_size: int,
    batch_wait_sec: int,
    max_update_limit: int,
) -> dict:
    """
    处理一天的完整流程

    Args:
        cfg: {date, req_time_day, success, failed, unknown, total}

    Returns:
        {
            "date": str,
            "req_time_day": int,
            "status": "success" | "skipped" | "failed",
            "before_stats": dict,
            "after_stats": dict | None,
            "need_success": int,
            "need_failed": int,
            "updated": int,
            "conflict": int,
            "failed_bulk": int,
            "message": str,
        }
    """
    date = cfg["date"]
    req_time_day = cfg["req_time_day"]
    target_success = cfg["success"]
    target_failed = cfg["failed"]
    target_unknown = cfg["unknown"]

    print(f"\nserviceType={service_type}, 账号={cfg.get('account', '-')}, 日期: {date}, reqTimeDay={req_time_day}")
    print(f"目标: 成功={target_success}, 失败={target_failed}, 未知={target_unknown}, 合计={cfg['total']}")

    # 1. 统计
    before_stats = count_by_res_status(es, es_index, service_type, req_time_day)
    print_stats(f"{date} 更新前统计", before_stats)

    # 2. 校验
    try:
        need_success, need_failed = validate_before_update(
            before_stats, target_success, target_failed, target_unknown, max_update_limit
        )
    except SystemExit as e:
        print(f"[校验失败] {e}")
        return {
            "date": date,
            "req_time_day": req_time_day,
            "status": "failed",
            "before_stats": before_stats,
            "after_stats": None,
            "need_success": 0,
            "need_failed": 0,
            "updated": 0,
            "conflict": 0,
            "failed_bulk": 0,
            "message": str(e),
        }

    need_update_total = need_success + need_failed
    print(f"\n[校验通过] 需要补成功: {need_success}, 需要补失败: {need_failed}, 合计: {need_update_total}")

    if need_update_total == 0:
        print("\n[无需更新] 当前各状态数量已满足目标, 跳过本天")
        return {
            "date": date,
            "req_time_day": req_time_day,
            "status": "skipped",
            "before_stats": before_stats,
            "after_stats": before_stats,
            "need_success": 0,
            "need_failed": 0,
            "updated": 0,
            "conflict": 0,
            "failed_bulk": 0,
            "message": "已满足目标",
        }

    # 3. 查询待更新文档
    print(f"\n开始查询 resStatus=1 的文档, 计划取 {need_update_total} 条...")
    candidates = list(
        search_unknown_docs(es, es_index, service_type, need_update_total, req_time_day)
    )
    print(f"实际查询到 {len(candidates)} 条待更新文档")

    if len(candidates) < need_update_total:
        print(
            f"[警告] 查询到的待更新文档 {len(candidates)} < 计划 {need_update_total}, "
            f"实际能补的数量将少于目标"
        )
        if len(candidates) <= need_success:
            need_success = len(candidates)
            need_failed = 0
        else:
            need_failed = len(candidates) - need_success

    # 4. 分配: 前 need_success 条改成功, 后 need_failed 条改失败
    actions = []
    for i, (doc_id, seq_no, primary_term) in enumerate(candidates):
        if i < need_success:
            doc = UPDATE_DOC_SUCCESS
        else:
            doc = UPDATE_DOC_FAILED
        actions.append((doc_id, seq_no, primary_term, doc))

    print(f"  计划改为成功: {need_success} 条")
    print(f"  计划改为失败: {need_failed} 条")

    # 5. DRY_RUN: 不执行更新
    if dry_run:
        print("\n[DRY-RUN] 打印前 5 条样例:")
        for doc_id, seq_no, primary_term, doc in actions[:5]:
            print(f"  doc_id={doc_id}, seq_no={seq_no}, primary_term={primary_term}, doc={doc}")
        if len(actions) > 5:
            print(f"  ... 其余 {len(actions) - 5} 条略")

        return {
            "date": date,
            "req_time_day": req_time_day,
            "status": "dry_run",
            "before_stats": before_stats,
            "after_stats": None,
            "need_success": need_success,
            "need_failed": need_failed,
            "updated": 0,
            "conflict": 0,
            "failed_bulk": 0,
            "message": f"DRY_RUN 计划更新 {len(actions)} 条",
        }

    # 6. 分批 bulk 更新
    print(f"\n开始执行 bulk 更新, 每批 {batch_size} 条...")
    total_updated = 0
    total_conflict = 0
    total_failed = 0
    batch_index = 0

    for i in range(0, len(actions), batch_size):
        batch = actions[i : i + batch_size]
        batch_index += 1
        result = bulk_update_docs(es, es_index, batch)
        total_updated += result["updated"]
        total_conflict += result["conflict"]
        total_failed += result["failed"]
        print(
            f"  批次 {batch_index}: 更新={result['updated']}, "
            f"冲突={result['conflict']}, 失败={result['failed']}"
        )
        time.sleep(batch_wait_sec)

    print(f"\n[更新完成] 实际更新={total_updated}, 版本冲突跳过={total_conflict}, 失败={total_failed}")
    print(f"  (版本冲突是预期内的, 表示该文档在脚本执行期间被其他流程修改过)")

    # 7. 更新后复核
    after_stats = count_by_res_status(es, es_index, service_type, req_time_day)
    print_stats(f"{date} 更新后统计", after_stats)
    print_comparison(before_stats, after_stats, target_success, target_failed, target_unknown)

    return {
        "date": date,
        "req_time_day": req_time_day,
        "status": "success",
        "before_stats": before_stats,
        "after_stats": after_stats,
        "need_success": need_success,
        "need_failed": need_failed,
        "updated": total_updated,
        "conflict": total_conflict,
        "failed_bulk": total_failed,
        "message": "完成",
    }


def main():
    print("=" * 60)
    print("创蓝短信补回调结果脚本 - 按 CSV/Excel 日统计补差额 (按天循环)")
    print("=" * 60)
    print(f"ES 地址:    {ES_HOST}")
    print(f"配置文件:   {EXCEL_FILE}")
    print(f"brandId:    {BRAND_ID}")
    print(f"smsChan:    {SMS_CHAN} (创蓝)")
    print(f"serviceType:{SERVICE_TYPES}")
    print(f"type 1 账号: {SERVICE_TYPE1_ACCOUNT or '(未配置)'}")
    print(f"type 2 账号: {SERVICE_TYPE2_ACCOUNT or '(未配置)'}")
    print(f"DRY_RUN:    {DRY_RUN}")

    # 1. 解析文件名 -> ES 索引
    try:
        es_index = extract_es_index_from_filename(EXCEL_FILE)
        print(f"ES 索引:    {es_index} (从文件名提取)")
    except ValueError as e:
        print(f"[错误] {e}")
        return

    # 2. 读取 CSV/Excel -> 每日配置
    try:
        configs = load_excel_config(EXCEL_FILE)
    except (FileNotFoundError, ValueError) as e:
        print(f"[错误] 读取配置文件失败: {e}")
        return

    print(f"\n共解析到 {len(configs)} 行有效配置")

    # 3. DRY_RUN 提示
    if DRY_RUN:
        print("\n" + "!" * 60)
        print("!  [DRY-RUN 模式] 所有天仅统计和打印计划, 不执行 ES 更新")
        print("!" * 60)
    else:
        print("\n" + "!" * 60)
        print(f"!  [真实执行模式] 所有天都将执行 ES bulk 更新")
        print(f"!  将在 {CONFIRM_WAIT_SEC} 秒后开始执行, 按 Ctrl+C 取消")
        print("!" * 60)
        time.sleep(CONFIRM_WAIT_SEC)

    # 4. 连接 ES
    es = connect_es()
    print(f"\n已连接到 ES: {ES_HOST}")

    # 5. SERVICE_TYPES 作为外层循环，每次只处理一种 serviceType
    account_by_service_type = {
        1: SERVICE_TYPE1_ACCOUNT,
        2: SERVICE_TYPE2_ACCOUNT,
    }
    summary = []
    for service_type in SERVICE_TYPES:
        if service_type in account_by_service_type:
            account = account_by_service_type[service_type].strip()
            if not account:
                print(f"\n[跳过] serviceType={service_type} 未配置对应账号")
                continue
            service_configs = [cfg for cfg in configs if cfg["account"] == account]
        else:
            account = ""
            service_configs = configs

        if not service_configs:
            print(
                f"\n[跳过] serviceType={service_type} 在配置文件中没有匹配账号 "
                f"{account!r} 的数据"
            )
            continue

        print(f"\n{'#' * 70}")
        print(
            f"开始处理 serviceType={service_type}, 账号={account or '(无需匹配)'}, "
            f"共 {len(service_configs)} 天"
        )
        print(f"{'#' * 70}")

        total_days = len(service_configs)
        for i, cfg in enumerate(service_configs, 1):
            print(f"\n{'=' * 60}")
            print(f"[{i}/{total_days}] serviceType={service_type}, 开始处理 {cfg['date']}")
            print(f"{'=' * 60}")

            try:
                result = process_one_day(
                    es,
                    es_index,
                    service_type,
                    cfg,
                    DRY_RUN,
                    BATCH_SIZE,
                    BATCH_WAIT_SEC,
                    MAX_UPDATE_LIMIT,
                )
            except Exception as e:
                print(f"[异常] serviceType={service_type}, {cfg['date']} 处理失败: {e}")
                result = {
                    "date": cfg["date"],
                    "req_time_day": cfg["req_time_day"],
                    "status": "failed",
                    "before_stats": None,
                    "after_stats": None,
                    "need_success": cfg["success"],
                    "need_failed": cfg["failed"],
                    "updated": 0,
                    "conflict": 0,
                    "failed_bulk": 0,
                    "message": f"异常: {e}",
                }

            result["service_type"] = service_type
            result["account"] = account
            summary.append(result)

    # 6. 汇总
    print(f"\n{'=' * 70}")
    print(f"所有天处理完成, 汇总:")
    print(f"{'=' * 70}")
    print(
        f"{'类型':<6}{'日期':<14}{'状态':<10}{'当前数':<8}{'计划':<8}{'更新':<8}{'冲突':<6}{'失败':<6}{'备注'}"
    )
    print("-" * 70)
    for r in summary:
        if r["status"] == "failed":
            plan = "-"
            updated = "-"
        elif r["status"] == "dry_run":
            plan = r["need_success"] + r["need_failed"]
            updated = "-"
        else:
            plan = r["need_success"] + r["need_failed"]
            updated = r["updated"]
        msg = r["message"][:30] + ("..." if len(r["message"]) > 30 else "")
        print(
            f"{r['service_type']:<6}{r['date']:<14}{r['status']:<10}{r.get('before_stats', {}).get('total', '-'):<8}"
            f"{str(plan):<8}{str(updated):<8}{r['conflict']:<6}{r['failed_bulk']:<6}{msg}"
        )

    # 7. 统计
    success_count = sum(1 for r in summary if r["status"] == "success")
    dry_run_count = sum(1 for r in summary if r["status"] == "dry_run")
    skipped_count = sum(1 for r in summary if r["status"] == "skipped")
    failed_count = sum(1 for r in summary if r["status"] == "failed")
    total_updated_all = sum(r["updated"] for r in summary)
    total_conflict_all = sum(r["conflict"] for r in summary)
    total_failed_all = sum(r["failed_bulk"] for r in summary)

    print("-" * 70)
    print(f"成功: {success_count}, DRY_RUN: {dry_run_count}, 跳过: {skipped_count}, 失败: {failed_count}")
    print(f"累计: 更新={total_updated_all}, 冲突={total_conflict_all}, 失败={total_failed_all}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
