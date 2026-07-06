"""
联麓短信回调结果补数据脚本

功能：
1. 解析 file 目录下的 inport.xlsx 文件
2. 读取 '任务编号','手机号','计费','状态','状态码' 列
3. 更新 ES 中的数据

字段映射：
- '任务编号' -> gatewayId
- '手机号' -> toClient
- '计费' -> chargeNum
- '状态' -> resStatus (失败=4, 成功=3)
- '状态' -> resStatusCode (失败=500, 成功=SUCCESS)
- '状态码' -> resStatusMsg
"""

import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from elasticsearch import Elasticsearch

# 配置
EXCEL_FILE = r"D:\Github\py-proj\联麓短信补回调数据\file\inport.xlsx"
# ES_HOST = "http://192.168.12.124:88/@q1cloud:base.es.biz-10.10.0.8:9200/"  # ES Q1地址
ES_HOST = "http://192.168.12.124:88/@qcloud:base.es.biz-172.21.65.197:9200/"  # ES Q云地址
ES_INDEX = "esmsgsms2605"  # ES 索引名
BRAND_ID = 7148
DRY_RUN = False  # True=只输出日志不实际更新, False=实际更新
BATCH_SIZE = 200 # 每个批次执行条数
BATCH_WAIT_SEC = 5 # 每个批次执行间隔时间 单位s

# 状态映射
STATUS_TO_RES_STATUS = {
    "失败": 4,
    "成功": 3,
}

STATUS_TO_RES_STATUS_CODE = {
    "失败": "500",
    "成功": "SUCCESS",
}


def connect_es() -> Elasticsearch:
    """连接 ES"""
    return Elasticsearch([ES_HOST], timeout=30, max_retries=3, retry_on_timeout=True)


def read_excel(file_path: str) -> pd.DataFrame:
    """读取 Excel 文件"""
    df = pd.read_excel(file_path)

    # 检查必要的列是否存在
    required_columns = ["任务编号", "手机号", "计费", "状态", "状态码"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Excel 文件缺少必要的列: {missing_columns}")

    return df


def clean_gateway_id(gateway_id: str) -> str:
    """清理任务编号，去掉开头的 '：' 字符"""
    if pd.isna(gateway_id):
        return ""
    gateway_id = str(gateway_id).strip()
    if gateway_id.startswith("："):
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
    """构建 ES 更新文档，如果状态为'未知'则返回 None"""
    status = row["状态"]

    # 如果状态为'未知'，跳过此条数据
    if status == "未知":
        return None

    res_status = STATUS_TO_RES_STATUS.get(status)
    res_status_code = STATUS_TO_RES_STATUS_CODE.get(status)

    doc = {
        "chargeNum": int(row["计费"]) if not pd.isna(row["计费"]) else 0,
        "resStatus": res_status,
        "resStatusCode": res_status_code,
        "resStatusMsg": str(row["状态码"]) if not pd.isna(row["状态码"]) else "",
    }
    return doc


def search_es_docs_batch(es: Elasticsearch, items: list) -> dict:
    """
    批量查询 ES 文档（使用 terms 查询 gatewayId）

    Args:
        es: ES 客户端
        items: 查询条件列表，每个元素为 (gateway_id, to_client)

    Returns:
        dict: key=(gateway_id, to_client), value=es_doc 或 None
    """
    if not items:
        return {}

    # 提取所有不同的 gateway_id
    gateway_ids = list(set(item[0] for item in items))

    # 使用 terms 查询所有 gateway_id
    query = {
        "query": {
            "bool": {
                "must": [
                    {"terms": {"gatewayId": gateway_ids}},
                    {"term": {"resStatus": 1}},
                    {"term": {"brandId": BRAND_ID}},
                ]
            }
        },
        "size": len(gateway_ids) * 10,  # 适当放大
    }
    result = es.search(index=ES_INDEX, body=query)
    hits = result.get("hits", {}).get("hits", [])

    # 构建结果字典
    results = {}
    for item in items:
        results[item] = None

    for hit in hits:
        source = hit["_source"]
        key = (source.get("gatewayId"), source.get("toClient"))
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
    print(f"开始处理文件: {EXCEL_FILE}")
    if DRY_RUN:
        print("=" * 50)
        print("[DRY-RUN 模式] 仅输出日志，不实际更新 ES 数据")
        print("=" * 50)

    # 检查文件是否存在
    if not os.path.exists(EXCEL_FILE):
        print(f"文件不存在: {EXCEL_FILE}")
        return

    # 读取 Excel
    df = read_excel(EXCEL_FILE)
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
    search_items = []  # [(gateway_id, to_client), ...]
    rows_data = []  # [(index, gateway_id, to_client, doc), ...]

    for index, row in df.iterrows():
        doc = build_update_doc(row)

        # 跳过状态为'未知'的数据
        if doc is None:
            skipped += 1
            print(f"[{index + 1}/{total}] 跳过: 状态为'未知'")
            continue

        # 从 Excel 行数据获取查询条件
        gateway_id = clean_gateway_id(row["任务编号"])
        to_client = str(row["手机号"]).strip() if not pd.isna(row["手机号"]) else ""

        search_items.append((gateway_id, to_client))
        rows_data.append((index, gateway_id, to_client, doc))

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
        for index, gateway_id, to_client, doc in batch_rows:
            key = (gateway_id, to_client)
            es_doc = batch_results.get(key)

            if es_doc is None:
                not_found += 1
                print(f"[{index + 1}/{total}] 未找到: gatewayId={gateway_id}, toClient={to_client}")
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
