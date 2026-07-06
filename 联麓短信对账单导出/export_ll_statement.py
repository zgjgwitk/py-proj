#   "es_url": "http://192.168.12.124:88/@qcloud:base.es.biz-172.21.65.197:9200/",
#   "es_url": "http://192.168.12.124:88/@q1cloud:base.es.biz-10.10.0.8:9200/",
from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests


SERVICE_TYPE_MAP = {
    "1": "通知短信",
    "2": "营销短信",
    "3": "国际短信",
    "4": "国际短信",
    "5": "视频短信",
    "notice": "通知短信",
    "marketing": "营销短信",
    "international": "国际短信",
    "video": "视频短信",
    "通知短信": "通知短信",
    "营销短信": "营销短信",
    "国际通知短信": "国际短信",
    "国际短信": "国际短信",
    "视频短信": "视频短信",
}

SUCCESS_RES_STATUS = 3
FAILED_RES_STATUS = [2, 4, 5]
UNKNOWN_RES_STATUS = 1


@dataclass
class Config:
    es_url: str
    index: str
    output: str
    sms_chan: int = 40
    timeout: int = 60
    verify_ssl: bool = True
    page_size: int = 1000
    brand_ids: list[int] | None = None
    headers: dict[str, str] | None = None


def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出联麓短信 ES 对账单")
    parser.add_argument("--config", default="", help="配置文件路径，支持 JSON")
    parser.add_argument("--es-url", default="", help="ES 地址")
    parser.add_argument("--index", default="", help="ES 索引名")
    parser.add_argument("--output", default="", help="输出 Excel 文件路径")
    parser.add_argument("--sms-chan", type=int, default=-1, help="短信通道，默认 40")
    parser.add_argument("--timeout", type=int, default=-1, help="请求超时秒数")
    parser.add_argument("--verify-ssl", default="", help="是否校验证书，true/false")
    parser.add_argument("--page-size", type=int, default=-1, help="composite 聚合分页大小")
    parser.add_argument("--brand-ids", default="", help="品牌编号列表，逗号分隔")
    return parser.parse_args()


def read_json_file(file_path: Path) -> dict[str, Any]:
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def parse_bool(value: str, default: bool) -> bool:
    if value == "":
        return default
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y"}:
        return True
    if lowered in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"无法识别布尔值: {value}")


def parse_brand_ids(value: str, default: list[int] | None) -> list[int]:
    if not value.strip():
        return list(default or [])
    brand_ids: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if item:
            brand_ids.append(int(item))
    return brand_ids


def build_config(args: argparse.Namespace) -> Config:
    script_dir = Path(__file__).resolve().parent
    config_path = Path(args.config) if args.config else script_dir / "config.json"
    raw = read_json_file(config_path)

    es_url = args.es_url or raw.get("es_url", "")
    index = args.index or raw.get("index", "")
    output = args.output or raw.get("output", f"联麓对账单_{index}.xlsx")

    if not es_url or not index:
        raise ValueError("缺少必要参数: es_url / index")

    config = Config(
        es_url=es_url.rstrip("/"),
        index=index,
        output=output,
        sms_chan=args.sms_chan if args.sms_chan >= 0 else int(raw.get("sms_chan", 40)),
        timeout=args.timeout if args.timeout > 0 else int(raw.get("timeout", 60)),
        verify_ssl=parse_bool(args.verify_ssl, bool(raw.get("verify_ssl", True))),
        page_size=args.page_size if args.page_size > 0 else int(raw.get("page_size", 1000)),
        brand_ids=parse_brand_ids(args.brand_ids, raw.get("brand_ids", [])),
        headers=raw.get("headers", {}) or {},
    )
    validate_config(config)
    return config


def validate_config(config: Config) -> None:
    if config.page_size <= 0:
        raise ValueError("page_size 必须大于 0")


def build_session(config: Config) -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    if config.headers:
        session.headers.update(config.headers)
    return session


def service_type_label(value: Any) -> str:
    if value is None or value == "":
        return "未知类型"
    normalized = str(value).strip()
    return SERVICE_TYPE_MAP.get(normalized, normalized)


def account_label(value: Any) -> str:
    if value is None:
        return "默认账号"
    text = str(value).strip()
    return text if text else "默认账号"


def to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(math.floor(value + 0.5))
    return int(value)


def build_base_filters(config: Config) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [
        {"term": {"smsChan": config.sms_chan}},
    ]
    if config.brand_ids:
        filters.append({"terms": {"brandId": config.brand_ids}})
    return filters


def build_metric_aggs() -> dict[str, Any]:
    return {
        "min_req_time": {"min": {"field": "reqTime", "format": "yyyy-MM-dd HH:mm:ss"}},
        "max_req_time": {"max": {"field": "reqTime", "format": "yyyy-MM-dd HH:mm:ss"}},
        "total_charge_num": {"sum": {"field": "chargeNum"}},
        "success_charge_num": {
            "filter": {"term": {"resStatus": SUCCESS_RES_STATUS}},
            "aggs": {"charge": {"sum": {"field": "chargeNum"}}},
        },
        "failed_charge_num": {
            "filter": {"terms": {"resStatus": FAILED_RES_STATUS}},
            "aggs": {"charge": {"sum": {"field": "chargeNum"}}},
        },
        "unknown_charge_num": {
            "filter": {"term": {"resStatus": UNKNOWN_RES_STATUS}},
            "aggs": {"charge": {"sum": {"field": "chargeNum"}}},
        },
    }


def build_composite_query(
    config: Config,
    filters: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    after_key: dict[str, Any] | None,
) -> dict[str, Any]:
    composite: dict[str, Any] = {
        "size": config.page_size,
        "sources": sources,
    }
    if after_key:
        composite["after"] = after_key

    return {
        "size": 0,
        "track_total_hits": True,
        "query": {"bool": {"filter": filters}},
        "aggs": {
            "group_by": {
                "composite": composite,
                "aggs": build_metric_aggs(),
            }
        },
    }


def post_es_query(
    session: requests.Session,
    config: Config,
    body: dict[str, Any],
) -> dict[str, Any]:
    url = f"{config.es_url}/{config.index}/_search"
    response = session.post(url, json=body, timeout=config.timeout, verify=config.verify_ssl)
    response.raise_for_status()
    return response.json()


def fetch_all_buckets(
    session: requests.Session,
    config: Config,
    filters: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    query_name: str,
) -> list[dict[str, Any]]:
    after_key: dict[str, Any] | None = None
    all_buckets: list[dict[str, Any]] = []

    while True:
        body = build_composite_query(config, filters, sources, after_key)
        data = post_es_query(session, config, body)
        aggregations = data.get("aggregations", {})
        group_by = aggregations.get("group_by", {})
        buckets = group_by.get("buckets", [])
        all_buckets.extend(buckets)
        log(f"{query_name} 拉取 {len(buckets)} 个 bucket，累计 {len(all_buckets)}")

        after_key = group_by.get("after_key")
        if not buckets or not after_key:
            break

    return all_buckets


def build_summary_rows(buckets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket in buckets:
        key = bucket.get("key", {})
        rows.append(
            {
                "品牌编号": to_int(key.get("brandId")),
                "EZR账号": account_label(key.get("ezrAcc")),
                "产品类型": service_type_label(key.get("serviceType")),
                "开始时间": bucket.get("min_req_time", {}).get("value_as_string", ""),
                "结束时间": bucket.get("max_req_time", {}).get("value_as_string", ""),
                "提交量": to_int(bucket.get("doc_count", 0)),
                "总计费量": to_int(bucket.get("total_charge_num", {}).get("value")),
                "成功计费量": to_int(bucket.get("success_charge_num", {}).get("charge", {}).get("value")),
                "失败计费量": to_int(bucket.get("failed_charge_num", {}).get("charge", {}).get("value")),
                "未知计费量": to_int(bucket.get("unknown_charge_num", {}).get("charge", {}).get("value")),
            }
        )

    rows.sort(key=lambda item: (item["品牌编号"], item["EZR账号"], item["产品类型"]))
    return rows


def build_detail_rows(buckets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket in buckets:
        key = bucket.get("key", {})
        rows.append(
            {
                "_brand_id": to_int(key.get("brandId")),
                "_ezr_acc": account_label(key.get("ezrAcc")),
                "品牌编号": to_int(key.get("brandId")),
                "EZR账号": account_label(key.get("ezrAcc")),
                "发送日期": to_int(key.get("reqTimeDay")),
                "产品类型": service_type_label(key.get("serviceType")),
                "提交量": to_int(bucket.get("doc_count", 0)),
                "总计费量": to_int(bucket.get("total_charge_num", {}).get("value")),
                "成功计费量": to_int(bucket.get("success_charge_num", {}).get("charge", {}).get("value")),
                "失败计费量": to_int(bucket.get("failed_charge_num", {}).get("charge", {}).get("value")),
                "未知计费量": to_int(bucket.get("unknown_charge_num", {}).get("charge", {}).get("value")),
            }
        )

    rows.sort(key=lambda item: (item["_brand_id"], item["_ezr_acc"], item["发送日期"], item["产品类型"]))
    return rows


def sanitize_sheet_name(name: str) -> str:
    cleaned = re.sub(r"[\\/*?:\[\]]", "_", name).strip()
    return cleaned or "Sheet"


def unique_sheet_name(raw_name: str, used: set[str]) -> str:
    base = sanitize_sheet_name(raw_name)
    candidate = base[:31]
    if candidate not in used:
        used.add(candidate)
        return candidate

    index = 2
    while True:
        suffix = f"_{index}"
        trimmed = base[: 31 - len(suffix)]
        candidate = f"{trimmed}{suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        index += 1


def export_excel(
    output_path: Path,
    summary_rows: list[dict[str, Any]],
    detail_rows: list[dict[str, Any]],
) -> None:
    if not summary_rows and not detail_rows:
        raise ValueError("没有可导出的数据")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    summary_df = pd.DataFrame(summary_rows)
    grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in detail_rows:
        grouped[(row["_brand_id"], row["_ezr_acc"])].append(row)

    used_sheet_names = {"各品牌汇总"}
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="各品牌汇总", index=False)

        for (brand_id, ezr_acc), rows in sorted(grouped.items(), key=lambda item: item[0]):
            sheet_name = unique_sheet_name(f"{brand_id}_{ezr_acc}", used_sheet_names)
            export_rows = [
                {
                    "品牌编号": row["品牌编号"],
                    "EZR账号": row["EZR账号"],
                    "发送日期": row["发送日期"],
                    "产品类型": row["产品类型"],
                    "提交量": row["提交量"],
                    "总计费量": row["总计费量"],
                    "成功计费量": row["成功计费量"],
                    "失败计费量": row["失败计费量"],
                    "未知计费量": row["未知计费量"],
                }
                for row in rows
            ]
            pd.DataFrame(export_rows).to_excel(writer, sheet_name=sheet_name, index=False)


def main() -> int:
    args = parse_args()
    config = build_config(args)
    output_path = Path(config.output)
    if not output_path.is_absolute():
        output_path = Path(__file__).resolve().parent / output_path

    log(f"开始导出，索引={config.index}")
    session = build_session(config)
    filters = build_base_filters(config)

    summary_sources = [
        {"brandId": {"terms": {"field": "brandId"}}},
        {"ezrAcc": {"terms": {"field": "ezrAcc", "missing_bucket": True}}},
        {"serviceType": {"terms": {"field": "serviceType", "missing_bucket": True}}},
    ]
    detail_sources = [
        {"brandId": {"terms": {"field": "brandId"}}},
        {"ezrAcc": {"terms": {"field": "ezrAcc", "missing_bucket": True}}},
        {"reqTimeDay": {"terms": {"field": "reqTimeDay"}}},
        {"serviceType": {"terms": {"field": "serviceType", "missing_bucket": True}}},
    ]

    summary_buckets = fetch_all_buckets(session, config, filters, summary_sources, "汇总查询")
    detail_buckets = fetch_all_buckets(session, config, filters, detail_sources, "明细查询")

    summary_rows = build_summary_rows(summary_buckets)
    detail_rows = build_detail_rows(detail_buckets)

    export_excel(output_path, summary_rows, detail_rows)
    log(f"导出完成: {output_path}")
    log(f"汇总行数: {len(summary_rows)}，明细行数: {len(detail_rows)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("用户中断执行")
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001
        log(f"执行失败: {exc}")
        raise SystemExit(1)
