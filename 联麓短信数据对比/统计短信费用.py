"""
需求描述: 统计 ES 索引中短信发送的费用总计, 按 reqTimeDay 做维度汇总 + 拆分明细 sheet.
详细:
- ES 地址> 参考 对比手机号在本地缺少的列表.py 中的 ES_URL
- ES 索引> esmsgsgs2608
- 筛选条件> brandId=7163, serviceType=2, resStatus=3
- 输出:
    1. 汇总 sheet: 按 reqTimeDay 统计 chargeNum 总和 + 命中 doc_count
    2. 明细 sheet: 按 reqTimeDay 拆分, 每个 sheet 列出当日命中的 (reqTimeDay, gatewayId, toClient, chargeNum)
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Iterable

try:
    import pandas as pd
    import requests
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        f"缺少依赖: {exc.name}. 请先执行: pip install pandas requests openpyxl\n"
    )
    sys.exit(1)


# ============== 配置常量 ==============
ES_URL = "http://192.168.12.124:88/@qcloud:base.es.biz-172.21.65.197:9200/"
ES_INDEX = "esmsgsms2608"
BRAND_ID = 7163
SERVICE_TYPE = 2
RES_STATUS = 3

# 导出的 xlsx 路径
EXPORT_PATH = Path(r"D:\Github\py-proj\联麓短信数据对比\sourceFile\短信费用统计.xlsx")
EXPORT_SHEET_SUMMARY = "费用按日汇总"
EXPORT_DETAIL_SHEET_PREFIX = "明细_"
EXPORT_SHEET_NAME_MAX_LEN = 31  # Excel sheet 名长度上限

# 明细查询返回的字段
DETAIL_FIELDS = ["reqTimeDay", "gatewayId", "toClient", "chargeNum"]

BATCH_SIZE = 1000
REQUEST_TIMEOUT = 30
RETRY_TIMES = 3
RETRY_BACKOFF = 2.0
# ES 性能不高, 每次请求后 sleep 50ms, 避免压垮 ES
REQUEST_SLEEP_SECONDS = 0.05


# ============== 日志 ==============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("sms-fee-stat")


# ============== 业务函数 ==============
def fetch_days_with_data() -> list[str]:
    """先按 reqTimeDay 做聚合, 返回有数据的日期列表 (升序).

    用途: 明细查询按天发起, 先用聚合把所有日期拉出来, 避免逐天探测.
    """
    url = f"{ES_URL.rstrip('/')}/{ES_INDEX}/_search"
    headers = {"Content-Type": "application/json"}
    page_size = 1000

    days: set[str] = set()
    after: dict | None = None
    page = 0

    while True:
        payload: dict = {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"brandId": str(BRAND_ID)}},
                        {"term": {"serviceType": SERVICE_TYPE}},
                        {"term": {"resStatus": RES_STATUS}},
                    ]
                }
            },
            "aggs": {
                "by_day": {
                    "composite": {
                        "size": page_size,
                        "sources": [
                            {"reqTimeDay": {"terms": {"field": "reqTimeDay"}}}
                        ],
                    }
                }
            },
        }
        if after is not None:
            payload["aggs"]["by_day"]["composite"]["after"] = after

        last_err: Exception | None = None
        for attempt in range(1, RETRY_TIMES + 1):
            try:
                resp = requests.post(
                    url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
                )
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"ES 返回非 200({resp.status_code}): {resp.text[:500]}"
                    )
                data = resp.json()
                buckets = (
                    data.get("aggregations", {}).get("by_day", {}).get("buckets", [])
                )
                after = data.get("aggregations", {}).get("by_day", {}).get("after_key")
                for bucket in buckets:
                    day = bucket.get("key", {}).get("reqTimeDay")
                    if day is not None:
                        days.add(str(day))
                time.sleep(REQUEST_SLEEP_SECONDS)
                last_err = None
                break
            except Exception as exc:
                last_err = exc
                if attempt < RETRY_TIMES:
                    sleep_sec = RETRY_BACKOFF ** attempt
                    logger.warning(
                        "日期聚合第 %d 页第 %d 次请求失败, %.1fs 后重试: %s",
                        page + 1, attempt, sleep_sec, exc,
                    )
                    time.sleep(sleep_sec)

        if last_err is not None:
            raise RuntimeError(
                f"日期聚合第 {page + 1} 页最终失败: {last_err}"
            )

        page += 1
        if not buckets or after is None:
            break

    logger.info("日期聚合完成, 共 %d 个 reqTimeDay, 总页数 %d", len(days), page)
    return sorted(days)


def fetch_details_by_day(days: Iterable[str]) -> dict[str, list[dict]]:
    """逐天按 reqTimeDay 拉明细, 返回 {reqTimeDay: [明细 dict, ...]}.

    每条明细字段: reqTimeDay, gatewayId, toClient, chargeNum.
    使用 search_after + _id 排序翻页, 避免 size 截断.
    """
    url = f"{ES_URL.rstrip('/')}/{ES_INDEX}/_search"
    headers = {"Content-Type": "application/json"}
    page_size = 1000

    details_by_day: dict[str, list[dict]] = {day: [] for day in days}

    for day in days:
        logger.info("开始查询明细 reqTimeDay=%s", day)
        last_sort: list | None = None
        page = 0

        while True:
            payload: dict = {
                "size": page_size,
                "_source": DETAIL_FIELDS,
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"brandId": str(BRAND_ID)}},
                            {"term": {"serviceType": SERVICE_TYPE}},
                            {"term": {"resStatus": RES_STATUS}},
                            {"term": {"reqTimeDay": day}},
                        ]
                    }
                },
                "sort": [{"_id": "asc"}],
            }
            if last_sort is not None:
                payload["search_after"] = last_sort

            last_err: Exception | None = None
            for attempt in range(1, RETRY_TIMES + 1):
                try:
                    resp = requests.post(
                        url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
                    )
                    if resp.status_code != 200:
                        raise RuntimeError(
                            f"ES 返回非 200({resp.status_code}): {resp.text[:500]}"
                        )
                    data = resp.json()
                    hits = data.get("hits", {}).get("hits", [])
                    if page == 0:
                        logger.info(
                            "明细 reqTimeDay=%s 第1页响应: total=%s, 本页 hits=%d",
                            day, data.get("hits", {}).get("total"), len(hits),
                        )
                    for hit in hits:
                        src = hit.get("_source", {}) or {}
                        details_by_day[day].append(
                            {
                                "reqTimeDay": src.get("reqTimeDay", day),
                                "gatewayId": src.get("gatewayId", ""),
                                "toClient": src.get("toClient", ""),
                                "chargeNum": src.get("chargeNum", 0),
                            }
                        )
                    time.sleep(REQUEST_SLEEP_SECONDS)
                    last_err = None
                    break
                except Exception as exc:
                    last_err = exc
                    if attempt < RETRY_TIMES:
                        sleep_sec = RETRY_BACKOFF ** attempt
                        logger.warning(
                            "明细 reqTimeDay=%s 第 %d 页第 %d 次请求失败, %.1fs 后重试: %s",
                            day, page + 1, attempt, sleep_sec, exc,
                        )
                        time.sleep(sleep_sec)

            if last_err is not None:
                raise RuntimeError(
                    f"明细 reqTimeDay={day} 第 {page + 1} 页最终失败: {last_err}"
                )

            page += 1
            if len(hits) < page_size:
                break
            last_sort = hits[-1].get("sort")

        logger.info("明细 reqTimeDay=%s 完成, 命中 %d 条", day, len(details_by_day[day]))

    return details_by_day


def summarize(details_by_day: dict[str, list[dict]]) -> dict[str, dict[str, float]]:
    """从明细汇总出 {reqTimeDay: {charge_sum, doc_count}}."""
    summary: dict[str, dict[str, float]] = {}
    for day, rows in details_by_day.items():
        charge_sum = 0.0
        for row in rows:
            try:
                charge_sum += float(row.get("chargeNum") or 0.0)
            except (TypeError, ValueError):
                continue
        summary[day] = {"charge_sum": charge_sum, "doc_count": len(rows)}
    return summary


def _build_sheet_name(day: str, used: set[str]) -> str:
    """构造合法且不重复的 sheet 名 (Excel 限制 31 字符)."""
    base = f"{EXPORT_DETAIL_SHEET_PREFIX}{day}"
    if len(base) > EXPORT_SHEET_NAME_MAX_LEN:
        base = base[:EXPORT_SHEET_NAME_MAX_LEN]
    name = base
    suffix = 1
    while name in used:
        suffix_str = f"_{suffix}"
        name = base[: EXPORT_SHEET_NAME_MAX_LEN - len(suffix_str)] + suffix_str
        suffix += 1
    used.add(name)
    return name


def export_excel(
    summary: dict[str, dict[str, float]],
    details_by_day: dict[str, list[dict]],
    target: Path,
) -> Path:
    """导出 xlsx: 汇总 sheet + 每个 reqTimeDay 一个明细 sheet."""
    # 汇总 sheet
    summary_rows = []
    total_charge = 0.0
    total_count = 0
    for day in sorted(summary):
        info = summary[day]
        summary_rows.append(
            {
                "reqTimeDay": day,
                "charge_sum": round(info["charge_sum"], 4),
                "doc_count": info["doc_count"],
            }
        )
        total_charge += info["charge_sum"]
        total_count += info["doc_count"]
    summary_rows.append(
        {
            "reqTimeDay": "合计",
            "charge_sum": round(total_charge, 4),
            "doc_count": total_count,
        }
    )
    df_summary = pd.DataFrame(summary_rows)

    tmp = target.with_name(target.stem + ".tmp.xlsx")
    used_sheet_names: set[str] = {EXPORT_SHEET_SUMMARY}
    try:
        with pd.ExcelWriter(tmp, engine="openpyxl") as writer:
            df_summary.to_excel(
                writer, sheet_name=EXPORT_SHEET_SUMMARY, index=False
            )
            for day in sorted(details_by_day):
                rows = details_by_day[day]
                if not rows:
                    continue
                sheet_name = _build_sheet_name(day, used_sheet_names)
                df_detail = pd.DataFrame(rows, columns=DETAIL_FIELDS)
                df_detail.to_excel(writer, sheet_name=sheet_name, index=False)
        if target.exists():
            target.unlink()
        tmp.rename(target)
    except PermissionError as exc:
        raise PermissionError(
            f"无法写入 {target}, 请确认该 Excel 文件未被打开后重试. 原始错误: {exc}"
        ) from exc
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass

    detail_count = sum(1 for d in details_by_day.values() if d)
    logger.info(
        "已导出: %s (汇总 1 个 sheet, 明细 %d 个 sheet, 合计 charge_sum=%s)",
        target, detail_count, total_charge,
    )
    return target


def main() -> int:
    start = time.time()
    try:
        days = fetch_days_with_data()
        if not days:
            logger.warning("未查询到任何 reqTimeDay 的数据")
            return 0

        details_by_day = fetch_details_by_day(days)
        summary = summarize(details_by_day)

        # 控制台输出汇总
        print("\n========== 短信费用按日汇总 ==========")
        print(f"{'reqTimeDay':<14}{'charge_sum':>16}{'doc_count':>16}")
        print("-" * 46)
        total_charge = 0.0
        total_count = 0
        for day in sorted(summary):
            info = summary[day]
            total_charge += info["charge_sum"]
            total_count += info["doc_count"]
            print(
                f"{day:<14}{info['charge_sum']:>16.4f}{info['doc_count']:>16}"
            )
        print("-" * 46)
        print(f"{'合计':<14}{total_charge:>16.4f}{total_count:>16}")
        print("======================================\n")

        export_excel(summary, details_by_day, EXPORT_PATH)
    except Exception:
        logger.exception("执行失败")
        return 1

    logger.info("全部完成, 耗时 %.2fs", time.time() - start)
    return 0


if __name__ == "__main__":
    sys.exit(main())
