"""统计每月验证码短信数量并导出 Excel。

用法: ``python 统计验证码类型.py 202604~202606``
也可以省略参数，届时通过命令行提示输入月份范围。
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

ES_URL = "http://192.168.12.124:88/@qcloud:base.es.biz-172.21.65.197:9200/"
# 默认统计月份范围（可直接修改此公共变量）
MONTH_RANGE = "202604~202606"
VERIFY_TYPES = ("WfxVerify", "VipReg", "SysUserPwdGet")
logger = logging.getLogger(__name__)


def parse_months(value: str) -> list[str]:
    """解析 YYYYMM 或 YYYYMM~YYYYMM，返回连续的 YYYY-MM 月份。"""
    m = re.fullmatch(r"(\d{6})(?:\s*[~\-]\s*(\d{6}))?", value.strip())
    if not m:
        raise ValueError("月份格式应为 YYYYMM 或 YYYYMM~YYYYMM，例如 202604~202606")
    start, end = m.group(1), m.group(2) or m.group(1)
    sy, sm, ey, em = int(start[:4]), int(start[4:]), int(end[:4]), int(end[4:])
    if not 1 <= sm <= 12 or not 1 <= em <= 12:
        raise ValueError("月份必须在 01 到 12 之间")
    if (sy, sm) > (ey, em):
        raise ValueError("起始月份不能晚于结束月份")
    result = []
    y, month = sy, sm
    while (y, month) <= (ey, em):
        result.append(f"{y:04d}-{month:02d}")
        month += 1
        if month == 13:
            y, month = y + 1, 1
    return result


def month_index(month: str) -> str:
    return "esmsgsms" + month.replace("-", "")[2:]


def query_month(es, index: str) -> dict[tuple[str, str], int]:
    body = {
        "size": 0,
        "query": {"bool": {"filter": [
            {"term": {"serviceType": 1}},
            {"terms": {"type": list(VERIFY_TYPES)}},
        ]}},
        "aggs": {"by_type": {"terms": {"field": "type", "size": 20},
            "aggs": {"by_brand": {"filters": {"filters": {
                "驿氪": {"term": {"brandId": 2}},
                "非驿氪": {"bool": {"must_not": {"term": {"brandId": 2}}}},
            }}}}}},
    }
    logger.info("ES 请求地址: %s/%s/_search", ES_URL.rstrip("/"), index)
    logger.info("ES 请求索引: %s", index)
    logger.info("ES 请求语句:\n%s", json.dumps(body, ensure_ascii=False, indent=2))
    response = es.search(index=index, body=body, ignore_unavailable=True)
    result = {}
    for bucket in response.get("aggregations", {}).get("by_type", {}).get("buckets", []):
        for brand, data in bucket.get("by_brand", {}).get("buckets", {}).items():
            result[(str(bucket["key"]), brand)] = data.get("doc_count", 0)
    return result


def export(months: list[str], output: str | None = None) -> Path:
    try:
        from elasticsearch import Elasticsearch
        es = Elasticsearch(ES_URL, request_timeout=60)
    except ImportError as exc:
        raise RuntimeError("请先安装依赖: pip install elasticsearch pandas openpyxl") from exc
    counts = {}
    for month in months:
        counts.update({(k[0], k[1], month): v for k, v in query_month(es, month_index(month)).items()})
    import pandas as pd
    rows = [{"type-场景": t, "驿氪/非驿氪": b, **{m: counts.get((t, b, m), 0) for m in months}}
            for t in VERIFY_TYPES for b in ("驿氪", "非驿氪")]
    path = Path(output or Path(__file__).with_name(f"验证码短信统计_{months[0]}_{months[-1]}.xlsx")).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="统计验证码短信数量")
    parser.add_argument("months", nargs="?", help="月份范围，如 202604~202606（覆盖 MONTH_RANGE）")
    parser.add_argument("-o", "--output", help="输出 Excel 文件路径")
    args = parser.parse_args()
    value = args.months or MONTH_RANGE
    months = parse_months(value)
    print(f"正在查询 {months[0]} 至 {months[-1]} ...")
    print(f"已导出: {export(months, args.output)}")


if __name__ == "__main__":
    main()
