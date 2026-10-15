# -*- coding: UTF-8 -*-
#! /usr/bin/python
r"""
功能: 调用 open.api 接口
  接口地址: https://open-q1.ezrpro.com/api/JdVipMatchVersion/UpdateMemberData
  服务端:   D:\code\EZP.OpenApi\BusiCore\EZP.Open.Api\Controllers\JdVipMatchVersionController.cs
  公共方法: D:\Github\py-proj\open.api接口请求\openapi_sign.py
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# 引入公共签名/URL 组装方法
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from openapi_sign import generate_sign, generate_timestamp  # noqa: E402

# ============== 造数据专用参数 ==============

# 默认会员标识, 不显式传 r_uid 时使用此值
DEFAULT_R_UID = "977d1c7e-f1e8-4ee0-ab31-6d4452a1384c8"

# totalOrderPrice , totalOrderCount
Total_Order_Price = 210000
Total_Order_Count = 4

# ============== 可配置参数 ==============
BASE_URL = "https://open-q1.ezrpro.com/api/JdVipMatchVersion/UpdateMemberData"
APP_ID = "q1dpp_test"
APP_SYSTEM = "EZR-Inside"
# 品牌级 AccessToken, 与服务端 ApiHelper.GetSign 中的 barnd.AccessToken 对应
BRAND_TOKEN = "a83c5efe72262e78280d68fe95c5061e"

# 业务参数中的密钥与品牌标识(对应 Args.appkey / Args.token / Args.brandId)
APP_KEY = "A9939AACB0CF06004388FA6EF9E41546"
APP_TOKEN = "A9939AACB0CF06004388FA6EF9E41546"
BRAND_ID = "100000000037737"

# 额外 header(对应服务端 BrandMiddleware / 多环境路由)
EXTRA_HEADERS = {
    "ezr-env-tag": "d6310",
    "ezr-brand-id": "1104",
}


def build_member_args(mix_phone, mix_pin, real_name=None, grade=0, point=0,
                      bind_status=2, card_status=1, jd_bind_time=None,
                      account="", platform="JD"):
    """
    组装 UpdateMemberData 接口的 Args 业务参数。
    字段命名严格对齐服务端接口定义, 严禁臆造字段。

    参数:
        mix_phone (str): 加密手机号(必填)
        mix_pin (str): 加密 PIN(必填)
        real_name (str, 可选): 真实姓名
        grade (int): 会员等级
        point (int): 积分
        bind_status (int): 绑定状态
        card_status (int): 卡状态
        jd_bind_time (str, 可选): 京东端绑定时间, 格式 yyyy-MM-dd HH:mm:ss
        account (str): 账号
        platform (str): 平台标识, 京东为 JD
        r_uid (str, 可选): 京东返回的唯一用户标识

    返回:
        dict: 业务参数字典
    """
    return {
        "bind_status": bind_status,
        "cdp_Id": None,
        "MixPhone": mix_phone,
        "MixPin": mix_pin,
        "jd_bind_time": jd_bind_time,
        "cardStatus": card_status,
        "totalOrderPrice": Total_Order_Price,
        "totalOrderCount": Total_Order_Count,
        "jdChannelNo": None,
        "memberData": {
            "realName": real_name,
            "grade": grade,
            "point": point,
            "sex": 0,
            "birthday": None,
            "birth_type": 0,
            "qq": None,
            "province": None,
            "city": None,
            "district": None,
            "email": None,
            "extend": None,
        },
        "appkey": APP_KEY,
        "token": APP_TOKEN,
        "brandId": BRAND_ID,
        "account": account,
        "omid": None,
        "platform": platform,
        "RUid": DEFAULT_R_UID,
        "timestamp":1789653925478,
    }


def call_update_member_data(args):
    """
    调用 UpdateMemberData 接口。
    服务端 JdVipMatchVersionController 全部为 [HttpPost],
    实际接受 application/x-www-form-urlencoded 提交(签名/时间戳/AppId/Args 等
    全部作为 form 字段), Args 字段值为 URL 编码后的 JSON 字符串,
    对应 BaseApiReqInfo2 模型的自动绑定。

    参数:
        args (dict): build_member_args 组装的业务参数

    返回:
        dict: 接口响应内容(已反序列化为字典)
    """
    # 生成签名所需时间戳, form body 与签名保持一致
    timestamp = generate_timestamp()
    sign = generate_sign(APP_ID, timestamp, BRAND_TOKEN)

    # Args 走 form 时为 URL 编码的 JSON 字符串(对齐 demo 中 query 编码行为)
    args_value = urllib.parse.quote(json.dumps(args, ensure_ascii=False, separators=(",", ":")))
    form_body = (
        f"AppId={urllib.parse.quote(APP_ID)}"
        f"&AppSystem={urllib.parse.quote(APP_SYSTEM)}"
        f"&Timestamp={urllib.parse.quote(timestamp)}"
        f"&Sign={urllib.parse.quote(sign)}"
        f"&Args={args_value}"
    )
    body_bytes = form_body.encode("utf-8")
    print(f"[请求URL] {BASE_URL}")
    print(f"[请求Body] {form_body}")

    req = urllib.request.Request(BASE_URL, data=body_bytes, method="POST")
    # 默认 header
    req.add_header("Content-Type", "application/x-www-form-urlencoded; charset=utf-8")
    req.add_header("User-Agent", "Mozilla/5.0 (OpenApi-Python-Client)")
    # 业务级 header
    for key, value in EXTRA_HEADERS.items():
        req.add_header(key, value)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")
            print(f"[响应状态] {resp.status}")
            print(f"[响应内容] {resp_body}")
            try:
                return json.loads(resp_body)
            except json.JSONDecodeError:
                return {"_raw": resp_body}
    except urllib.error.HTTPError as e:
        print(f"[HTTP错误] {e.code} {e.reason}", file=sys.stderr)
        try:
            err_body = e.read().decode("utf-8")
            print(f"[错误内容] {err_body}", file=sys.stderr)
        except Exception:
            pass
        raise
    except urllib.error.URLError as e:
        print(f"[网络错误] {e.reason}", file=sys.stderr)
        raise


if __name__ == "__main__":
    # ===== 示例调用 =====
    # TODO: 替换为实际值(从业务表查询或外部数据源注入)
    args = build_member_args(
        mix_phone="c423fd4b962ad15bd4e72ec2e653c4b7",
        mix_pin="o*AAQXy0evPfRGXRq-SkdfsWNCNGE4M4tBzaw8UPNauq8b8g3CLuM",
        jd_bind_time="2026-09-17 22:05:24",
        account="50001_jd"
    )
    result = call_update_member_data(args)
    print(f"[结果] {json.dumps(result, ensure_ascii=False)}")