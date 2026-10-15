from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock
from typing import Final

from pull_logs_to_excel import (
    LogExportApplication,
    LogApiClient,
    QueryConfig,
    DEFAULT_APP_NAME,
    DEFAULT_CLUSTER,
    DEFAULT_BRAND_ID,
    DEFAULT_START_DATE_MS,
    DEFAULT_END_DATE_MS,
    DEFAULT_SEARCH_WORD,
    DEFAULT_SORT_MODE,
    DEFAULT_TOKEN,
)


BASE_DIR: Final = Path(__file__).resolve().parent
DEMO_OUTPUT_FILE: Final = BASE_DIR / "测试两页日志结果.xlsx"
PAGE_SIZE: Final = 100
TOTAL_PAGES: Final = 2
EXCEL_BATCH_SIZE: Final = 100


def build_log_event(index: int, page_number: int) -> dict[str, object]:
    old_cdp_id = f"{10000 + page_number * PAGE_SIZE + index}_dbjd"
    bind_vip_id = str(200000 + page_number * PAGE_SIZE + index)
    message = (
        f"历史绑定校验，BindId=6887|1|20240625|{old_cdp_id},"
        f"BindMobileMatch=True,VipMobileMatch=True,BindVipId={bind_vip_id}"
    )
    return {
        "id": f"evt-{page_number}-{index}",
        "message": message,
        "level": "INFO",
        "createdOn": DEFAULT_START_DATE_MS + index * 60_000 + page_number * 3_600_000,
        "loggerName": "JdVipConnectionMatchVersionManager",
    }


def build_page_response(page_number: int) -> dict[str, object]:
    log_events = [build_log_event(idx, page_number) for idx in range(PAGE_SIZE)]
    return {
        "status": True,
        "message": "ok",
        "data": {
            "total": PAGE_SIZE * TOTAL_PAGES,
            "logEvents": log_events,
        },
    }


def build_demo_session() -> MagicMock:
    session = MagicMock()
    requested_pages: list[int] = []

    def post_side_effect(url: str, json: dict[str, object], timeout: int) -> MagicMock:
        page = int(json.get("page", 0))
        requested_pages.append(page)
        if len(requested_pages) > TOTAL_PAGES:
            payload = {
                "status": True,
                "message": "ok",
                "data": {"total": PAGE_SIZE * TOTAL_PAGES, "logEvents": []},
            }
        else:
            payload = build_page_response(page)
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        response.text = __import__("json").dumps(payload, ensure_ascii=False)
        response.headers = {"Content-Type": "application/json"}
        return response

    session.post.side_effect = post_side_effect
    return session


def run_demo() -> Path:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config = QueryConfig(
        token=DEFAULT_TOKEN,
        cookie="opt.authorize=demo-cookie",
        app_name=DEFAULT_APP_NAME,
        cluster=DEFAULT_CLUSTER,
        brand_id=DEFAULT_BRAND_ID,
        start_date_ms=DEFAULT_START_DATE_MS,
        end_date_ms=DEFAULT_END_DATE_MS,
        search_word=DEFAULT_SEARCH_WORD,
        sort_mode=DEFAULT_SORT_MODE,
        page_size=PAGE_SIZE,
        excel_batch_size=EXCEL_BATCH_SIZE,
        timeout_seconds=30,
        retry_count=3,
        output_path=DEMO_OUTPUT_FILE,
    )

    demo_client = LogApiClient(config, session=build_demo_session())
    application = LogExportApplication(config, client=demo_client)
    return application.run()


if __name__ == "__main__":
    raise SystemExit(0 if run_demo().exists() else 1)
