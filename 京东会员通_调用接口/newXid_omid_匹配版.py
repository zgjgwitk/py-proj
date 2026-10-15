# -*- coding: UTF-8 -*-
#! /usr/bin/python
r"""直接请求京东会员匹配版 /CrmMember/newXid2omid 接口（新 XID 批量转 OMID）。

对齐 C# 实现：
    EZP.Open.Api.Business.ThirdParty.JdVipConnection
        .JdVipConnectionMatchVersionManager.ConvertNewXid2Omid
    以及 ezr.crm.commontool.apihost 中域名常量
        https://mkt-cloud-membership.jdx.com

请求体（JSON，京东侧直接调用）：
    {
        "timestamp":     毫秒时间戳,
        "appkey":        京东 AppKey,
        "token":         MD5 签名(大写),
        "brandId":       京东侧品牌 ID(customerId),
        "platform":      "JD",
        "newXids":       ["<newXid>", ...],
        "sourceAppkey":  京东 AppKey
    }

请求头：
    Content-Type = application/json
    ruid         = 32 位 GUID(无横线), 对齐 C# SendRequestV2 自动注入的 ruid

京东侧 token 签名（对齐 C# JdVipConnectionHttpClientHelper.Sign）：
    1) 跳过 "token" / 空值 / 数组 / JObject 类型字段
    2) key 升序排序
    3) 拼成 AppSecret + key + UrlDecode(value) + ... + AppSecret
    4) MD5 后转大写 16 进制

响应（JSON，京东侧）：
    {
        "status": "0",       # 成功码(字符串 "0" 表示成功)
        "errMsg": "...",
        "result": { "<newXid>": "<omid>", ... }
    }

示例：
    python newXid_omid_匹配版.py --xid "n_xxxx1" --xid "n_xxxx2"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError

# ============== 顶层常量(默认值 / 占位符) ==============

# 京东匹配版网关域名(对齐 ezr.crm.commontool.apihost 中硬编码常量)
JD_CDP_BASE_URL = "https://mkt-cloud-membership.jdx.com"
# 京东侧业务路径(对齐 C# SendRequestV2 第二个参数)
JD_CDP_PATH = "/CrmMember/newXid2omid"
# 完整 URL 模板, 默认指向 q1/prod 同地址(京东侧不分环境, 由 brandId 路由)
DEFAULT_URL = f"{JD_CDP_BASE_URL}{JD_CDP_PATH}"

# 京东侧品牌配置(请根据实际 brandId 调整后再发起请求)
# 占位符: 由用户写入真实值
APP_KEY = "1A501D82B46C27AC381100F28BD6242D"            # 京东 AppKey(写入 args.appkey)
SOURCE_APP_KEY = "9592B5FDED9D3C681E089CC1FEA72F78"     # 京东 sourceAppkey(可与 APP_KEY 不同)
APP_SECRET = "6A8580903BA362FC3FF47144BE168347"         # 京东 AppSecret, 用于 token 签名
BRAND_ID = "100000000040596"                            # 京东侧 brandId(customerId)

# 待转换的新 XID 列表(默认空, 实际值由用户在此处写入;
# 命令行 --xid 仍可追加, 二者会去重合并)
NEW_XIDS: List[str] = ["no*AAQSrFH5L9OiS1tuc2ggTyLLMDM3OMd9Qjy-WN1aErpD4n__KmYqHSvyxfcPUtzjGZ1_5znyZ7gFn7Xs5LObmJqJ1QdH4hJtu2xprfFYj09tcyVoYlDy1OPTHZMur_Xb8lXuxRGK"]

# 控制常量
MILLISECONDS_PER_SECOND = 1000
DEFAULT_TIMEOUT_SECONDS = 30
PLATFORM_JD = "JD"
ERROR_PREVIEW_LENGTH = 500
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
# 单次批量上限, 保守对齐 OUID 实现(MaxOuidCount = 10)
MAX_NEWXID_BATCH = 10

# 简短别名, 便于直接引用
APPKEY = APP_KEY
SOURCE_APPKEY = SOURCE_APP_KEY
SECRET = APP_SECRET


# ============== 签名工具 ==============

def jd_cdp_sign(params: Dict[str, Any], app_secret: str) -> str:
    """对齐 C# JdVipConnectionHttpClientHelper.Sign。

    规则:
        1) 跳过 "token" / 空值 / 数组 / JObject 类型字段
        2) key 升序排序
        3) 拼成 AppSecret + key + UrlDecode(value) + ... + AppSecret
        4) MD5 后大写 16 进制
    """
    if not isinstance(params, dict) or not params:
        raise ValueError("params 不能为空")
    if not isinstance(app_secret, str) or not app_secret:
        raise ValueError("app_secret 不能为空")

    sorted_keys = sorted(params.keys())
    query_parts: List[str] = [app_secret]
    for key in sorted_keys:
        if not key or key.lower() == "token":
            continue
        value = params[key]
        if value is None:
            continue
        # 数组/对象直接跳过(C# 端通过 IsArray / JObject 判断)
        if isinstance(value, (list, tuple, set, dict)):
            continue
        text = str(value)
        if not text:
            continue
        # C# 端先 UrlDecode 再拼接, Python 这边因为我们直接传明文, 不做反向解码
        query_parts.append(f"{key}{urllib.parse.unquote(text)}")
    query_parts.append(app_secret)
    raw = "".join(query_parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


# ============== 请求体组装 ==============

def build_jd_args(new_xids: Iterable[str]) -> Dict[str, Any]:
    """组装京东内部 /CrmMember/newXid2omid 接口的业务参数(不含 token)。"""
    new_xid_list = [item for item in (str(x).strip() for x in new_xids) if item]
    if not new_xid_list:
        raise ValueError("newXids 不能为空")
    if len(new_xid_list) > MAX_NEWXID_BATCH:
        raise ValueError(f"newXids 单次最多支持 {MAX_NEWXID_BATCH} 个有效值")
    return {
        "timestamp": int(time.time() * MILLISECONDS_PER_SECOND),
        "appkey": APPKEY,
        "brandId": BRAND_ID,
        "platform": PLATFORM_JD,
        # 服务端使用 HashSet<string>, JSON 序列化为数组
        "newXids": new_xid_list,
        "sourceAppkey": SOURCE_APPKEY,
    }


# ============== 客户端 ==============

class NewXid2OmidClient:
    """匹配版新 XID 转 OMID 客户端(直接请求京东网关)。"""

    def __init__(
        self,
        url: str = DEFAULT_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not isinstance(url, str) or not url.strip():
            raise ValueError("url 不能为空")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须为有限正数")
        self.url = url.strip()
        self.timeout_seconds = timeout_seconds

    def _build_url(self) -> str:
        return self.url

    def _build_headers(self) -> Dict[str, str]:
        # ruid 对齐 C# SendRequestV2 中 Guid.NewGuid().ToString("N")
        return {
            "Content-Type": "application/json; charset=utf-8",
            "ruid": _generate_ruid(),
        }

    def convert(self, new_xids: Iterable[str]) -> Dict[str, Any]:
        """执行新 XID 转 OMID 批量调用, 返回京东侧完整响应字典。"""
        jd_args = build_jd_args(new_xids)
        # token 由签名计算, 不能计入签名前的 args
        sign_source_args = {k: v for k, v in jd_args.items() if k != "token"}
        jd_args["token"] = jd_cdp_sign(sign_source_args, SECRET)

        body_bytes = json.dumps(
            jd_args, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        url = self._build_url()
        headers = self._build_headers()
        print(f"[匹配版请求URL] {url}")
        print(f"[匹配版请求Headers] {json.dumps(headers, ensure_ascii=False, sort_keys=True)}")
        print(f"[匹配版请求Body] {body_bytes.decode('utf-8')}")

        http_request = urllib.request.Request(
            url, data=body_bytes, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as resp:
                resp_body = resp.read().decode("utf-8")
                status_code = resp.status
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            print(
                f"[匹配版请求失败HTTPError] code={exc.code}\n"
                f"[匹配版请求失败HTTPError] body={error_body[:ERROR_PREVIEW_LENGTH]}",
                file=sys.stderr,
            )
            raise RuntimeError(
                f"京东接口 HTTP {exc.code}: {error_body[:ERROR_PREVIEW_LENGTH]}"
            ) from exc
        except (URLError, OSError) as exc:
            print(
                f"[匹配版请求失败URLError] reason={exc}",
                file=sys.stderr,
            )
            raise RuntimeError(f"京东接口网络请求失败: {exc}") from exc

        print(f"[匹配版响应状态] {status_code}")
        print(f"[匹配版响应内容] {resp_body}")
        try:
            return json.loads(resp_body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"京东接口返回非 JSON(HTTP {status_code}): "
                f"{resp_body[:ERROR_PREVIEW_LENGTH]}"
            ) from exc

    @staticmethod
    def extract_omid_map(new_xids: Iterable[str], response: Dict[str, Any]) -> Dict[str, str]:
        """按 C# 匹配版响应结构解析 OMID 映射。

        成功条件: status == "0" + result 为 {newXid: omid} 字典。
        注: 京东侧实际响应字段是 status / errMsg / result(对应
            C# JdVipBaseResponse<T> 的 status / errMsg / result JsonProperty)。
        """
        if not isinstance(response, dict) or str(response.get("status")) != "0":
            return {}
        data = response.get("result")
        if not isinstance(data, dict):
            return {}
        result: Dict[str, str] = {}
        for xid in new_xids:
            omid = data.get(xid)
            if isinstance(omid, str) and omid.strip():
                result[str(xid)] = omid
        return result


# ============== 工具 ==============

def _generate_ruid() -> str:
    """生成 32 位无横线 GUID, 对齐 C# Guid.NewGuid().ToString("N")。"""
    import uuid
    return uuid.uuid4().hex


# ============== 命令行入口 ==============

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="调用京东会员匹配版 /CrmMember/newXid2omid 接口(直接请求京东)",
    )
    parser.add_argument(
        "--xid",
        dest="new_xids",
        action="append",
        default=None,
        help="待转换的新 XID, 可重复传入, 例如 --xid n_xxxx1 --xid n_xxxx2。"
             "未传入时使用脚本顶部 NEW_XIDS 全局变量。",
    )
    parser.add_argument(
        "--url",
        default=os.getenv("JD_NEWXID2OMID_URL", DEFAULT_URL),
        help=f"完整请求 URL, 默认 {DEFAULT_URL}",
    )
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS,
        help=f"请求超时(秒), 默认 {DEFAULT_TIMEOUT_SECONDS}",
    )
    return parser.parse_args(argv)


def _ensure_config_filled() -> None:
    """防御性检查: 占位符未替换时拒绝执行, 避免发出无效请求。"""
    placeholders = {
        "APP_KEY": APP_KEY,
        "SOURCE_APP_KEY": SOURCE_APP_KEY,
        "APP_SECRET": APP_SECRET,
        "BRAND_ID": BRAND_ID,
    }
    unresolved = [name for name, val in placeholders.items()
                  if not val or "<" in val or ">" in val or "PLACEHOLDER" in val]
    if unresolved:
        raise ValueError(
            "以下占位符未替换为真实值: " + ", ".join(unresolved)
            + "。请在脚本顶部常量区写入实际配置后再调用。"
        )


def _collect_new_xids(cli_xids: Optional[Iterable[str]]) -> List[str]:
    """合并全局变量 NEW_XIDS 与命令行 --xid, 按出现顺序去重。"""
    sources: List[Iterable[str]] = []
    if NEW_XIDS:
        sources.append(NEW_XIDS)
    if cli_xids:
        sources.append(cli_xids)
    seen: set[str] = set()
    merged: List[str] = []
    for source in sources:
        for item in source:
            value = str(item).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            merged.append(value)
    return merged


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    new_xids = _collect_new_xids(args.new_xids)
    if not new_xids:
        print(
            "[匹配版入参错误] 至少在脚本顶部 NEW_XIDS 写入一个值, "
            "或通过 --xid 传入",
            file=sys.stderr,
        )
        return EXIT_FAILURE

    try:
        _ensure_config_filled()
        client = NewXid2OmidClient(
            url=args.url,
            timeout_seconds=args.timeout,
        )
        response = client.convert(new_xids)
    except (ValueError, RuntimeError) as exc:
        print(f"[匹配版调用失败] {exc}", file=sys.stderr)
        return EXIT_FAILURE

    omid_map = NewXid2OmidClient.extract_omid_map(new_xids, response)
    print(f"[匹配版OMID结果] {json.dumps(omid_map, ensure_ascii=False, indent=2)}")
    if str(response.get("status")) == "0" and omid_map:
        return EXIT_SUCCESS
    return EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
