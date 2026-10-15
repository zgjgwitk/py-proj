"""调用京东会员通直连版 /backend/membership/offline/pin2xidV2 接口（明文 pin 转 xid）。

对齐 C# 实现：
    EZR.OP.InnerApi.Business.JDOrder.JdOrderAddManager.ConvertXidByPinDirect

请求体（JSON）：
    {"appId": "<JdBrandId>", "pin": "<jd_xxx>"}

请求头：
    source   = AppKey
    timestamp= 当前毫秒时间戳字符串
    auth     = MD5(AppSecret + timestamp).toUpper()

响应（JSON）：
    {
        "status": "0",        # 成功码
        "errMsg": null,
        "result": { "xid": "o*AAS..." }
    }

示例：
    python pin2xidV2_直连版.py --pin jd_xxxxxxxx
    python pin2xidV2_直连版.py --pin jd_xxxxxxxx --appkey ... --app-secret ... --jd-brand-id ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("jd_vip_pin2xid_v2_direct")

# ---- 顶层常量（默认值）----

## 1149 - 加拿大鹅
DEFAULT_JD_BRAND_ID = "100000000062499"
DEFAULT_APP_KEY = "canadagoose"
DEFAULT_APP_SECRET = "18bc3af1fa381f68aecb4c70364724b3a5c74f6c8d5e33b914faa0b5570947f0941104c3654547f348e5d089514fcf90"
# DEFAULT_PIN = "jd_xxxxxxxx"

## 订单通应用
# DEFAULT_APP_KEY = "C3AE5FE08E8AAB3FA6E38786F8F4F11F"
# DEFAULT_APP_SECRET = "a88abef8b14b4ab3baaf367729394c59"
# 示例明文 pin（jd_ 前缀），用于直接验证接口
DEFAULT_PIN = "jd_dSOVDGwGAeNQ"

# 直连版完整 URL（路径 /backend/membership/offline/pin2xidV2）
DEFAULT_URL = "https://membership-express.jdx.com/backend/membership/offline/pin2xidV2"

MILLISECONDS_PER_SECOND = 1000
DEFAULT_TIMEOUT_SECONDS = 5
SUCCESS_STATUS = "0"
ERROR_PREVIEW_LENGTH = 500
EXIT_SUCCESS = 0
EXIT_FAILURE = 1

# 简短别名，便于直接引用
APP_KEY = DEFAULT_APP_KEY
APP_SECRET = DEFAULT_APP_SECRET


@dataclass(frozen=True)
class Pin2XidV2Request:
    """直连版明文 pin 转 xid 请求体（对齐 C# DirectPin2XidV2Request）。"""

    app_id: str  # 京东侧品牌 ID，写入 appId
    pin: str  # 明文京东 pin（jd_ 前缀），写入 pin

    def to_payload(self) -> Dict[str, Any]:
        for name in ("app_id", "pin"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} 不能为空")
        return {
            "appId": self.app_id,
            "pin": self.pin,
        }


class Pin2XidV2Client:
    """直连版明文 pin 转 xid 客户端（对齐 C# ConvertXidByPinDirect）。

    直连版不计算请求体 token，仅在请求头附带 source / timestamp / auth。
    """

    def __init__(self, app_key: str, app_secret: str, url: str = DEFAULT_URL,
                 timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        if not isinstance(app_key, str) or not app_key.strip():
            raise ValueError("app_key 不能为空，写入 source 请求头")
        if not isinstance(app_secret, str) or not app_secret.strip():
            raise ValueError("app_secret 不能为空，用于生成 auth 请求头")
        if not isinstance(url, str) or not url.strip():
            raise ValueError("url 不能为空")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须为有限正数")
        self.app_key = app_key
        self.app_secret = app_secret
        self.url = url.strip()
        self.timeout_seconds = timeout_seconds

    def _build_url(self) -> str:
        return self.url

    def _build_headers(self, timestamp_ms: str) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "source": self.app_key,
            "timestamp": timestamp_ms,
            "auth": hashlib.md5((self.app_secret + timestamp_ms).encode("utf-8")).hexdigest().upper(),
        }

    def convert_pin_to_xid(self, request_data: Pin2XidV2Request) -> Dict[str, Any]:
        payload = request_data.to_payload()
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp_ms = str(int(time.time() * MILLISECONDS_PER_SECOND))
        headers = self._build_headers(timestamp_ms)
        url = self._build_url()
        http_request = Request(url=url, data=body, headers=headers, method="POST")
        # 直接打印完整请求头与请求体，绕过 logger 等级，便于排查签名 / 入参问题。
        print(
            "[直连版请求] url={url}\n"
            "[直连版请求] headers={headers}\n"
            "[直连版请求] body={body}".format(
                url=url,
                headers=json.dumps(headers, ensure_ascii=False, sort_keys=True),
                body=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            )
        )
        try:
            with urlopen(http_request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
                status_code = response.status
        except HTTPError as exc:
            # 异常分支同样直接打印，便于排查 HTTP 500 等服务端错误。
            print(
                "[直连版请求失败HTTPError] headers={headers}\n"
                "[直连版请求失败HTTPError] body={body}".format(
                    headers=json.dumps(headers, ensure_ascii=False, sort_keys=True),
                    body=json.dumps(payload, ensure_ascii=False, sort_keys=True),
                )
            )
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"京东接口 HTTP {exc.code}: {error_body[:ERROR_PREVIEW_LENGTH]}") from exc
        except (URLError, OSError) as exc:
            print(
                "[直连版请求失败URLError] headers={headers}\n"
                "[直连版请求失败URLError] body={body}".format(
                    headers=json.dumps(headers, ensure_ascii=False, sort_keys=True),
                    body=json.dumps(payload, ensure_ascii=False, sort_keys=True),
                )
            )
            raise RuntimeError(f"京东接口网络请求失败: {exc}") from exc

        try:
            result = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"京东接口返回非 JSON（HTTP {status_code}）: {response_body[:ERROR_PREVIEW_LENGTH]}"
            ) from exc
        if not isinstance(result, dict):
            raise RuntimeError("京东接口返回 JSON 顶层结构不是对象")
        LOGGER.info(
            "直连版 pin 转 xid 响应完成，HTTP %s，status=%s，pin=%s",
            status_code, result.get("status"), request_data.pin,
        )
        return result

    def extract_xid(self, response: Dict[str, Any]) -> Optional[str]:
        """按 C# 直连版响应结构解析 xid。

        成功条件：HTTP 成功 + status == "0" + result.xid 非空。
        """
        if str(response.get("status")) != SUCCESS_STATUS:
            return None
        result_obj = response.get("result")
        if not isinstance(result_obj, dict):
            return None
        xid = result_obj.get("xid")
        if isinstance(xid, str) and xid.strip():
            return xid
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="调用京东会员通直连版明文 pin 转 xid 接口")
    parser.add_argument("--pin", default=os.getenv("JD_PIN", DEFAULT_PIN),
                        help="明文京东 pin（jd_ 前缀）")
    parser.add_argument("--jd-brand-id", dest="jd_brand_id",
                        default=os.getenv("JD_BRAND_ID", DEFAULT_JD_BRAND_ID),
                        help="京东侧品牌 ID（写入请求体 appId 字段）")
    parser.add_argument("--appkey", default=os.getenv("JD_APP_KEY", DEFAULT_APP_KEY),
                        help="京东 AppKey（写入请求头 source）")
    parser.add_argument("--app-secret", default=os.getenv("JD_APP_SECRET", DEFAULT_APP_SECRET),
                        help="京东 AppSecret（用于生成 auth 头）")
    parser.add_argument("--url", default=os.getenv("JD_DIRECT_URL", DEFAULT_URL),
                        help=f"直连版完整 URL，默认 {DEFAULT_URL}")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    # 默认放行 INFO，确保请求头 / 请求体日志在没有 --verbose 时也能看到；
    # --verbose 进一步放开到 DEBUG，便于排查。
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        request_data = Pin2XidV2Request(app_id=args.jd_brand_id, pin=args.pin)
        client = Pin2XidV2Client(
            app_key=args.appkey,
            app_secret=args.app_secret,
            url=args.url,
            timeout_seconds=args.timeout,
        )
        response = client.convert_pin_to_xid(request_data)
    except (ValueError, RuntimeError) as exc:
        LOGGER.error("直连版 pin 转 xid 失败：%s", exc)
        return EXIT_FAILURE

    print(json.dumps(response, ensure_ascii=False, indent=2))
    if str(response.get("status")) == SUCCESS_STATUS:
        xid = client.extract_xid(response)
        if xid:
            LOGGER.info("PIN %s -> XID %s 转换成功", args.pin, xid)
        return EXIT_SUCCESS
    return EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
