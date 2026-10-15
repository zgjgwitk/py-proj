# -*- coding: UTF-8 -*-
#! /usr/bin/python
# 功能: open.api 接口请求公共方法(SHA1 签名、时间戳生成、URL 参数组装)

import hashlib
import json
import urllib.parse
from datetime import datetime


def generate_timestamp(dt=None):
    """
    生成 open.api 接口要求的时间戳, 格式 yyyyMMddHHmmss
    对应服务端 MyFormatFullDateTimeStrEx 扩展方法。

    参数:
        dt (datetime, 可选): 指定时间, 默认当前时间

    返回:
        str: 时间戳字符串
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y%m%d%H%M%S")


def generate_sign(app_id, timestamp, token):
    """
    生成 open.api 接口的 SHA1 签名(大写)。
    对应服务端 ApiHelper.GetSign 中 EncryptType != 1 的分支。
    算法: SHA1("AppId={AppId}&Timestamp={Timestamp}&Token={Token}"), 结果转大写。

    参数:
        app_id (str): 应用编码
        timestamp (str): yyyyMMddHHmmss 格式的时间戳
        token (str): 访问令牌, 优先使用外部系统 AccessToken, 否则使用品牌 AccessToken

    返回:
        str: 大写形式的 SHA1 签名
    """
    raw = f"AppId={app_id}&Timestamp={timestamp}&Token={token}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest().upper()


def build_query_string(args_dict, app_id, app_system, timestamp, sign):
    """
    组装 open.api 接口的 query string。
    Args 字段需先 JSON 序列化, 再做 URL 编码。

    参数:
        args_dict (dict): 业务参数(将 JSON 序列化后整体作为 Args 的值)
        app_id (str): 应用编码
        app_system (str): 调用系统标识, 如 EZR-Inside
        timestamp (str): yyyyMMddHHmmss 格式的时间戳(由调用方传入, 保证与签名一致)
        sign (str): 已生成的签名

    返回:
        str: 可直接拼接到 URL 的 query string
    """
    # ensure_ascii=False 保证中文不被转义, 与服务端 JsonfastFormatter 行为一致
    args_json = json.dumps(args_dict, ensure_ascii=False, separators=(",", ":"))
    params = {
        "AppId": app_id,
        "AppSystem": app_system,
        "Timestamp": timestamp,
        "Sign": sign,
        "Args": args_json,
    }
    return urllib.parse.urlencode(params)


def build_request_url(base_url, args_dict, app_id, app_system, token):
    """
    一站式生成完整请求 URL(已包含 query string 与签名)。

    参数:
        base_url (str): 接口地址, 例如 https://open-q1.ezrpro.com/api/JdVipMatchVersion/UpdateMemberData
        args_dict (dict): 业务参数
        app_id (str): 应用编码
        app_system (str): 调用系统标识
        token (str): 访问令牌

    返回:
        str: 完整的请求 URL
    """
    timestamp = generate_timestamp()
    sign = generate_sign(app_id, timestamp, token)
    # 业务参数里携带毫秒级 timestamp(参照 demo 中的 1789653925478)
    args_dict["timestamp"] = int(datetime.now().timestamp() * 1000)
    query = build_query_string(args_dict, app_id, app_system, timestamp, sign)
    return f"{base_url}?{query}"