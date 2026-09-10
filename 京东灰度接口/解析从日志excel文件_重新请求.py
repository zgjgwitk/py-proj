r"""
功能补充：重新请求完成后，将每行 HTTP 状态码、响应内容和错误信息写入新的结果 Excel，源 Excel 只读不覆盖。

功能说明
========

1. 读取日志 Excel 文件，默认文件为：
   D:\Github\py-proj\京东灰度接口\file\京东灰度接口日志_20260908_142900_20260908_155105.xlsx
2. 提取 `httpPath`、`requestContent`、`extend.businessId`，组装 HTTP POST 请求：
   - 完整地址：`https://cb-tp.ezrpro.com` + `httpPath`
   - 请求体：`requestContent` JSON，并新增 `LocalRetry=1`
   - 请求头：`ruid=extend.businessId`
3. 按 Excel 行顺序逐条重新请求，并记录每条请求的结果。
4. 缺少必要列、JSON 无效或请求失败时，输出明确错误；
   若某条记录没有 `extend.businessId`，仍发送请求但将 `ruid` 设为空并记录警告。
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import requests
from openpyxl import load_workbook


DEFAULT_INPUT_PATH: Final = (
    Path(__file__).resolve().parent
    / "file"
    / "京东灰度接口日志_20260908_142900_20260908_155105_去重_v2.xlsx"
)
DEFAULT_BASE_URL: Final = "https://cb-tp.ezrpro.com"
DEFAULT_TIMEOUT_SECONDS: Final = 30
DEFAULT_RETRY_COUNT: Final = 3
RETRY_INTERVAL_SECONDS: Final = 1
LOCAL_RETRY_FIELD: Final = "LocalRetry"
LOCAL_RETRY_VALUE: Final = 1
HTTP_PATH_COLUMN: Final = "httpPath"
REQUEST_CONTENT_COLUMN: Final = "requestContent"
BUSINESS_ID_COLUMN: Final = "extend.businessId"
LOG_TIME_COLUMN: Final = "日志时间"
SESSION_ID_COLUMN: Final = "sessionId"
TIMESTAMP_COLUMN: Final = "timestamp"
TOKEN_COLUMN: Final = "token"
APPKEY_COLUMN: Final = "appkey"
BRAND_ID_COLUMN: Final = "brandId"
RUID_HEADER: Final = "ruid"
RESULT_STATUS_COLUMN: Final = "重新请求HTTP状态码"
RESULT_BODY_COLUMN: Final = "重新请求响应内容"
RESULT_ERROR_COLUMN: Final = "重新请求错误"
RESPONSE_CELL_LENGTH_LIMIT: Final = 32767
LOGGER = logging.getLogger("jd_gray_re_request")


@dataclass(frozen=True)
class ReRequestConfig:
    """重新请求任务配置。"""

    input_path: Path
    output_path: Path
    base_url: str
    timeout_seconds: int
    retry_count: int

    def validate(self) -> None:
        if not self.input_path.exists():
            raise FileNotFoundError(f"输入 Excel 文件不存在：{self.input_path}")
        if self.input_path.suffix.lower() not in {".xlsx", ".xlsm"}:
            raise ValueError("输入文件必须是 .xlsx 或 .xlsm 格式")
        if self.output_path == self.input_path:
            raise ValueError("输出文件不能覆盖输入文件")
        if not self.base_url.strip():
            raise ValueError("base-url 不能为空")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout 必须大于 0")
        if self.retry_count <= 0:
            raise ValueError("retries 必须大于 0")


@dataclass(frozen=True)
class ReRequestRecord:
    """从 Excel 单行解析出的请求数据。"""

    row_number: int
    http_path: str
    request_content: dict[str, object]
    business_id: str


@dataclass(frozen=True)
class ReRequestResult:
    """单条请求结果，按 Excel 行号与源数据关联。"""

    row_number: int
    status_code: int | None = None
    response_content: str = ""
    error: str = ""


class ExcelRequestReader:
    """读取 Excel 请求数据并完成必要字段校验。"""

    def read(self, input_path: Path) -> list[ReRequestRecord]:
        workbook = load_workbook(
            input_path,
            read_only=True,
            data_only=True,
        )
        try:
            sheet = workbook.active
            header_cells = next(sheet.iter_rows(min_row=1, max_row=1), None)
            if header_cells is None:
                raise ValueError("Excel 没有表头")

            header_indexes = self._build_header_indexes(header_cells)
            records: list[ReRequestRecord] = []
            for row_number, row in enumerate(sheet.iter_rows(min_row=2), start=2):
                if self._is_empty_row(row):
                    continue
                records.append(self._parse_row(row, row_number, header_indexes))
            return records
        finally:
            workbook.close()

    @staticmethod
    def _build_header_indexes(header_cells: tuple[object, ...]) -> dict[str, int]:
        indexes: dict[str, int] = {}
        for index, cell in enumerate(header_cells):
            if cell.value is None:
                continue
            header_name = str(cell.value).strip()
            if header_name:
                indexes[header_name] = index

        required_columns = {
            HTTP_PATH_COLUMN,
            REQUEST_CONTENT_COLUMN,
            BUSINESS_ID_COLUMN,
        }
        missing_columns = sorted(required_columns - indexes.keys())
        if missing_columns:
            raise ValueError(f"Excel 缺少必要列：{missing_columns}")
        return indexes

    @staticmethod
    def _is_empty_row(row: tuple[object, ...]) -> bool:
        return all(cell.value is None for cell in row)

    @staticmethod
    def _parse_row(
        row: tuple[object, ...],
        row_number: int,
        header_indexes: dict[str, int],
    ) -> ReRequestRecord:
        http_path = ExcelRequestReader._get_string_cell(
            row,
            header_indexes[HTTP_PATH_COLUMN],
            HTTP_PATH_COLUMN,
            row_number,
        )
        raw_request_content = ExcelRequestReader._get_string_cell(
            row,
            header_indexes[REQUEST_CONTENT_COLUMN],
            REQUEST_CONTENT_COLUMN,
            row_number,
        )
        business_id = ExcelRequestReader._get_optional_string_cell(
            row,
            header_indexes[BUSINESS_ID_COLUMN],
            BUSINESS_ID_COLUMN,
            row_number,
        )
        if not business_id:
            LOGGER.warning(
                "第 %s 行缺少 extend.businessId，将使用空 ruid 发送请求",
                row_number,
            )
        try:
            request_content = json.loads(raw_request_content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"第 {row_number} 行 requestContent JSON 无效：{exc.msg}"
            ) from exc
        if not isinstance(request_content, dict):
            raise ValueError(f"第 {row_number} 行 requestContent 必须是 JSON 对象")

        return ReRequestRecord(
            row_number=row_number,
            http_path=http_path,
            request_content=request_content,
            business_id=business_id,
        )

    @staticmethod
    def _get_string_cell(
        row: tuple[object, ...],
        index: int,
        column_name: str,
        row_number: int,
    ) -> str:
        if index >= len(row):
            raise ValueError(f"第 {row_number} 行缺少列 {column_name}")
        value = row[index].value
        if value is None or not str(value).strip():
            raise ValueError(f"第 {row_number} 行字段 {column_name} 为空")
        return str(value).strip()

    @staticmethod
    def _get_optional_string_cell(
        row: tuple[object, ...],
        index: int,
        column_name: str,
        row_number: int,
    ) -> str:
        """读取允许为空的字段；列本身缺失仍视为错误。"""

        if index >= len(row):
            raise ValueError(f"第 {row_number} 行缺少列 {column_name}")
        value = row[index].value
        return "" if value is None else str(value).strip()


class ExcelResultWriter:
    """将请求结果追加到新 Excel 文件，始终保留源文件不变。"""

    def write(self, input_path: Path, output_path: Path, results: list[ReRequestResult]) -> None:
        workbook = load_workbook(
            input_path,
            keep_vba=input_path.suffix.lower() == ".xlsm",
        )
        try:
            sheet = workbook.active
            headers = {
                str(cell.value).strip(): cell.column
                for cell in sheet[1]
                if cell.value is not None and str(cell.value).strip()
            }
            result_columns = self._ensure_result_columns(sheet, headers)
            self._remove_unused_columns(sheet)
            headers = {
                str(cell.value).strip(): cell.column
                for cell in sheet[1]
                if cell.value is not None and str(cell.value).strip()
            }
            result_columns = {
                column_name: headers[column_name]
                for column_name in (
                    RESULT_STATUS_COLUMN,
                    RESULT_BODY_COLUMN,
                    RESULT_ERROR_COLUMN,
                )
            }
            result_by_row = {item.row_number: item for item in results}
            for row_number, result in result_by_row.items():
                sheet.cell(row_number, result_columns[RESULT_STATUS_COLUMN]).value = result.status_code
                sheet.cell(row_number, result_columns[RESULT_BODY_COLUMN]).value = self._limit_cell_length(
                    result.response_content
                )
                sheet.cell(row_number, result_columns[RESULT_ERROR_COLUMN]).value = self._limit_cell_length(
                    result.error
                )

            output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = output_path.with_name(output_path.name + ".tmp")
            workbook.save(temporary_path)
            workbook.close()
            temporary_path.replace(output_path)
        except Exception:
            workbook.close()
            raise

    @staticmethod
    def _remove_unused_columns(sheet: object) -> None:
        """仅保留重新请求所需字段、指定追溯字段及请求结果字段。"""

        keep_columns = {
            HTTP_PATH_COLUMN,
            REQUEST_CONTENT_COLUMN,
            BUSINESS_ID_COLUMN,
            LOG_TIME_COLUMN,
            SESSION_ID_COLUMN,
            TIMESTAMP_COLUMN,
            TOKEN_COLUMN,
            APPKEY_COLUMN,
            BRAND_ID_COLUMN,
            RESULT_STATUS_COLUMN,
            RESULT_BODY_COLUMN,
            RESULT_ERROR_COLUMN,
        }
        columns_to_remove: list[int] = []
        for cell in sheet[1]:
            if cell.value is None:
                continue
            column_name = str(cell.value).strip()
            if column_name and column_name not in keep_columns:
                columns_to_remove.append(cell.column)

        for column_index in reversed(columns_to_remove):
            sheet.delete_cols(column_index)

    @staticmethod
    def _ensure_result_columns(sheet: object, headers: dict[str, int]) -> dict[str, int]:
        result_columns: dict[str, int] = {}
        next_column = max(headers.values(), default=0) + 1
        for column_name in (RESULT_STATUS_COLUMN, RESULT_BODY_COLUMN, RESULT_ERROR_COLUMN):
            if column_name in headers:
                result_columns[column_name] = headers[column_name]
            else:
                sheet.cell(1, next_column).value = column_name
                result_columns[column_name] = next_column
                next_column += 1
        return result_columns

    @staticmethod
    def _limit_cell_length(value: str) -> str:
        if len(value) <= RESPONSE_CELL_LENGTH_LIMIT:
            return value
        LOGGER.warning("响应内容超过 Excel 单元格长度限制，将截断保存")
        return value[:RESPONSE_CELL_LENGTH_LIMIT]


class ReRequestClient:
    """执行 POST 请求，并对临时网络错误进行有限重试。"""

    def __init__(self, config: ReRequestConfig) -> None:
        self._config = config
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json;charset=UTF-8",
                "User-Agent": "JdGrayReRequest/1.0",
            }
        )

    def close(self) -> None:
        self._session.close()

    def send(self, record: ReRequestRecord) -> requests.Response:
        url = self._build_url(record.http_path)
        body = dict(record.request_content)
        body[LOCAL_RETRY_FIELD] = LOCAL_RETRY_VALUE
        headers = {RUID_HEADER: record.business_id}
        last_error: Exception | None = None

        for attempt in range(1, self._config.retry_count + 1):
            try:
                LOGGER.info(
                    "第 %s 行发送请求：%s，ruid=%s，第 %s/%s 次",
                    record.row_number,
                    url,
                    record.business_id,
                    attempt,
                    self._config.retry_count,
                )
                response = self._session.post(
                    url,
                    json=body,
                    headers=headers,
                    timeout=self._config.timeout_seconds,
                )
                response.raise_for_status()
                LOGGER.info(
                    "第 %s 行请求成功：HTTP %s",
                    record.row_number,
                    response.status_code,
                )
                return response
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                LOGGER.warning(
                    "第 %s 行请求失败，第 %s/%s 次：%s",
                    record.row_number,
                    attempt,
                    self._config.retry_count,
                    exc,
                )
                if attempt < self._config.retry_count:
                    time.sleep(RETRY_INTERVAL_SECONDS * attempt)

        raise RuntimeError(
            f"第 {record.row_number} 行请求最终失败：{last_error}"
        ) from last_error

    def _build_url(self, http_path: str) -> str:
        normalized_base_url = self._config.base_url.rstrip("/")
        normalized_path = http_path.strip()
        if not normalized_path.startswith("/"):
            raise ValueError(f"httpPath 必须以 / 开头：{http_path!r}")
        return f"{normalized_base_url}{normalized_path}"


class ReRequestApplication:
    """协调 Excel 读取和逐条重新请求。"""

    def __init__(self, config: ReRequestConfig) -> None:
        self._config = config

    def run(self) -> int:
        self._config.validate()
        records = ExcelRequestReader().read(self._config.input_path)
        LOGGER.info("读取 Excel 完成：共 %s 条待请求数据", len(records))

        client = ReRequestClient(self._config)
        success_count = 0
        results: list[ReRequestResult] = []
        try:
            for record in records:
                try:
                    response = client.send(record)
                    results.append(
                        ReRequestResult(
                            row_number=record.row_number,
                            status_code=response.status_code,
                            response_content=self._response_content(response),
                        )
                    )
                    success_count += 1
                except Exception as exc:
                    response = getattr(exc, "response", None)
                    results.append(
                        ReRequestResult(
                            row_number=record.row_number,
                            status_code=getattr(response, "status_code", None),
                            response_content=self._response_content(response),
                            error=str(exc),
                        )
                    )
                    LOGGER.exception("第 %s 行请求失败，将继续处理后续数据", record.row_number)
        finally:
            client.close()

        ExcelResultWriter().write(
            self._config.input_path,
            self._config.output_path,
            results,
        )
        LOGGER.info("请求结果已写回新 Excel：%s", self._config.output_path)

        LOGGER.info(
            "重新请求完成：成功 %s/%s 条",
            success_count,
            len(records),
        )
        return 0

    @staticmethod
    def _response_content(response: requests.Response | None) -> str:
        if response is None:
            return ""
        try:
            return json.dumps(response.json(), ensure_ascii=False)
        except (ValueError, TypeError):
            return response.text or ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="读取日志 Excel 并重新请求京东会员接口"
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_PATH),
        help="输入 Excel 文件路径",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="结果 Excel 文件路径；未指定时在源文件名后追加‘_重新请求结果’",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="请求接口基础地址",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="单次请求超时时间（秒）",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRY_COUNT,
        help="失败重试次数",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        args = parse_args()
        input_path = Path(args.input).expanduser().resolve()
        output_path = (
            Path(args.output).expanduser().resolve()
            if args.output
            else input_path.with_name(f"{input_path.stem}_重新请求结果{input_path.suffix}")
        )
        config = ReRequestConfig(
            input_path=input_path,
            output_path=output_path,
            base_url=args.base_url,
            timeout_seconds=args.timeout,
            retry_count=args.retries,
        )
        return ReRequestApplication(config).run()
    except KeyboardInterrupt:
        LOGGER.warning("用户中断执行")
        return 130
    except Exception as exc:
        LOGGER.exception("执行失败：%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
