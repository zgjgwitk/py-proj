from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from typing import Final

from pull_logs_to_excel import (
    HourLogExportController,
    LogExportApplication,
    LogApiClient,
    QueryConfig,
    DEFAULT_APP_NAME,
    DEFAULT_CLUSTER,
    DEFAULT_BRAND_ID,
    DEFAULT_SEARCH_WORD,
    DEFAULT_SORT_MODE,
    DEFAULT_TOKEN,
)


BASE_DIR: Final = Path(__file__).resolve().parent
DEMO_OUTPUT_BASE: Final = BASE_DIR / "按小时测试结果.xlsx"
HOUR_WINDOW_START_MS: Final = 1_789_387_200_000
HOUR_WINDOW_END_MS: Final = 1_789_394_399_999
HOUR_MS: Final = 60 * 60 * 1000
PAGE_SIZE: Final = 100
PAGES_PER_HOUR: Final = 2
EXCEL_BATCH_SIZE: Final = 100


def format_hour_label(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y%m%d_%H")


def build_log_event(index: int, hour_offset: int, page_number: int) -> dict[str, object]:
    old_cdp_id = f"{hour_offset * 10000 + page_number * PAGE_SIZE + index}_dbjd"
    bind_vip_id = str(300000 + hour_offset * 1000 + page_number * PAGE_SIZE + index)
    message = (
        f"历史绑定校验，BindId=6887|1|20240625|{old_cdp_id},"
        f"BindMobileMatch=True,VipMobileMatch=True,BindVipId={bind_vip_id}"
    )
    created_on = HOUR_WINDOW_START_MS + hour_offset * HOUR_MS + page_number * 1_800_000 + index * 60_000
    return {
        "id": f"evt-{hour_offset}-{page_number}-{index}",
        "message": message,
        "level": "INFO",
        "createdOn": created_on,
        "loggerName": "JdVipConnectionMatchVersionManager",
    }


def build_page_response(hour_offset: int, page_number: int) -> dict[str, object]:
    log_events = [build_log_event(idx, hour_offset, page_number) for idx in range(PAGE_SIZE)]
    return {
        "status": True,
        "message": "ok",
        "data": {
            "total": PAGE_SIZE * PAGES_PER_HOUR,
            "logEvents": log_events,
        },
    }


class DemoSessionFactory:
    def __init__(self) -> None:
        self._hour_counters: dict[int, int] = {}

    def create(self, hour_start_ms: int) -> MagicMock:
        session = MagicMock()
        hour_offset = (hour_start_ms - HOUR_WINDOW_START_MS) // HOUR_MS
        self._hour_counters[hour_offset] = 0

        def post_side_effect(url: str, json: dict[str, object], timeout: int) -> MagicMock:
            self._hour_counters[hour_offset] += 1
            page_index = self._hour_counters[hour_offset]
            if page_index > PAGES_PER_HOUR:
                payload = {
                    "status": True,
                    "message": "ok",
                    "data": {"total": PAGE_SIZE * PAGES_PER_HOUR, "logEvents": []},
                }
            else:
                payload = build_page_response(hour_offset, page_index - 1)
            response = MagicMock()
            response.raise_for_status.return_value = None
            response.json.return_value = payload
            response.text = __import__("json").dumps(payload, ensure_ascii=False)
            response.headers = {"Content-Type": "application/json"}
            return response

        session.post.side_effect = post_side_effect
        return session


class DemoApplicationFactory:
    def __init__(self, session_factory: DemoSessionFactory) -> None:
        self._session_factory = session_factory

    def __call__(self, config: QueryConfig) -> LogExportApplication:
        session = self._session_factory.create(config.start_date_ms)
        demo_client = LogApiClient(config, session=session)
        return LogExportApplication(config, client=demo_client)


def run_demo() -> list[Path]:
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
        start_date_ms=HOUR_WINDOW_START_MS,
        end_date_ms=HOUR_WINDOW_END_MS,
        search_word=DEFAULT_SEARCH_WORD,
        sort_mode=DEFAULT_SORT_MODE,
        page_size=PAGE_SIZE,
        excel_batch_size=EXCEL_BATCH_SIZE,
        timeout_seconds=30,
        retry_count=3,
        output_path=DEMO_OUTPUT_BASE,
    )

    controller = HourLogExportController(
        base_config=config,
        application_factory=DemoApplicationFactory(DemoSessionFactory()),
    )
    return controller.run()


if __name__ == "__main__":
    raise SystemExit(0 if run_demo() else 1)
