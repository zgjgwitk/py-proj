"""调整京东会员等级并同步至 CDP；参考 query_member_point 的签名和认证规则。"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from 京东会员通_调用接口.查积分query_member_point import (
    DEFAULT_APP_KEY, DEFAULT_APP_SECRET, DEFAULT_BRAND_ID,
    DEFAULT_TIMEOUT_SECONDS, SUCCESS_CODE, build_signature,
)

LOGGER = logging.getLogger("jd_vip_adjust_member_grade")
DEFAULT_URL = "https://mkt-cloud-membership.jdx.com/CrmMemberGrade/adjustMemberGradeToCDP"
DEFAULT_ACCOUNT = "2022071_jd"
DEFAULT_OMID = "5rdVmMOMzd-UhTFmdSEqcJD5K3urAeuEtJ5t092ZleU"
DEFAULT_PLATFORM = "EZR"
DEFAULT_GRADE = 1
DEFAULT_ADJUST_TYPE = 38
DEFAULT_EXPIRE_TYPE = "1"
DEFAULT_CONTENT = "等级初始化"
MILLISECONDS_PER_SECOND = 1000
ERROR_PREVIEW_LENGTH = 500
EXIT_SUCCESS = 0
EXIT_FAILURE = 1


@dataclass(frozen=True)
class MemberGradeRequest:
    appkey: str
    brand_id: str
    account: str
    omid: str
    grade: int = DEFAULT_GRADE
    expire_type: str = DEFAULT_EXPIRE_TYPE
    adjust_type: int = DEFAULT_ADJUST_TYPE
    content: str = DEFAULT_CONTENT
    platform: str = DEFAULT_PLATFORM
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    ruid: Optional[str] = None
    timestamp: Optional[int] = None

    def to_payload(self) -> Dict[str, Any]:
        """保留示例中的字段名称和 null；时间格式由调用方按接口约定传入。"""
        # omid 可能为空（例如部分会员尚未建立 OMID 映射），由接口自行处理。
        for name in ("appkey", "brand_id", "account", "expire_type", "platform", "content"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} 不能为空")
        for name in ("grade", "adjust_type"):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} 必须为整数")
        if self.timestamp is not None and (type(self.timestamp) is not int or self.timestamp <= 0):
            raise ValueError("timestamp 必须为正整数毫秒时间戳")
        for name in ("start_time", "end_time", "ruid"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} 必须为非空字符串或 None")
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "expire_type": self.expire_type,
            "grade": self.grade,
            "type": self.adjust_type,
            "content": self.content,
            "timestamp": self.timestamp if self.timestamp is not None else int(time.time() * MILLISECONDS_PER_SECOND),
            "appkey": self.appkey,
            "brandId": self.brand_id,
            "omid": self.omid,
            "account": self.account,
            "platform": self.platform,
            "ruid": self.ruid,
        }


class MemberGradeClient:
    def __init__(self, app_secret: str, url: str = DEFAULT_URL,
                 timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        if not isinstance(app_secret, str) or not app_secret.strip():
            raise ValueError("app_secret 不能为空，用于生成 token 和 auth")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须为有限正数")
        self.app_secret = app_secret
        self.url = url
        self.timeout_seconds = timeout_seconds

    def adjust_member_grade(self, request_data: MemberGradeRequest) -> Dict[str, Any]:
        payload = request_data.to_payload()
        # 对完整等级请求重新签名，不能复用示例中的固定 token。
        payload["token"] = build_signature(payload, self.app_secret)
        header_timestamp = str(int(time.time() * MILLISECONDS_PER_SECOND))
        ruid = request_data.ruid or uuid.uuid4().hex
        headers = {
            "Content-Type": "application/json", "ruid": ruid,
            "source": request_data.appkey, "timestamp": header_timestamp,
            "auth": hashlib.md5((self.app_secret + header_timestamp).encode("utf-8")).hexdigest().upper(),
        }
        request = Request(self.url,
                          data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                          headers=headers, method="POST")
        LOGGER.info("请求会员等级调整，grade=%s，ruid=%s", request_data.grade, ruid)
        # 修改接口不自动重试，避免网络超时后重复执行。
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
                status_code = response.status
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"京东接口 HTTP {exc.code}: {error_body[:ERROR_PREVIEW_LENGTH]}") from exc
        except (URLError, OSError) as exc:
            raise RuntimeError(f"京东接口网络请求失败: {exc}") from exc
        try:
            result = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"京东接口返回非 JSON（HTTP {status_code}）: {response_body[:ERROR_PREVIEW_LENGTH]}") from exc
        if not isinstance(result, dict):
            raise RuntimeError("京东接口返回 JSON 顶层结构不是对象")
        LOGGER.info("等级调整响应完成，HTTP %s，code=%s，ruid=%s", status_code, result.get("code"), ruid)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="调整京东会员等级并同步到 CDP")
    parser.add_argument("--account", default=os.getenv("JD_ACCOUNT", DEFAULT_ACCOUNT))
    parser.add_argument("--omid", default=os.getenv("JD_OMID", DEFAULT_OMID))
    parser.add_argument("--brand-id", default=os.getenv("JD_BRAND_ID", DEFAULT_BRAND_ID))
    parser.add_argument("--appkey", default=os.getenv("JD_APP_KEY", DEFAULT_APP_KEY))
    parser.add_argument("--app-secret", default=os.getenv("JD_APP_SECRET", DEFAULT_APP_SECRET))
    parser.add_argument("--grade", type=int, default=DEFAULT_GRADE)
    parser.add_argument("--expire-type", default=DEFAULT_EXPIRE_TYPE)
    parser.add_argument("--type", dest="adjust_type", type=int, default=DEFAULT_ADJUST_TYPE)
    parser.add_argument("--content", default=DEFAULT_CONTENT)
    parser.add_argument("--platform", default=DEFAULT_PLATFORM)
    parser.add_argument("--start-time", help="按接口约定传入，不传则为 null")
    parser.add_argument("--end-time", help="按接口约定传入，不传则为 null")
    parser.add_argument("--timestamp", type=int, help="毫秒时间戳，默认当前时间")
    parser.add_argument("--ruid", default=os.getenv("JD_RUID"))
    parser.add_argument("--url", default=os.getenv("JD_MEMBER_GRADE_URL", DEFAULT_URL))
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        request_data = MemberGradeRequest(
            appkey=args.appkey,
            brand_id=args.brand_id,
            account=args.account,
            omid=args.omid,
            grade=args.grade,
            expire_type=args.expire_type,
            adjust_type=args.adjust_type,
            content=args.content,
            platform=args.platform,
            start_time=args.start_time,
            end_time=args.end_time,
            ruid=args.ruid,
            timestamp=args.timestamp,
        )
        result = MemberGradeClient(args.app_secret, args.url, args.timeout).adjust_member_grade(request_data)
    except (ValueError, RuntimeError) as exc:
        LOGGER.error("等级调整失败：%s", exc)
        return EXIT_FAILURE
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return EXIT_SUCCESS if str(result.get("code")) == SUCCESS_CODE else EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
