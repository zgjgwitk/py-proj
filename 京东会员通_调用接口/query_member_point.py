"""调用京东会员通 queryMemberPoint 接口。

示例：
    python query_member_point.py --account 1376513_jd

如需由 AppSecret 计算 token，请通过环境变量 JD_APP_SECRET 或 --app-secret
传入；未传入时使用命令行示例中已有的 token。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import unquote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

## sql: SELECT * FROM `ed_base_brand_jd_vip_cfg` where BrandId=7135

## 6887-bluebox
DEFAULT_APP_KEY = "7EBBCACF814CADB4E1D665AAE8DA216B"
DEFAULT_APP_SECRET = "EC2AF45ED9050DA2DCF5B9302910C971"
DEFAULT_BRAND_ID = "100000000012524"
DEFAULT_ACCOUNT = "71535_dbjd"
DEFAULT_TOKEN = "BC8FAC87ADC715B0BD48FAB6A9580EED" # 联调用

## 6959-比音勒芬
# DEFAULT_APP_KEY = "321AFAAA04E84FB2D01FBF4EE7F1C424"
# DEFAULT_APP_SECRET = "7EFFF4F329D0BD6D4072EA191C5F429B"
# DEFAULT_BRAND_ID = "100000000004343"
# DEFAULT_ACCOUNT = "200606551596"
# DEFAULT_TOKEN = "BC8FAC87ADC715B0BD48FAB6A9580EED" # 联调用

## 7135-bluebox
# DEFAULT_APP_KEY = "7CDAB3FF60A5D023B49E230385FAB501"
# DEFAULT_APP_SECRET = "813375C72EB18D221A76065ED33C9C2F"
# DEFAULT_BRAND_ID = "100000000023479"
# DEFAULT_ACCOUNT = "1201660_jd"
# DEFAULT_TOKEN = "BC8FAC87ADC715B0BD48FAB6A9580EED" # 联调用

LOGGER = logging.getLogger("jd_vip_query_member_point")
DEFAULT_URL = "https://mkt-cloud-membership.jdx.com/CrmMemberPoint/queryMemberPoint"
DEFAULT_PLATFORM = "JD"
DEFAULT_TIMEOUT_SECONDS = 10
SUCCESS_CODE = "0"


@dataclass(frozen=True)
class MemberPointRequest:
    timestamp: int
    appkey: str
    token: str
    brand_id: str
    account: str
    platform: str = DEFAULT_PLATFORM
    ruid: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        """生成接口要求的 camelCase JSON 请求体。"""
        return {
            "timestamp": self.timestamp,
            "appkey": self.appkey,
            "token": self.token,
            "brandId": self.brand_id,
            "account": self.account,
            "platform": self.platform,
            "ruid": self.ruid,
        }


def build_signature(payload: Dict[str, Any], app_secret: str) -> str:
    """按 C# JdVipConnectionHttpClientHelper.Sign 规则生成大写 MD5。"""
    if not app_secret:
        raise ValueError("app_secret 不能为空")

    parts = [app_secret]
    for key in sorted(payload):
        if not key or key.lower() == "token":
            continue
        value = payload[key]
        if value is None or value == "":
            continue
        # C# 实现不将数组、对象加入签名；本接口字段均为标量，保留该防御逻辑。
        if isinstance(value, (list, tuple, dict)):
            continue
        parts.extend((key, unquote(str(value))))
    parts.append(app_secret)
    return hashlib.md5("".join(parts).encode("utf-8")).hexdigest().upper()


def query_member_point(
    request_data: MemberPointRequest,
    url: str = DEFAULT_URL,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    app_secret: Optional[str] = None,
) -> Dict[str, Any]:
    """发送请求并返回解析后的 JSON；HTTP 或 JSON 异常会抛出明确异常。"""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds 必须大于 0")
    if not request_data.account.strip():
        raise ValueError("account 不能为空")

    body = json.dumps(request_data.to_payload(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ruid = request_data.ruid or uuid.uuid4().hex
    header_timestamp = str(int(time.time() * 1000))
    headers = {
        "Content-Type": "application/json",
        "ruid": ruid,
        "source": request_data.appkey,
        "timestamp": header_timestamp,
    }
    if app_secret:
        headers["auth"] = hashlib.md5((app_secret + header_timestamp).encode("utf-8")).hexdigest().upper()
    else:
        raise ValueError("调用直连版接口必须提供 app_secret，用于生成 auth 请求头")
    http_request = Request(
        url=url,
        data=body,
        headers=headers,
        method="POST",
    )
    LOGGER.info("请求京东会员通积分接口，account=%s，url=%s，ruid=%s", request_data.account, url, ruid)
    try:
        with urlopen(http_request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
            status_code = response.status
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"京东接口 HTTP {exc.code}: {error_body}") from exc
    except URLError as exc:
        raise RuntimeError(f"京东接口网络请求失败: {exc.reason}") from exc

    try:
        result = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"京东接口返回非 JSON（HTTP {status_code}）: {response_body[:500]}") from exc
    if not isinstance(result, dict):
        raise RuntimeError("京东接口返回 JSON 顶层结构不是对象")
    LOGGER.info("京东接口响应完成，HTTP %s，code=%s", status_code, result.get("code"))
    return result


def _env_or_default(name: str, default: str) -> str:
    return os.getenv(name, default)


def main() -> int:
    parser = argparse.ArgumentParser(description="查询京东会员通会员积分")
    parser.add_argument("--account", default=_env_or_default("JD_ACCOUNT", DEFAULT_ACCOUNT))
    parser.add_argument("--brand-id", default=_env_or_default("JD_BRAND_ID", DEFAULT_BRAND_ID))
    parser.add_argument("--appkey", default=_env_or_default("JD_APP_KEY", DEFAULT_APP_KEY))
    parser.add_argument("--token", default=os.getenv("JD_TOKEN", DEFAULT_TOKEN))
    parser.add_argument(
        "--app-secret",
        default=os.getenv("JD_APP_SECRET", DEFAULT_APP_SECRET),
        help="按 C# 规则计算 token 和 auth；环境变量 JD_APP_SECRET 可覆盖默认配置",
    )
    parser.add_argument("--timestamp", type=int, default=None, help="毫秒时间戳，默认当前时间")
    parser.add_argument("--ruid", default=os.getenv("JD_RUID"))
    parser.add_argument("--url", default=os.getenv("JD_MEMBER_POINT_URL", DEFAULT_URL))
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    timestamp = args.timestamp if args.timestamp is not None else int(time.time() * 1000)
    request_data = MemberPointRequest(timestamp, args.appkey, args.token, args.brand_id, args.account, ruid=args.ruid)
    payload = request_data.to_payload()
    if args.app_secret:
        payload["token"] = build_signature(payload, args.app_secret)
        request_data = MemberPointRequest(timestamp, args.appkey, payload["token"], args.brand_id, args.account, ruid=args.ruid)

    result = query_member_point(request_data, args.url, args.timeout, args.app_secret)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if str(result.get("code")) == SUCCESS_CODE else 1


if __name__ == "__main__":
    raise SystemExit(main())
