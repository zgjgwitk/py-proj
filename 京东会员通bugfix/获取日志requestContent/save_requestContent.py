r"""
功能: 抓取 open.api 的特定日志, 保存 requestContent 内容到csv文件
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any, TextIO
from zoneinfo import ZoneInfo

import requests


LIST_URL = "https://log.ezrpro.work/api/logsnew"

DEFAULT_COOKIE = (
    "opt.authorize=267dffc44a4b4c05a4378fd3ac539eaf"
)

DEFAULT_CONFIG = {
    "app_name": "EZP.Open.Api",
    "cluster": "QCloud",
    "clusters": "QCloud",
    "log_categories": "HttpServer",
    "search_word": "#message:MemberRegisterCdpToCrm AND brandId:(-7095 -1752 -5417 -7054 -7135 -7097 -7126 -7091 -7003) AND duration:>1",
    "token": "267dffc44a4b4c05a4378fd3ac539eaf",
    "page_size": 100,
    "start_time": "2026-09-28 21:30:00",
    "end_time": "2026-09-28 21:49:00",
    "timezone": "Asia/Shanghai",
    "cookie": DEFAULT_COOKIE,
}

CSV_FIELDNAMES = ["sessionId", "brandId", "requestContent"]


@dataclass
class QueryWindow:
    start: datetime
    end: datetime

    @property
    def start_ms(self) -> int:
        return int(self.start.timestamp() * 1000)

    @property
    def end_ms(self) -> int:
        return int(self.end.timestamp() * 1000)

    @property
    def label(self) -> str:
        return f"{self.start:%Y-%m-%d %H:%M:%S} ~ {self.end:%Y-%m-%d %H:%M:%S}"


def log(message: str) -> None:
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="查询日志平台 logsnew 列表接口，逐页写入每日 CSV"
    )
    parser.add_argument("--start-time", default=DEFAULT_CONFIG["start_time"], help="开始时间，格式: YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--end-time", default=DEFAULT_CONFIG["end_time"], help="结束时间，格式: YYYY-MM-DD HH:MM:SS")
    # brand-id 可选：未传则不传 brandId 给后端，使用 search_word 内的过滤条件
    parser.add_argument("--brand-id", default=None, help="brandId；不传则不限制具体品牌，使用 search_word 中的过滤")
    parser.add_argument("--search-word", default=DEFAULT_CONFIG["search_word"], help="日志搜索词")
    parser.add_argument("--token", default=DEFAULT_CONFIG["token"], help="列表接口 token")
    parser.add_argument("--cookie", default=DEFAULT_CONFIG["cookie"], help="请求 Cookie")
    parser.add_argument("--app-name", default=DEFAULT_CONFIG["app_name"], help="appName")
    parser.add_argument("--cluster", default=DEFAULT_CONFIG["cluster"], help="cluster")
    parser.add_argument("--clusters", default=DEFAULT_CONFIG["clusters"], help="clusters")
    parser.add_argument("--log-categories", default=DEFAULT_CONFIG["log_categories"], help="logCategories")
    parser.add_argument("--page-size", type=int, default=DEFAULT_CONFIG["page_size"], help="分页大小")
    parser.add_argument("--timezone", default=DEFAULT_CONFIG["timezone"], help="时区")
    parser.add_argument(
        "--output",
        default="",
        help="输出 CSV 文件名前缀，默认 requestContent；最终文件命名 {prefix}_{YYYY-MM-DD}.csv",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="CSV 输出目录，默认为脚本所在目录",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="仅调试用，限制最终成功写入的条数；0 表示不限制",
    )
    parser.add_argument(
        "--split-mode",
        choices=("day", "hour"),
        default="hour",
        help="查询窗口切分粒度：hour 按整点小时（默认，单日量大时更快），day 按自然日",
    )
    return parser.parse_args()


def parse_datetime(value: str, tz: ZoneInfo) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return parsed.replace(tzinfo=tz)


def split_into_day_windows(start: datetime, end: datetime) -> list[QueryWindow]:
    """按自然日（00:00:00.000 ~ 23:59:59.999）切分查询窗口。"""
    windows: list[QueryWindow] = []
    current = start
    while current <= end:
        day_end = datetime.combine(current.date(), dt_time(23, 59, 59, 999000), current.tzinfo)
        window_end = min(day_end, end)
        windows.append(QueryWindow(start=current, end=window_end))
        current = window_end + timedelta(milliseconds=1)
    return windows


def split_into_hour_windows(start: datetime, end: datetime) -> list[QueryWindow]:
    """按整点小时（HH:00:00.000 ~ HH:59:59.999）切分查询窗口。

    单日数据量大、深分页慢时使用：单次请求命中量大幅下降，响应更快。
    CSV 仍按天落盘（由 createdOn 决定），所以不影响下游消费。
    """
    windows: list[QueryWindow] = []
    current = start
    while current <= end:
        # 对齐到当前所在小时的整点
        hour_start = current.replace(minute=0, second=0, microsecond=0)
        # 当前小时边界 = hh:59:59.999
        hour_end = datetime.combine(
            hour_start.date(),
            dt_time(hour_start.hour, 59, 59, 999000),
            current.tzinfo,
        )
        window_end = min(hour_end, end)
        windows.append(QueryWindow(start=current, end=window_end))
        # 推进到下一个整点起点
        current = (hour_start + timedelta(hours=1))
    return windows


def build_session(cookie: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://log.ezrpro.work/",
            "Content-Type": "application/json;charset=UTF-8",
            "Cookie": cookie,
            "User-Agent": "Mozilla/5.0",
        }
    )
    return session


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
    attempts: int = 3,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.request(method, url, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            # 每次请求结束统一 sleep 1s，避免触发风控
            time.sleep(1)
            return data
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            body_preview = ""
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                body_preview = f" body={exc.response.text[:300]}"
            log(f"请求失败，第 {attempt}/{attempts} 次重试: {method} {url} -> {exc}{body_preview}")
            # 失败也 sleep 1s，与成功路径一致
            time.sleep(1)
            if attempt < attempts:
                time.sleep(attempt)
    assert last_error is not None
    raise last_error


def timestamp_to_local_date(created_on_ms: int, tz: ZoneInfo) -> datetime.date | None:
    if not created_on_ms:
        return None
    try:
        return datetime.fromtimestamp(int(created_on_ms) / 1000, tz=tz).date()
    except (TypeError, ValueError, OSError):
        return None


class PageSink:
    """按日期懒加载打开每日 CSV 文件，同一日内复用句柄并去重。"""

    def __init__(
        self,
        *,
        output_dir: Path,
        prefix: str,
        tz: ZoneInfo,
        errors_path: Path,
    ) -> None:
        self._output_dir = output_dir
        self._prefix = prefix
        self._tz = tz
        self._errors_path = errors_path
        self._writers: dict[datetime.date, tuple[TextIO, csv.DictWriter, set[str]]] = {}
        self._error_fp: TextIO | None = None
        self.stats: dict[datetime.date, int] = {}
        self.error_count = 0
        self.duplicate_count = 0

    def _path_for(self, day: datetime.date) -> Path:
        return self._output_dir / f"{self._prefix}_{day:%Y-%m-%d}.csv"

    def _ensure_writer(self, day: datetime.date) -> tuple[TextIO, csv.DictWriter, set[str]]:
        cached = self._writers.get(day)
        if cached is not None:
            return cached
        path = self._path_for(day)
        is_new = not path.exists()
        # newline="" 防止 csv 在 Windows 下出现空行；utf-8-sig 便于 Excel 打开
        fp = path.open("a", encoding="utf-8-sig", newline="")
        writer = csv.DictWriter(fp, fieldnames=CSV_FIELDNAMES)
        if is_new:
            writer.writeheader()
            fp.flush()
        seen: set[str] = set()
        self._writers[day] = (fp, writer, seen)
        self.stats[day] = 0
        log(f"已创建每日 CSV: {path}")
        return fp, writer, seen

    def _ensure_error_fp(self) -> TextIO:
        if self._error_fp is None:
            self._error_fp = self._errors_path.open("a", encoding="utf-8")
        return self._error_fp

    def write_event(self, event: dict[str, Any]) -> None:
        """处理单条列表事件：立刻按 createdOn 落入对应日期 CSV 或错误文件。"""
        session_id = str(event.get("sessionId") or "").strip()
        brand_id = event.get("brandId")
        created_on = int(event.get("createdOn") or 0)
        raw_request_content = event.get("requestContent")

        if raw_request_content is None or str(raw_request_content) == "":
            err = {
                "sessionId": session_id,
                "brandId": brand_id,
                "createdOn": created_on,
                "reason": "列表数据缺少 requestContent 字段",
            }
            fp = self._ensure_error_fp()
            fp.write(json.dumps(err, ensure_ascii=False) + "\n")
            fp.flush()
            self.error_count += 1
            return

        day = timestamp_to_local_date(created_on, self._tz)
        if day is None:
            err = {
                "sessionId": session_id,
                "brandId": brand_id,
                "createdOn": created_on,
                "reason": "缺少 createdOn，无法归属日期",
            }
            fp = self._ensure_error_fp()
            fp.write(json.dumps(err, ensure_ascii=False) + "\n")
            fp.flush()
            self.error_count += 1
            return

        fp, writer, seen = self._ensure_writer(day)
        dedupe_key = f"{session_id}|{created_on}"
        if dedupe_key in seen:
            self.duplicate_count += 1
            return
        seen.add(dedupe_key)

        request_content = str(raw_request_content)
        writer.writerow(
            {
                "sessionId": session_id,
                "brandId": "" if brand_id is None else str(brand_id),
                "requestContent": request_content,
            }
        )
        fp.flush()
        self.stats[day] = self.stats.get(day, 0) + 1

    def close(self) -> None:
        for fp, _, _ in self._writers.values():
            try:
                fp.flush()
                fp.close()
            except OSError as exc:  # noqa: BLE001
                log(f"关闭每日 CSV 失败: {exc}")
        if self._error_fp is not None:
            try:
                self._error_fp.flush()
                self._error_fp.close()
            except OSError as exc:  # noqa: BLE001
                log(f"关闭错误文件失败: {exc}")


def fetch_log_list_streaming(
    session: requests.Session,
    window: QueryWindow,
    *,
    config: argparse.Namespace,
    sink: PageSink,
    remaining_limit: int,
) -> int:
    """逐页拉取日志并立即写入 sink；返回本窗口成功写入条数。"""
    log(f"开始查询列表窗口: {window.label}")
    page = 0
    written_in_window = 0
    while True:
        if remaining_limit > 0 and written_in_window >= remaining_limit:
            log(f"已达 --limit={config.limit} 限制，提前结束窗口")
            break
        payload = {
            "appName": config.app_name,
            "cluster": config.cluster,
            "clusters": config.clusters,
            "hosts": "",
            "levels": "",
            "logCategories": config.log_categories,
            "startDate": window.start_ms,
            "endDate": window.end_ms,
            "searchWord": config.search_word,
            "highlight": True,
            "histogram": True,
            "interval": 3600000,
            "sortMode": "3",
            "page": page,
            "pageSize": config.page_size,
            "token": config.token,
        }
        if config.brand_id is not None:
            payload["brandId"] = config.brand_id
        data = request_json(session, "POST", LIST_URL, payload=payload)
        log_events = (data.get("data") or {}).get("logEvents") or []
        total = (data.get("data") or {}).get("total")
        log(f"窗口 {window.label} 第 {page} 页返回 {len(log_events)} 条，total={total}")

        if not log_events:
            break

        for event in log_events:
            sink.write_event(event)
            if "stats" not in dir(sink):
                continue
            # 累加本窗口写入数；去重/错误的样本不计入
            for day_count in sink.stats.values():
                _ = day_count  # stats 内部已统计，此处不需要逐事件再加
        # 真正按 sink.stats 的总增量来判断限制更简单
        written_in_window = sum(sink.stats.values()) - sink._written_before_window
        if remaining_limit > 0 and written_in_window >= remaining_limit:
            log(f"已达 --limit={config.limit} 限制，停止翻页")
            break

        page += 1
    return written_in_window


def fetch_all_streaming(
    session: requests.Session,
    windows: list[QueryWindow],
    *,
    config: argparse.Namespace,
    sink: PageSink,
) -> int:
    """逐个窗口拉取；每个窗口首次进入时记录基线写入数，方便做 limit 控制。"""
    total_written = 0
    for window in windows:
        sink._written_before_window = total_written  # type: ignore[attr-defined]
        remaining = max(0, config.limit - total_written) if config.limit else 0
        written = fetch_log_list_streaming(
            session,
            window,
            config=config,
            sink=sink,
            remaining_limit=remaining,
        )
        total_written += written
        log(f"窗口 {window.label} 完成，本窗口新增 {written} 条，累计 {total_written} 条")
        if config.limit and total_written >= config.limit:
            break
    return total_written


def main() -> int:
    args = parse_args()
    tz = ZoneInfo(args.timezone)
    start = parse_datetime(args.start_time, tz)
    end = parse_datetime(args.end_time, tz) + timedelta(milliseconds=999)
    if start > end:
        raise ValueError("开始时间不能大于结束时间")

    script_dir = Path(__file__).resolve().parent
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir.strip() else script_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    prefix = args.output.strip() or "requestContent"
    if prefix.lower().endswith(".csv"):
        prefix = prefix[:-4]
    errors_path = output_dir / f"{prefix}_errors.jsonl"

    log("任务启动")
    log(f"查询时间范围: {start:%Y-%m-%d %H:%M:%S %Z} ~ {end:%Y-%m-%d %H:%M:%S %Z}")
    log(f"输出目录: {output_dir}")
    log(f"CSV 前缀: {prefix}")
    log(f"错误文件: {errors_path}")
    log(f"窗口切分粒度: {args.split_mode}")
    if args.split_mode == "hour":
        windows = split_into_hour_windows(start, end)
    else:
        windows = split_into_day_windows(start, end)
    log(f"共拆分为 {len(windows)} 个{('自然日' if args.split_mode == 'day' else '小时')}窗口")

    sink = PageSink(output_dir=output_dir, prefix=prefix, tz=tz, errors_path=errors_path)
    try:
        session = build_session(args.cookie)
        total_written = fetch_all_streaming(session, windows, config=args, sink=sink)
    finally:
        sink.close()

    log(f"处理完成：写入 {total_written} 条，跳过 {sink.error_count} 条，重复 {sink.duplicate_count} 条")
    if sink.stats:
        log("按天写入汇总：")
        for day in sorted(sink.stats.keys()):
            log(f"  {day:%Y-%m-%d}: {sink.stats[day]} 条 -> {output_dir / f'{prefix}_{day:%Y-%m-%d}.csv'}")
    if sink.error_count:
        log(f"错误样本已写入: {errors_path}")
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