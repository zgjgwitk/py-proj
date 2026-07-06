from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests


LIST_URL = "https://log.ezrpro.work/api/logs"
DETAIL_URL_TEMPLATE = (
    "https://log.ezrpro.work/api/log/session/{session_id}"
    "?sessionId={session_id}&appName={app_name}&estimatedDate={estimated_date}&page=0&pageSize=50"
)

DEFAULT_COOKIE = (
    "opt.authorize=267dffc44a4b4c05a4378fd3ac539eaf; "
    "jwt_token="
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJ1c2VyaWQiOjI3OSwibmFtZSI6InNzb2xvZ2luIiwidXNlcm5hbWUiOiJaaGFuZ0ppbmdXZWkiLCJleHBpciI6MTc4MTUxOTQ5Nn0."
    "jSscwoNgnT8lhLi-LRrIOSmpi7EoMDLumTJguUn7X5Q"
)

DEFAULT_CONFIG = {
    "app_name": "EZP.Open.Api",
    "cluster": "QCloud",
    "clusters": "QCloud",
    "log_categories": "HttpServer",
    "brand_id": "6973",
    "search_word": "#message:MemberRegisterCdpToCrm AND duration:>1",
    "token": "07f58351f8c44ce8a84ff3388481f874",
    "page_size": 100,
    # "start_time": "2026-06-10 22:00:00",
    "start_time": "2026-06-15 0:00:00",
    "end_time": "2026-06-15 23:59:59",
    "timezone": "Asia/Shanghai",
    "cookie": DEFAULT_COOKIE,
}

MESSAGE_KEYWORDS = ["请求request：", "请求request:", "reqargs:"]


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


def sql_escape(value: str) -> str:
    return value.replace("'", "''")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="查询京东会员通 unionId 日志并导出 Excel")
    parser.add_argument("--start-time", default=DEFAULT_CONFIG["start_time"], help="开始时间，格式: YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--end-time", default=DEFAULT_CONFIG["end_time"], help="结束时间，格式: YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--brand-id", default=DEFAULT_CONFIG["brand_id"], help="brandId")
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
        help="输出文件名，默认写入当前目录，例如 2026-06-10.txt",
    )
    parser.add_argument(
        "--detail-limit",
        type=int,
        default=0,
        help="仅调试用，限制明细查询数量；0 表示不限制",
    )
    return parser.parse_args()


def parse_datetime(value: str, tz: ZoneInfo) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return parsed.replace(tzinfo=tz)


def split_into_day_windows(start: datetime, end: datetime) -> list[QueryWindow]:
    windows: list[QueryWindow] = []
    current = start
    while current <= end:
        day_end = datetime.combine(current.date(), dt_time(23, 59, 59, 999000), current.tzinfo)
        window_end = min(day_end, end)
        windows.append(QueryWindow(start=current, end=window_end))
        current = window_end + timedelta(milliseconds=1)
    return windows


def build_session(cookie: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json, text/plain, */*",
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
            return response.json()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            body_preview = ""
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                body_preview = f" body={exc.response.text[:300]}"
            log(f"请求失败，第 {attempt}/{attempts} 次重试: {method} {url} -> {exc}{body_preview}")
            if attempt < attempts:
                time.sleep(attempt)
    assert last_error is not None
    raise last_error


def fetch_log_list(
    session: requests.Session,
    window: QueryWindow,
    *,
    config: argparse.Namespace,
) -> list[dict[str, Any]]:
    log(f"开始查询列表窗口: {window.label}")
    page = 0
    collected: list[dict[str, Any]] = []
    while True:
        payload = {
            "appName": config.app_name,
            "cluster": config.cluster,
            "clusters": config.clusters,
            "hosts": "",
            "levels": "",
            "logCategories": config.log_categories,
            "brandId": config.brand_id,
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
        data = request_json(session, "POST", LIST_URL, payload=payload)
        log_events = (data.get("data") or {}).get("logEvents") or []
        total = (data.get("data") or {}).get("total")
        log(f"窗口 {window.label} 第 {page} 页返回 {len(log_events)} 条，total={total}")
        if not log_events:
            break
        collected.extend(log_events)
        page += 1
    log(f"窗口 {window.label} 列表查询结束，共拿到 {len(collected)} 条")
    return collected


def deduplicate_sessions(log_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique_map: dict[str, dict[str, Any]] = {}
    for event in log_events:
        session_id = str(event.get("sessionId") or "").strip()
        created_on = int(event.get("createdOn") or 0)
        if not session_id or not created_on:
            continue
        saved = unique_map.get(session_id)
        if saved is None or created_on < int(saved.get("createdOn") or 0):
            unique_map[session_id] = event
    log(f"按 sessionId 去重后剩余 {len(unique_map)} 条")
    return list(unique_map.values())


def fetch_detail_events(
    session: requests.Session,
    *,
    session_id: str,
    created_on: int,
    app_name: str,
) -> list[dict[str, Any]]:
    url = DETAIL_URL_TEMPLATE.format(
        session_id=session_id,
        app_name=app_name,
        estimated_date=created_on,
    )
    data = request_json(session, "GET", url)
    return (data.get("data") or {}).get("logEvents") or []


def find_target_message(log_events: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    for event in log_events:
        message = str(event.get("message") or "")
        lowered = message.casefold()
        for keyword in MESSAGE_KEYWORDS:
            if keyword.casefold() in lowered:
                return message, keyword
    for event in log_events:
        message = str(event.get("message") or "")
        if "MixPin" in message and "unionId" in message:
            return message, "MixPin+unionId fallback"
    return None, None


def extract_json_candidates(message: str) -> list[str]:
    candidates: list[str] = []
    trimmed = message.strip()
    candidates.append(trimmed)
    for keyword in ["请求request：", "请求request:", "ReqArgs:", "reqargs:"]:
        marker_index = trimmed.find(keyword)
        if marker_index >= 0:
            candidates.append(trimmed[marker_index + len(keyword):].strip())
    first_brace = trimmed.find("{")
    last_brace = trimmed.rfind("}")
    if 0 <= first_brace < last_brace:
        candidates.append(trimmed[first_brace:last_brace + 1])
    return [candidate for candidate in candidates if candidate]


def parse_embedded_payload(message: str) -> dict[str, Any]:
    candidates = extract_json_candidates(message)
    seen: set[str] = set()
    queue = candidates[:]
    while queue:
        raw = queue.pop(0).strip()
        if not raw or raw in seen:
            continue
        seen.add(raw)
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, str):
                queue.append(parsed)
        except json.JSONDecodeError:
            pass
        if raw.startswith(("'", '"')) and raw.endswith(("'", '"')) and len(raw) >= 2:
            queue.append(raw[1:-1])
        if '\\"' in raw:
            queue.append(raw.replace('\\"', '"'))
        try:
            queue.append(bytes(raw, "utf-8").decode("unicode_escape"))
        except UnicodeDecodeError:
            pass
    raise ValueError(f"未能从 message 中解析出 JSON，原文片段: {message[:200]}")


def build_update_sql(row: dict[str, str]) -> str:
    union_id = sql_escape(row["unionId"])
    cdp_id = sql_escape(row["CdpId"])
    mix_pin = sql_escape(row["MixPin"])
    return (
        "update `crm_vip_info_third_party_bind` "
        f"set `CustomerIdentityExt`='{union_id}',LastModifiedDate='2026-06-15 23:59:59' "
        "where BrandId=6973 and ThirdPartyId=1 "
        f"and CustomerIdentity='{cdp_id}' and CustomerIdentityExt='{mix_pin}' ;"
    )


def build_fields_file_path(sql_output_path: Path) -> Path:
    return sql_output_path.with_name(f"{sql_output_path.stem}_fields.txt")


def export_sql_file(output_path: Path, results: list[dict[str, str]]) -> None:
    sql_lines = [build_update_sql(row) for row in results]
    content = "\n".join(sql_lines)
    if content:
        content += "\n"
    output_path.write_text(content, encoding="utf-8")


def export_fields_file(output_path: Path, results: list[dict[str, str]]) -> None:
    lines = ["sessionId\tMixPin\tunionId\tCdpId"]
    for row in results:
        lines.append(f'{row["sessionId"]}\t{row["MixPin"]}\t{row["unionId"]}\t{row["CdpId"]}')
    content = "\n".join(lines)
    if content:
        content += "\n"
    output_path.write_text(content, encoding="utf-8")


def process_details(
    session: requests.Session,
    list_events: list[dict[str, Any]],
    config: argparse.Namespace,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    results: list[dict[str, str]] = []
    errors: list[dict[str, Any]] = []
    total = len(list_events)
    for index, event in enumerate(list_events, start=1):
        session_id = str(event.get("sessionId") or "").strip()
        created_on = int(event.get("createdOn") or 0)
        if not session_id or not created_on:
            errors.append(
                {
                    "sessionId": session_id,
                    "createdOn": created_on,
                    "reason": "列表数据缺少 sessionId 或 createdOn",
                }
            )
            continue
        if config.detail_limit and index > config.detail_limit:
            log(f"已达到 detail-limit={config.detail_limit}，停止查询更多明细")
            break
        log(f"[{index}/{total}] 查询明细 sessionId={session_id}, createdOn={created_on}")
        try:
            detail_events = fetch_detail_events(
                session,
                session_id=session_id,
                created_on=created_on,
                app_name=config.app_name,
            )
            log(f"[{index}/{total}] 明细返回 {len(detail_events)} 条日志")
            target_message, matched_keyword = find_target_message(detail_events)
            if not target_message:
                raise ValueError("未找到包含目标关键词的 message")
            payload = parse_embedded_payload(target_message)
            mix_pin = str(payload.get("MixPin") or "")
            union_id = str((payload.get("extend") or {}).get("unionId") or "")
            cdp_id = str(payload.get("cdp_Id") or payload.get("CdpId") or "")
            if not mix_pin or not union_id or not cdp_id:
                raise ValueError(
                    f"字段缺失: MixPin={bool(mix_pin)}, unionId={bool(union_id)}, cdp_Id={bool(cdp_id)}"
                )
            result = {
                "sessionId": session_id,
                "MixPin": mix_pin,
                "unionId": union_id,
                "CdpId": cdp_id,
            }
            results.append(result)
            log(
                f"[{index}/{total}] 解析成功 keyword={matched_keyword}, "
                f"MixPin={mix_pin[:18]}..., unionId={union_id[:18]}..., CdpId={cdp_id}"
            )
        except Exception as exc:  # noqa: BLE001
            reason = str(exc)
            errors.append({"sessionId": session_id, "createdOn": created_on, "reason": reason})
            log(f"[{index}/{total}] 解析失败 sessionId={session_id}: {reason}")
    return results, errors


def main() -> int:
    args = parse_args()
    tz = ZoneInfo(args.timezone)
    start = parse_datetime(args.start_time, tz)
    end = parse_datetime(args.end_time, tz) + timedelta(milliseconds=999)
    if start > end:
        raise ValueError("开始时间不能大于结束时间")

    if args.output.strip():
        output_name = args.output.strip()
    elif start.date() == (end - timedelta(milliseconds=999)).date():
        output_name = f"{start:%Y-%m-%d}.txt"
    else:
        output_name = f"{start:%Y-%m-%d}_to_{(end - timedelta(milliseconds=999)):%Y-%m-%d}.txt"
    output_path = Path(__file__).resolve().parent / output_name
    fields_output_path = build_fields_file_path(output_path)

    log("任务启动")
    log(f"查询时间范围: {start:%Y-%m-%d %H:%M:%S %Z} ~ {end:%Y-%m-%d %H:%M:%S %Z}")
    log(f"SQL 文件: {output_path}")
    log(f"字段文件: {fields_output_path}")
    windows = split_into_day_windows(start, end)
    log(f"共拆分为 {len(windows)} 个自然日窗口")

    session = build_session(args.cookie)

    all_log_events: list[dict[str, Any]] = []
    for window in windows:
        all_log_events.extend(fetch_log_list(session, window, config=args))

    unique_events = deduplicate_sessions(all_log_events)
    results, errors = process_details(session, unique_events, args)
    export_sql_file(output_path, results)
    export_fields_file(fields_output_path, results)

    log(f"处理完成，成功 {len(results)} 条，失败 {len(errors)} 条")
    log(f"SQL 文件已导出: {output_path}")
    log(f"字段文件已导出: {fields_output_path}")
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
