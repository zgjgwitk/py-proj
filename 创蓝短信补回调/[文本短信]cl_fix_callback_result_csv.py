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
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from elasticsearch import Elasticsearch

# 配置
# 输入文件共用同一个目录；文件名需包含 yy-MM 或 yyyy-MM，用于自动确定 ES 月索引
INPUT_DIR = r"D:\Github\py-proj\创蓝短信补回调\file"
INPUT_FILES = [
    "26-05.csv",
    "26-06.csv",
    "26-07.csv",
]
# ES_HOST = "http://192.168.12.124:88/@q1cloud:base.es.biz-10.10.0.8:9200/"  # ES Q1地址
ES_HOST = "http://192.168.12.124:88/@qcloud:base.es.biz-172.21.65.197:9200/"  # ES Q云地址
BRAND_ID = 99999
DRY_RUN = False  # True=只输出日志不实际更新, False=实际更新
BATCH_SIZE = 50  # 每个批次执行条数（减小以避免连接超时）
BATCH_WAIT_SEC = 3  # 每个批次执行间隔时间 单位s


REQUIRED_COLUMNS = ["client_msg_id", "状态报告"]
WRITEBACK_COLUMN = "回写结果"
PROGRESS_ROW_COLUMN = "行索引"


def extract_es_index_from_filename(file_path: str) -> str:
    """从文件名中的 yyyy-MM 或 yy-MM 提取 ES 索引名。"""
    file_name = os.path.basename(file_path)
    match = re.search(r"(?<!\d)(\d{2}|\d{4})-(\d{2})(?!\d)", file_name)
    if not match:
        raise ValueError(
            f"文件名 {file_name} 不包含 yyyy-MM 或 yy-MM 格式的年月, 无法提取索引名"
        )
    year, month = match.group(1), match.group(2)
    return f"esmsgsms{year[-2:]}{month}"


def get_previous_es_index(es_index: str) -> str:
    """根据当前 ES 索引名计算上个月的索引名。"""
    match = re.fullmatch(r"esmsgsms(\d{2})(\d{2})", es_index)
    if not match:
        raise ValueError(f"ES 索引名格式不正确: {es_index}")

    year, month = int(match.group(1)), int(match.group(2))
    if month == 1:
        year = (year - 1) % 100
        month = 12
    else:
        month -= 1
    return f"esmsgsms{year:02d}{month:02d}"


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

    # 老文件可能没有处理状态列，补充空列后按未处理数据执行
    if WRITEBACK_COLUMN not in df.columns:
        df[WRITEBACK_COLUMN] = ""

    return df


def save_input_file(df: pd.DataFrame, file_path: str) -> None:
    """将回写结果保存回原输入文件。"""
    suffix = Path(file_path).suffix.lower()
    if suffix == ".csv":
        df.to_csv(file_path, index=False, encoding="utf-8-sig")
    elif suffix in (".xlsx", ".xls"):
        df.to_excel(file_path, index=False)


def get_progress_file_path(input_file: str) -> str:
    """返回当前输入文件对应的批次进度文件路径。"""
    return f"{input_file}.writeback_progress.csv"


def load_progress(df: pd.DataFrame, progress_file: str) -> int:
    """加载历史批次进度，同一行有多条记录时以最后一条为准。"""
    if not os.path.exists(progress_file):
        return 0

    progress_df = pd.read_csv(progress_file, dtype=str, encoding="utf-8")
    if not {PROGRESS_ROW_COLUMN, WRITEBACK_COLUMN}.issubset(progress_df.columns):
        raise ValueError(f"进度文件格式不正确: {progress_file}")

    restored = {}
    for _, progress_row in progress_df.iterrows():
        try:
            row_index = int(progress_row[PROGRESS_ROW_COLUMN])
        except (TypeError, ValueError):
            continue
        result = str(progress_row[WRITEBACK_COLUMN]).strip()
        if row_index in df.index and result in ("1", "2", "3"):
            restored[row_index] = result

    for row_index, result in restored.items():
        df.at[row_index, WRITEBACK_COLUMN] = result
    return len(restored)


def append_progress(progress_file: str, updates: dict[int, str]) -> None:
    """将本批次产生的回写结果追加到进度文件，避免重写整个输入文件。"""
    if not updates:
        return

    progress_df = pd.DataFrame(
        [
            {PROGRESS_ROW_COLUMN: row_index, WRITEBACK_COLUMN: result}
            for row_index, result in updates.items()
        ]
    )
    progress_df.to_csv(
        progress_file,
        mode="a",
        header=not os.path.exists(progress_file),
        index=False,
        encoding="utf-8",
    )


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


def search_es_docs_batch(es: Elasticsearch, items: list, es_index: str) -> dict:
    """
    批量查询 ES 文档（使用 terms 查询 gatewayId）

    Args:
        es: ES 客户端
        items: 查询条件列表，每个元素为 gateway_id
        es_index: 要查询的 ES 索引名

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
    result = es.search(index=es_index, body=query)
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
        update_list: 更新列表，每个元素为 (es_index, doc_id, doc, row_index)

    Returns:
        tuple: (成功数, 失败数, 成功更新的 DataFrame 行索引列表)
    """
    if not update_list:
        return 0, 0, []

    success = 0
    failed = 0
    successful_row_indexes = []

    # 构建 bulk 请求体
    bulk_body = []
    for es_index, doc_id, doc, _ in update_list:
        bulk_body.append({"update": {"_index": es_index, "_id": doc_id}})
        bulk_body.append({"doc": doc})
        # print(f"[update] doc_id={doc_id}, resStatus={doc['resStatus']}, resStatusCode={doc['resStatusCode']}, resStatusMsg={doc['resStatusMsg']}")

    # 执行批量更新
    try:
        result = es.bulk(body=bulk_body)
        for update_item, item in zip(update_list, result.get("items", [])):
            if item.get("update", {}).get("result") in ["updated", "noop"]:
                success += 1
                successful_row_indexes.append(update_item[3])
            else:
                failed += 1
    except Exception as e:
        print(f"批量更新失败: {e}")
        failed = len(update_list)

    return success, failed, successful_row_indexes


def process_input_file(es: Elasticsearch, input_file: str) -> dict:
    """处理单个输入文件，并返回本文件的处理统计。"""
    print(f"\n开始处理文件: {input_file}")
    # 检查文件是否存在
    if not os.path.exists(input_file):
        print(f"文件不存在: {input_file}")
        return {"total": 0, "success": 0, "not_found": 0, "failed": 1, "skipped": 0}

    # 每个文件分别计算当前月和上月索引，避免多文件使用同一个索引
    es_index = extract_es_index_from_filename(input_file)
    previous_es_index = get_previous_es_index(es_index)
    print(f"当前索引: {es_index}, 上月索引: {previous_es_index}")

    # 读取 CSV/Excel
    df = read_input_file(input_file)
    print(f"共读取 {len(df)} 条记录")

    # 如果上次执行中断，先从追加式进度文件恢复已经处理过的行
    progress_file = get_progress_file_path(input_file)
    restored_count = load_progress(df, progress_file)
    if restored_count:
        print(f"已从进度文件恢复 {restored_count} 条处理结果: {progress_file}")

    # 统计
    total = len(df)
    success = 0
    not_found = 0
    failed = 0
    skipped = 0

    # 构建查询条件列表和更新文档列表
    search_items = []  # [(gateway_id), ...]
    rows_data = []  # [(index, gateway_id, doc), ...]
    pending_progress = {}  # 尚未写入进度文件的 {row_index: 回写结果}

    for index, row in df.iterrows():
        writeback_result = (
            str(row[WRITEBACK_COLUMN]).strip()
            if not pd.isna(row[WRITEBACK_COLUMN])
            else ""
        )
        # 1=已成功回写，2=已确认未找到，3=业务条件不满足而跳过
        if writeback_result in ("1", "2", "3"):
            skipped += 1
            print(
                f"[{index + 1}/{total}] 跳过: {WRITEBACK_COLUMN}={writeback_result}"
            )
            continue

        doc = build_update_doc(row)

        # 状态报告为空时没有可回写内容
        if doc is None:
            skipped += 1
            df.at[index, WRITEBACK_COLUMN] = "3"
            pending_progress[index] = "3"
            print(f"[{index + 1}/{total}] 跳过: 状态报告为空")
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
        batch_results = search_es_docs_batch(es, batch, es_index)
        hit_count = sum(1 for v in batch_results.values() if v is not None)
        print(
            f"批次 {(i // batch_size) + 1} 查询 {es_index} 完成: "
            f"共查询 {len(batch)} 条, 命中 {hit_count} 条"
        )

        # 构建更新列表
        update_list = []  # [(es_index, doc_id, doc, row_index), ...]
        not_found_rows = []  # [(index, gateway_id, doc), ...]
        for index, gateway_id, doc in batch_rows:
            es_doc = batch_results.get(gateway_id)

            if es_doc is None:
                not_found_rows.append((index, gateway_id, doc))
                continue

            doc_id = es_doc["_id"]

            if DRY_RUN:
                print(
                    f"[{index + 1}/{total}] [DRY-RUN] 在 {es_index} 查找到: "
                    f"doc_id={doc_id}"
                )
                success += 1
            else:
                update_list.append((es_index, doc_id, doc, index))

        # 当前月未命中的 gatewayId，统一到上个月索引再查询一次
        if not_found_rows:
            previous_items = [gateway_id for _, gateway_id, _ in not_found_rows]
            previous_results = search_es_docs_batch(
                es, previous_items, previous_es_index
            )
            previous_hit_count = sum(
                1 for value in previous_results.values() if value is not None
            )
            print(
                f"批次 {(i // batch_size) + 1} 补查 {previous_es_index} 完成: "
                f"共查询 {len(previous_items)} 条, 命中 {previous_hit_count} 条"
            )

            for index, gateway_id, doc in not_found_rows:
                es_doc = previous_results.get(gateway_id)
                if es_doc is None:
                    not_found += 1
                    df.at[index, WRITEBACK_COLUMN] = "2"
                    pending_progress[index] = "2"
                    print(
                        f"[{index + 1}/{total}] 当前月及上月均未找到: "
                        f"gatewayId={gateway_id}"
                    )
                    continue

                doc_id = es_doc["_id"]
                if DRY_RUN:
                    print(
                        f"[{index + 1}/{total}] [DRY-RUN] 在 {previous_es_index} "
                        f"查找到: doc_id={doc_id}"
                    )
                    success += 1
                else:
                    update_list.append((previous_es_index, doc_id, doc, index))

        # 更新本批次
        if not DRY_RUN and update_list:
            batch_success, batch_failed, successful_row_indexes = (
                update_es_docs_batch(es, update_list)
            )
            for row_index in successful_row_indexes:
                df.at[row_index, WRITEBACK_COLUMN] = "1"
                pending_progress[row_index] = "1"
            success += batch_success
            failed += batch_failed
            print(f"批次 {(i // batch_size) + 1} 更新完成: 成功={batch_success}, 失败={batch_failed}")

        # 每批只追加本批状态，避免反复重写完整 CSV/Excel 文件
        if not DRY_RUN and pending_progress:
            append_progress(progress_file, pending_progress)
            print(
                f"批次 {(i // batch_size) + 1} 进度已保存: "
                f"{len(pending_progress)} 条"
            )
            pending_progress.clear()

        time.sleep(BATCH_WAIT_SEC)  # 间隔 s

        processed_count += len(batch)

    # 没有进入查询批次时，也要保存因业务条件而跳过的行
    if not DRY_RUN and pending_progress:
        append_progress(progress_file, pending_progress)
        pending_progress.clear()

    # 全部完成后只重写一次原文件，再清理已经合并的进度文件
    if not DRY_RUN:
        save_input_file(df, input_file)
        print(f"已保存 {WRITEBACK_COLUMN}: {input_file}")
        if os.path.exists(progress_file):
            os.remove(progress_file)
            print(f"已清理进度文件: {progress_file}")

    # 输出统计
    print("\n" + "=" * 50)
    print(f"处理完成!")
    print(f"总计: {total}")
    print(f"成功: {success}")
    print(f"未找到: {not_found}")
    print(f"失败: {failed}")
    print(f"跳过: {skipped}")
    print("=" * 50)

    # 返回结构化结果，供所有文件处理完成后的总结表格使用
    return {
        "total": total,
        "success": success,
        "not_found": not_found,
        "failed": failed,
        "skipped": skipped,
    }


def main():
    if not INPUT_FILES:
        print("未配置任何输入文件")
        return

    if DRY_RUN:
        print("=" * 50)
        print("[DRY-RUN 模式] 仅输出日志，不实际更新 ES 数据")
        print("=" * 50)

    es = connect_es()
    print(f"已连接到 ES: {ES_HOST}")

    # 逐个处理文件；process_input_file 内部仍会立即输出该文件的处理日志
    summary_rows = []
    for input_file_name in INPUT_FILES:
        input_file = os.path.join(INPUT_DIR, input_file_name)
        result = process_input_file(es, input_file)
        summary_rows.append({"文件": input_file_name, **result})

    # 将内部统计字段转换为便于阅读的中文表头
    summary_df = pd.DataFrame(summary_rows).rename(
        columns={
            "total": "总计",
            "success": "成功",
            "not_found": "未找到",
            "failed": "失败",
            "skipped": "跳过",
        }
    )
    # 在各文件统计之后追加一行总计
    total_row = {
        "文件": "合计",
        "总计": summary_df["总计"].sum(),
        "成功": summary_df["成功"].sum(),
        "未找到": summary_df["未找到"].sum(),
        "失败": summary_df["失败"].sum(),
        "跳过": summary_df["跳过"].sum(),
    }
    summary_df = pd.concat(
        [summary_df, pd.DataFrame([total_row])], ignore_index=True
    )

    # 所有文件处理结束后，再统一输出总结表格
    print("\n" + "#" * 50)
    print("全部文件处理总结")
    print(summary_df.to_string(index=False))
    print("#" * 50)


if __name__ == "__main__":
    main()
