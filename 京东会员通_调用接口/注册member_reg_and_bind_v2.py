"""调用京东会员通 memberRegAndBindV2 接口；签名规则严格对齐 C# JdVipConnectionHttpClientHelper.Sign。

本文件不依赖同包内的任何模块，所有入参、签名、HTTP 客户端均自给自足。
"""

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
from urllib.parse import unquote
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("jd_vip_member_reg_and_bind_v2")

# ---- 顶层常量（默认值） ----

## 6887-山下有松
DEFAULT_CUSTOMER_ID = "100000000012524" # 示例请求中的京东侧品牌 ID（写入 brandId 字段）
DEFAULT_BRAND_ID = "100000000012524" # EZR 品牌 ID，仅用于日志标识
DEFAULT_APP_KEY = "7EBBCACF814CADB4E1D665AAE8DA216B" # 与 appSecret 配对的 appkey
DEFAULT_APP_SECRET = "EC2AF45ED9050DA2DCF5B9302910C971" # 与 appKey 配对的 appSecret，用于 token + auth 头签名
# Grade: 50001=>1, 50011=>2, 50012=>3, 50013=>4, 50014=>5,

# 示例请求中的京东账号（一般为 {EzrVipId}_jd）
DEFAULT_ACCOUNT = "1753064_jd"
# 示例请求中的明文手机号（脚本内部 MD5 后写入 mixMobile）
DEFAULT_MOBILE = "18943079362"
# 示例请求中的 extend 扩展字段（含 null 占位，调用方按需覆盖）
DEFAULT_EXTEND: Dict[str, Any] = {
    "sex": 0, # ezr:1-男,2-女 ; jd:1-男,0-女
    "birthday": "2000-8-17",
    "birth_type": 1,
    "register_time": "2025-12-11 20:57:51",
    "grade": 3
}

# 简短别名，便于直接引用
APP_KEY = DEFAULT_APP_KEY
APP_SECRET = DEFAULT_APP_SECRET
DEFAULT_PLATFORM = "EZR"
DEFAULT_TIMEOUT_SECONDS = 10
SUCCESS_CODE = "0"
DEFAULT_URL = "https://mkt-cloud-membership.jdx.com/CrmMemberV2/memberRegAndBindV2"
MILLISECONDS_PER_SECOND = 1000
ERROR_PREVIEW_LENGTH = 500
EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def sign_request(payload: Dict[str, Any], app_secret: str) -> str:
    """按 C# JdVipConnectionHttpClientHelper.Sign 规则生成大写 MD5 token。

    规则：
        result = MD5(appSecret + concat(sorted(key + UrlDecode(value))) + appSecret)
    跳过：token / null / 空字符串 / list / dict（包括 extend 字典整体）。
    """
    if not app_secret:
        raise ValueError("app_secret 不能为空")
    parts = [app_secret]
    for key in sorted(payload.keys()):
        if not key or key.lower() == "token":
            continue
        value = payload[key]
        if value is None:
            continue
        if isinstance(value, (list, tuple, dict)):
            continue
        text = str(value)
        if not text:
            continue
        parts.append(key)
        parts.append(unquote(text))
    parts.append(app_secret)
    return hashlib.md5("".join(parts).encode("utf-8")).hexdigest().upper()


@dataclass(frozen=True)
class MemberRegAndBindRequest:
    """CrmToCdpMemberRegAndBindRequest：会员注册并绑定至京东 CDP。

    各字段含义与 C# 一致；接口示例 request 中：
        account  -> 京东账号（约定 {EzrVipId}_jd）
        brandId  -> 京东侧品牌 ID（写入 customer_id）
        mixMobile-> MD5 大写密文手机号
        extend   -> 扩展字段字典
    """
    appkey: str
    customer_id: str
    account: str
    mobile: str
    extend: Dict[str, Any]
    platform: str = DEFAULT_PLATFORM
    omid: Optional[str] = None
    ruid: Optional[str] = None
    timestamp: Optional[int] = None

    def to_payload(self) -> Dict[str, Any]:
        for name in ("appkey", "customer_id", "account", "mobile", "platform"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} 不能为空")
        # 明文手机号经 MD5 加密后写入 mixMobile（接口要求大写 32 位）
        mix_mobile = hashlib.md5(self.mobile.encode("utf-8")).hexdigest().upper()
        if not isinstance(self.extend, dict):
            raise ValueError("extend 必须为字典")
        for name in ("birth_type", "sex", "grade"):
            value = self.extend.get(name)
            if value is not None and type(value) is not int:
                raise ValueError(f"extend.{name} 必须为整数或 None")
        if self.timestamp is not None and (type(self.timestamp) is not int or self.timestamp <= 0):
            raise ValueError("timestamp 必须为正整数毫秒时间戳")
        return {
            "timestamp": self.timestamp if self.timestamp is not None else int(time.time() * MILLISECONDS_PER_SECOND),
            "appkey": self.appkey,
            "brandId": self.customer_id,
            "account": self.account,
            "mixMobile": mix_mobile,
            "extend": dict(self.extend),
            "platform": self.platform,
            "omid": self.omid,
            "ruid": self.ruid,
        }


class MemberRegAndBindClient:
    def __init__(self, app_secret: str, url: str = DEFAULT_URL,
                 timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        if not isinstance(app_secret, str) or not app_secret.strip():
            raise ValueError("app_secret 不能为空，用于生成 token 和 auth")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须为有限正数")
        self.app_secret = app_secret
        self.url = url
        self.timeout_seconds = timeout_seconds

    def member_reg_and_bind(self, request_data: MemberRegAndBindRequest) -> Dict[str, Any]:
        payload = request_data.to_payload()
        # 对完整注册绑定请求重新签名，不能复用示例中的固定 token。
        payload["token"] = sign_request(payload, self.app_secret)
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
        LOGGER.info("请求会员注册并绑定，account=%s，customer_id=%s，ruid=%s",
                    request_data.account, request_data.customer_id, ruid)
        # 注册绑定接口不自动重试，避免网络超时后重复执行。
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
        LOGGER.info("注册绑定响应完成，HTTP %s，code=%s，ruid=%s", status_code, result.get("code"), ruid)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="调用京东会员通 memberRegAndBindV2 接口")
    parser.add_argument("--account", default=os.getenv("JD_ACCOUNT", DEFAULT_ACCOUNT))
    parser.add_argument("--customer-id", default=os.getenv("JD_CUSTOMER_ID", DEFAULT_CUSTOMER_ID),
                        help="京东侧品牌 ID（brandId 字段），区别于 EZR 品牌 ID")
    parser.add_argument("--brand-id", default=os.getenv("JD_BRAND_ID", DEFAULT_BRAND_ID),
                        help="EZR 品牌 ID，仅用于日志标识")
    parser.add_argument("--appkey", default=os.getenv("JD_APP_KEY", DEFAULT_APP_KEY))
    parser.add_argument("--app-secret", default=os.getenv("JD_APP_SECRET", DEFAULT_APP_SECRET))
    parser.add_argument("--mobile", default=os.getenv("JD_MOBILE", DEFAULT_MOBILE),
                        help="明文手机号，脚本内部 MD5 后写入 mixMobile")
    parser.add_argument("--name", dest="real_name", help="真实姓名（覆盖 extend.real_name）")
    parser.add_argument("--sex", type=int, help="性别 0未知 1男 2女（覆盖 extend.sex）")
    parser.add_argument("--birthday", help="生日，格式 yyyy-MM-dd（覆盖 extend.birthday）")
    parser.add_argument("--birth-type", type=int, default=None,
                        help="生日类别 1公历 2农历（覆盖 extend.birth_type，默认沿用 DEFAULT_EXTEND）")
    parser.add_argument("--register-time", help="会员注册时间，格式 yyyy-MM-dd HH:mm:ss（覆盖 extend.register_time）")
    parser.add_argument("--grade", type=int, help="会员等级 (1,2,3,4,5)（覆盖 extend.grade）")
    parser.add_argument("--union-id", dest="union_id", help="京东 UnionId（覆盖 extend.unionId）")
    parser.add_argument("--platform", default=DEFAULT_PLATFORM)
    parser.add_argument("--omid", default=os.getenv("JD_OMID"))
    parser.add_argument("--timestamp", type=int, help="毫秒时间戳，默认当前时间")
    parser.add_argument("--ruid", default=os.getenv("JD_RUID"))
    parser.add_argument("--url", default=os.getenv("JD_MEMBER_REG_AND_BIND_URL", DEFAULT_URL))
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        # 复制示例默认 extend，再按命令行覆盖
        extend: Dict[str, Any] = dict(DEFAULT_EXTEND)
        if args.real_name is not None:
            extend["real_name"] = args.real_name
        if args.sex is not None:
            extend["sex"] = args.sex
        if args.birthday is not None:
            extend["birthday"] = args.birthday
        if args.birth_type is not None:
            extend["birth_type"] = args.birth_type
        if args.register_time is not None:
            extend["register_time"] = args.register_time
        if args.grade is not None:
            extend["grade"] = args.grade
        if args.union_id is not None:
            extend["unionId"] = args.union_id

        request_data = MemberRegAndBindRequest(
            appkey=args.appkey,
            customer_id=args.customer_id,
            account=args.account,
            mobile=args.mobile,
            extend=extend,
            platform=args.platform,
            omid=args.omid,
            ruid=args.ruid,
            timestamp=args.timestamp,
        )
        result = MemberRegAndBindClient(args.app_secret, args.url, args.timeout).member_reg_and_bind(request_data)
    except (ValueError, RuntimeError) as exc:
        LOGGER.error("注册绑定失败：%s", exc)
        return EXIT_FAILURE
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return EXIT_SUCCESS if str(result.get("code")) == SUCCESS_CODE else EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())