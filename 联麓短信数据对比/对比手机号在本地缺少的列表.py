"""
需求描述: 读取本地 CSV, 按 任务编号 去 ES 匹配, 输出是否匹配 + ES chargeNum.
详细:
- 源文件> D:\\Github\\py-proj\\联麓短信数据对比\\sourceFile\\s_2.csv
- ES 条件> brandId=7163, gatewayId=<任务编号去冒号>
- 导出字段> 手机号, 任务编号, 计费, 状态, 发送时间, 接收时间, 是否匹配es, es.chargeNum
- 导出位置> sourceFile 目录下
"""

from __future__ import annotations

import csv
import logging
import sys
import time
from pathlib import Path

try:
    import pandas as pd
    import requests
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        f"缺少依赖: {exc.name}. 请先执行: pip install pandas requests openpyxl\n"
    )
    sys.exit(1)


# ============== 配置常量 ==============
SOURCE_FILE = Path(r"D:\Github\py-proj\联麓短信数据对比\sourceFile\0807.csv")
EXPORT_DIR = Path(r"D:\Github\py-proj\联麓短信数据对比\sourceFile")
EXPORT_PREFIX = "matched_"
EXPORT_SHEET_NAME = "匹配结果"

ES_URL = "http://192.168.12.124:88/@qcloud:base.es.biz-172.21.65.197:9200/"
ES_INDEX = "esmsgsms2608"
BRAND_ID = 7163

# CSV 表头比数据少 1 列, 按列索引读取. 0-indexed.
COL_INDEX = {
    "任务编号": 0,   # 带 "：" 前缀的原始任务编号
    "手机号": 4,
    "计费": 7,
    "状态": 8,
    "发送时间": 11,
    "接收时间": 12,
}

EXPORT_COLUMNS = [
    "手机号", "任务编号", "计费", "状态", "发送时间", "接收时间",
    "是否匹配es", "es.chargeNum", "es.reqTimeDay",
]

BATCH_SIZE = 1000
REQUEST_TIMEOUT = 10
RETRY_TIMES = 3
RETRY_BACKOFF = 2.0
# ES 性能不高, 每次请求后 sleep 50ms, 避免压垮 ES
REQUEST_SLEEP_SECONDS = 0.05


# ============== 日志 ==============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("match-sms-es")


# ============== 工具函数 ==============
def _strip_taskid_prefix(value: str) -> str:
    """去掉 CSV 任务编号前导的中文冒号, 用于 ES gatewayId 匹配."""
    if value is None:
        return ""
    s = str(value).strip()
    if s.startswith("："):
        s = s[1:]
    return s.strip()


def _to_float(value) -> float | None:
    """转换为 float, 失败返回 None."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ============== 业务函数 ==============
def load_csv(path: Path) -> pd.DataFrame:
    """读取 CSV. 复用原列索引解析方式, 按列索引构造导出字段."""
    if not path.exists():
        raise FileNotFoundError(f"源文件不存在: {path}")

    logger.info("开始读取 CSV: %s", path)
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = [row for row in reader]

    if not rows:
        raise ValueError("CSV 为空")

    header = rows[0]
    data_rows = rows[1:]
    max_cols = max((len(r) for r in data_rows), default=0)
    logger.info(
        "CSV 表头列数: %d, 数据行最大列数: %d, 数据行数: %d",
        len(header), max_cols, len(data_rows),
    )

    parts: dict[str, list[str]] = {}
    for col in EXPORT_COLUMNS:
        if col in {"是否匹配es", "es.chargeNum", "es.reqTimeDay"}:
            continue
        idx = COL_INDEX[col]
        if idx >= max_cols:
            raise ValueError(
                f"列 {col} (index={idx}) 超出 CSV 实际最大列数 {max_cols}"
            )
        vals = []
        for r in data_rows:
            vals.append(r[idx].strip() if idx < len(r) else "")
        parts[col] = vals

    df = pd.DataFrame(parts)
    logger.info("CSV 读取完成, 总行数: %d", len(df))
    return df


def fetch_charge_by_gateway(taskids: list[str]) -> dict[str, dict | None]:
    """按 gatewayId (任务编号去冒号) 去 ES 匹配, 返回 {gatewayId: {chargeNum, reqTimeDay} 或 None}.

    每批最多 BATCH_SIZE 个 gatewayId, 单批内用 terms 查询 + search_after 翻页.
    每个 gatewayId 只取首个命中文档的 chargeNum + reqTimeDay, 后续命中跳过避免重复计数.
    条件: brandId + gatewayId in (...).
    """
    if not taskids:
        return {}

    url = f"{ES_URL.rstrip('/')}/{ES_INDEX}/_search"
    headers = {"Content-Type": "application/json"}
    page_size = 1000

    result: dict[str, dict | None] = {}
    batches = (len(taskids) + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info(
        "ES 匹配开始, 共 %d 个 gatewayId, 分 %d 批 (brandId=%s)",
        len(taskids), batches, BRAND_ID,
    )

    for batch_index in range(batches):
        batch = taskids[batch_index * BATCH_SIZE: (batch_index + 1) * BATCH_SIZE]
        last_sort: list | None = None
        page = 0

        # 本批命中 gatewayId -> {chargeNum, reqTimeDay}
        batch_hits: dict[str, dict | None] = {}

        while True:
            payload: dict = {
                "size": page_size,
                "_source": ["gatewayId", "chargeNum", "reqTimeDay"],
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"brandId": str(BRAND_ID)}},
                            {"terms": {"gatewayId": batch}},
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
                    if batch_index == 0 and page == 0:
                        logger.info(
                            "ES 第1批第1页响应: total=%s, 本页 hits=%d",
                            data.get("hits", {}).get("total"), len(hits),
                        )
                    for hit in hits:
                        src = hit.get("_source", {}) or {}
                        gid = src.get("gatewayId")
                        if gid is None:
                            continue
                        gid_key = str(gid).strip()
                        if gid_key in batch_hits:
                            # 同一 gatewayId 已取过, 跳过避免重复计数
                            continue
                        batch_hits[gid_key] = {
                            "chargeNum": _to_float(src.get("chargeNum")),
                            "reqTimeDay": src.get("reqTimeDay"),
                        }
                    time.sleep(REQUEST_SLEEP_SECONDS)
                    last_err = None
                    break
                except Exception as exc:
                    last_err = exc
                    if attempt < RETRY_TIMES:
                        sleep_sec = RETRY_BACKOFF ** attempt
                        logger.warning(
                            "第 %d 批第 %d 页第 %d 次请求失败, %.1fs 后重试: %s",
                            batch_index + 1, page + 1, attempt, sleep_sec, exc,
                        )
                        time.sleep(sleep_sec)

            if last_err is not None:
                raise RuntimeError(
                    f"第 {batch_index + 1} 批第 {page + 1} 页请求最终失败: {last_err}"
                )

            page += 1
            if len(hits) < page_size:
                break
            last_sort = hits[-1].get("sort")

        # 未命中的 gatewayId 标记为 None
        for gid in batch:
            result[gid] = batch_hits.get(gid)

        if (batch_index + 1) % 10 == 0 or batch_index + 1 == batches:
            logger.info(
                "ES 匹配进度: %d/%d 批, 本批命中 %d/%d",
                batch_index + 1, batches, len(batch_hits), len(batch),
            )

    return result


def annotate_matches(
    df: pd.DataFrame, charge_map: dict[str, dict | None]
) -> pd.DataFrame:
    """基于 gatewayId -> {chargeNum, reqTimeDay} 映射, 给 df 加上 是否匹配es / es.chargeNum / es.reqTimeDay 三列."""
    df = df.copy()
    taskids_norm = df["任务编号"].astype(str).map(_strip_taskid_prefix)

    matched_flags: list[bool] = []
    charge_vals: list[float | None] = []
    day_vals: list[str | None] = []
    matched_count = 0
    for tid in taskids_norm:
        if not tid:
            matched_flags.append(False)
            charge_vals.append(None)
            day_vals.append(None)
            continue
        hit = charge_map.get(tid)
        is_hit = hit is not None
        matched_flags.append(is_hit)
        charge_vals.append(hit["chargeNum"] if hit else None)
        day_vals.append(hit["reqTimeDay"] if hit else None)
        if is_hit:
            matched_count += 1

    df["是否匹配es"] = matched_flags
    df["es.chargeNum"] = charge_vals
    df["es.reqTimeDay"] = day_vals
    logger.info("匹配完成: 命中 %d/%d", matched_count, len(df))
    return df


def export_excel(df: pd.DataFrame, source_path: Path) -> Path:
    """在 sourceFile 目录下导出 matched_<原文件名>.xlsx."""
    target = EXPORT_DIR / f"{EXPORT_PREFIX}{source_path.stem}.xlsx"
    tmp = target.with_name(target.stem + ".tmp.xlsx")
    try:
        with pd.ExcelWriter(tmp, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=EXPORT_SHEET_NAME, index=False)
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
    logger.info("已导出: %s (行数=%d)", target, len(df))
    return target


def main() -> int:
    start = time.time()
    try:
        df = load_csv(SOURCE_FILE)
        taskids = (
            df["任务编号"]
            .astype(str)
            .map(_strip_taskid_prefix)
            .loc[lambda s: s.astype(bool)]
            .unique()
            .tolist()
        )
        logger.info("去重后有效任务编号数: %d", len(taskids))

        charge_map = fetch_charge_by_gateway(taskids)
        df_annotated = annotate_matches(df, charge_map)
        export_excel(df_annotated, SOURCE_FILE)
    except Exception:
        logger.exception("执行失败")
        return 1

    logger.info("全部完成, 耗时 %.2fs", time.time() - start)
    return 0


if __name__ == "__main__":
    sys.exit(main())
