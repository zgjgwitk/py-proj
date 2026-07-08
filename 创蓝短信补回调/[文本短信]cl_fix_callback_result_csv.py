"""
创蓝短信回调结果补数据脚本

功能：
1. 解析 file 目录下的 csv 文件
2. 读取 'client_msg_id','状态报告' 列
3. 更新 ES 中的数据

字段映射：
- 'client_msg_id' -> gatewayId
- '状态报告' -> resStatusCode (失败=500, 成功=SUCCESS)
- '状态报告' -> resStatusMsg
"""

import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from elasticsearch import Elasticsearch

# 配置
INPUT_FILE = r"D:\Github\py-proj\创蓝短信补回调\file\26-05.csv"
# ES_HOST = "http://192.168.12.124:88/@q1cloud:base.es.biz-10.10.0.8:9200/"  # ES Q1地址
ES_HOST = "http://192.168.12.124:88/@qcloud:base.es.biz-172.21.65.197:9200/"  # ES Q云地址
ES_INDEX = "esmsgsms2605"  # ES 索引名
BRAND_ID = 7072
DRY_RUN = False  # True=只输出日志不实际更新, False=实际更新
BATCH_SIZE = 50  # 每个批次执行条数（减小以避免连接超时）
BATCH_WAIT_SEC = 3  # 每个批次执行间隔时间 单位s


REQUIRED_COLUMNS = ["client_msg_id", "状态报告"]



def connect_es() -> Elasticsearch:
    """连接 ES"""
    return Elasticsearch([ES_HOST], timeout=30, max_retries=3, retry_on_timeout=True)


def read_input_file(file_path: str) -> pd.DataFrame:
    """读取 CSV/Excel 文件"""
    suffix = Path(file_path).suffix.lower()

    if suffix == ".csv":
        df = None
        last_error = None
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                df = pd.read_csv(file_path, dtype=str, encoding=encoding)
                break
            except UnicodeDecodeError as exc:
                last_error = exc
        if df is None:
            raise ValueError(f"CSV 文件编码解析失败: {last_error}")
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(file_path, dtype=str)
    else:
        raise ValueError(f"不支持的文件类型: {suffix}，请使用 .csv、.xlsx 或 .xls 文件")

    df.columns = [str(col).strip() for col in df.columns]

    # 检查必要的列是否存在
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"文件缺少必要的列: {missing_columns}")

    return df


def clean_gateway_id(gateway_id: str) -> str:
    """清理client_msg_id，去掉开头的 '：' 字符"""
    if pd.isna(gateway_id):
        return ""
    gateway_id = str(gateway_id).strip()
    if gateway_id.startswith("："):
        gateway_id = gateway_id[1:]
    elif gateway_id.startswith("'"):
        gateway_id = gateway_id[1:]
    return gateway_id


def parse_datetime(value) -> str | None:
    """解析日期时间"""
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%S")
    # 尝试解析字符串
    try:
        dt = pd.to_datetime(value)
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return str(value)


def build_update_doc(row: pd.Series) -> dict | None:
    """构建 ES 更新文档，如果 状态报告 为''则返回 None"""

    res_status = 4
    res_status_code = str(row["状态报告"]).strip() if not pd.isna(row["状态报告"]) else ""

    # 如果状态为'未知'，跳过此条数据
    if res_status_code == "":
        return None
    
    if res_status_code == "DELIVRD":
        res_status_code = "SUCCESS"
        res_status = 3

    doc = {
        "resStatus": res_status,
        "resStatusCode": res_status_code,
        "resStatusMsg": str(row["状态报告"]).strip() if not pd.isna(row["状态报告"]) else "",
    }
    return doc


def search_es_docs_batch(es: Elasticsearch, items: list) -> dict:
    """
    批量查询 ES 文档（使用 terms 查询 gatewayId）

    Args:
        es: ES 客户端
        items: 查询条件列表，每个元素为 gateway_id

    Returns:
        dict: key=gateway_id, value=es_doc 或 None
    """
    if not items:
        return {}

    # 提取所有不同的 gateway_id
    gateway_ids = list(set(item for item in items if item))

    # 使用 terms 查询所有 gateway_id
    query = {
        "query": {
            "bool": {
                "must": [
                    {"terms": {"gatewayId": gateway_ids}},
                    {"term": {"resStatus": 1}},
                    {"term": {"brandId": BRAND_ID}},
                    {"terms": {"serviceType": [1, 2]}}
                ]
            }
        },
        "_source": ["gatewayId"],  # 只返回 gatewayId 字段，减少传输数据量
        "size": len(gateway_ids),  # 不需要放大，精确匹配
    }
    result = es.search(index=ES_INDEX, body=query)
    hits = result.get("hits", {}).get("hits", [])

    # 构建结果字典
    results = {}
    for item in items:
        results[item] = None

    for hit in hits:
        source = hit["_source"]
        key = source.get("gatewayId")
        if key in results:
            results[key] = hit

    return results


def update_es_docs_batch(es: Elasticsearch, update_list: list) -> tuple:
    """
    批量更新 ES 文档

    Args:
        es: ES 客户端
        update_list: 更新列表，每个元素为 (doc_id, doc)

    Returns:
        tuple: (成功数, 失败数)
    """
    if not update_list:
        return 0, 0

    success = 0
    failed = 0

    # 构建 bulk 请求体
    bulk_body = []
    for doc_id, doc in update_list:
        bulk_body.append({"update": {"_index": ES_INDEX, "_id": doc_id}})
        bulk_body.append({"doc": doc})
        # print(f"[update] doc_id={doc_id}, resStatus={doc['resStatus']}, resStatusCode={doc['resStatusCode']}, resStatusMsg={doc['resStatusMsg']}")

    # 执行批量更新
    try:
        result = es.bulk(body=bulk_body)
        for item in result.get("items", []):
            if item.get("update", {}).get("result") in ["updated", "noop"]:
                success += 1
            else:
                failed += 1
    except Exception as e:
        print(f"批量更新失败: {e}")
        failed = len(update_list)

    return success, failed


def main():
    print(f"开始处理文件: {INPUT_FILE}")
    if DRY_RUN:
        print("=" * 50)
        print("[DRY-RUN 模式] 仅输出日志，不实际更新 ES 数据")
        print("=" * 50)

    # 检查文件是否存在
    if not os.path.exists(INPUT_FILE):
        print(f"文件不存在: {INPUT_FILE}")
        return

    # 读取 CSV/Excel
    df = read_input_file(INPUT_FILE)
    print(f"共读取 {len(df)} 条记录")

    # 连接 ES
    es = connect_es()
    print(f"已连接到 ES: {ES_HOST}")

    # 统计
    total = len(df)
    success = 0
    not_found = 0
    failed = 0
    skipped = 0

    # 构建查询条件列表和更新文档列表
    search_items = []  # [(gateway_id), ...]
    rows_data = []  # [(index, gateway_id, doc), ...]

    for index, row in df.iterrows():
        doc = build_update_doc(row)

        # 跳过状态为'3'的数据
        if doc is None:
            skipped += 1
            print(f"[{index + 1}/{total}] 跳过: 状态为'3'")
            continue

        # 从表格行数据获取查询条件
        gateway_id = clean_gateway_id(row["client_msg_id"])

        search_items.append(gateway_id)
        rows_data.append((index, gateway_id, doc))

    # 查询一批、跟新一批
    batch_size = BATCH_SIZE
    processed_count = 0

    for i in range(0, len(search_items), batch_size):
        batch = search_items[i:i + batch_size]
        batch_rows = rows_data[i:i + batch_size]

        # 查询本批次
        batch_results = search_es_docs_batch(es, batch)
        hit_count = sum(1 for v in batch_results.values() if v is not None)
        print(f"批次 {(i // batch_size) + 1} 查询完成: 共查询 {len(batch)} 条, 命中 {hit_count} 条")

        # 构建更新列表
        update_list = []  # [(doc_id, doc), ...]
        for index, gateway_id, doc in batch_rows:
            key = gateway_id
            es_doc = batch_results.get(key)

            if es_doc is None:
                not_found += 1
                print(f"[{index + 1}/{total}] 未找到: gatewayId={gateway_id}")
                continue

            doc_id = es_doc["_id"]

            if DRY_RUN:
                print(f"[{index + 1}/{total}] [DRY-RUN] 查找到: doc_id={doc_id}")
                success += 1
            else:
                update_list.append((doc_id, doc))

        # 更新本批次
        if not DRY_RUN and update_list:
            batch_success, batch_failed = update_es_docs_batch(es, update_list)
            success += batch_success
            failed += batch_failed
            print(f"批次 {(i // batch_size) + 1} 更新完成: 成功={batch_success}, 失败={batch_failed}")

        time.sleep(BATCH_WAIT_SEC)  # 间隔 s

        processed_count += len(batch)

    # 输出统计
    print("\n" + "=" * 50)
    print(f"处理完成!")
    print(f"总计: {total}")
    print(f"成功: {success}")
    print(f"未找到: {not_found}")
    print(f"失败: {failed}")
    print(f"跳过: {skipped}")
    print("=" * 50)


if __name__ == "__main__":
    main()
