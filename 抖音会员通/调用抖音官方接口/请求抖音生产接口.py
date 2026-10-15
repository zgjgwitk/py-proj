#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
参考 D:\Code\InnerApi\EZR.InnerApiTest\Douyin\DouyinMemberTest.cs 实现请求抖音官方接口的功能
实现此测试用例中的所有方法

-- 执行程序,再命令输入此命令:
python 抖音会员通/调用抖音官方接口/请求抖音生产接口.py
"""

import hashlib
import hmac
import json
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except ImportError:  # 兜底:无 requests 时使用标准库
    import urllib.request
    import urllib.error
    _HAS_REQUESTS = False


# -----------------------------
# 全局执行配置(每次执行前手动修改)
# -----------------------------

# 当前要执行的方法(留空 = 全部依次执行,否则只执行指定的那个)
# 可选值:
#   1"get_access_token"                  -> 仅获取 access_token
#   2"get_douyin_order_detail"          -> 仅查询订单详情
#   3"get_douyin_order_list"            -> 仅查询订单列表
#   4"get_douyin_order_list_111"        -> 仅查询订单列表(分页)
#   5"get_douyin_return_order_detail"   -> 仅查询退单明细
#   6"find_order_in_list_poll"          -> 轮询列表直到命中目标订单
#   7"find_return_order_in_list_poll"   -> 轮询列表直到命中目标退单
#   "" 或 None                           -> 全部依次执行
CURRENT_ACTION: Optional[str] = "find_order_in_list_poll"

# -----------------------------
# 4. get_douyin_order_list_111
# -----------------------------
# 当前操作的 brandId(对应 DOUYIN_SETTINGS 中的 key)
CURRENT_BRAND_ID: int = 7135

# 要查询的订单 ID(用于 GetDouyinOrderDetail / GetDouyinOrderList111)
CURRENT_ORDER_ID: str = "6926680844642581736"
# 订单列表查询的起始时间(用于 GetDouyinOrderList / GetDouyinOrderList111)
CURRENT_LAST_END_DATE: datetime = datetime(2026, 4, 4)

# 退单 ID(用于 GetDouyinReturnOrderDetail,留空则按时间区间查询)
CURRENT_AFTER_SALE_ID: str = "147345526818070576"

# 分页页码(从 1 开始,用于 GetDouyinOrderList111)
CURRENT_PAGE_INDEX: int = 1

# 强制刷新 access_token(True=每次都重新拉,False=优先使用配置中的缓存)
CURRENT_FORCE_REFRESH_TOKEN: bool = False

# -----------------------------
# 6. find_order_in_list_poll 轮询查找订单
# -----------------------------
# 当前操作的 brandId(对应 DOUYIN_SETTINGS 中的 key)
CURRENT_BRAND_ID_6: int = 7135
# 轮询查找时的目标订单号(用于 find_order_in_list_poll)
CURRENT_TARGET_ORDER_ID_6: str = "6926680844642581736"

# 订单列表查询的起始时间(用于 find_order_in_list_poll)
CURRENT_LAST_END_DATE_6: datetime = datetime(2026, 8, 29, 0, 0, 0)
# 轮询查找时的时间窗口终点(用于 find_order_in_list_poll)
CURRENT_SEARCH_END_DATE_6: datetime = datetime(2026, 9, 21, 23, 59, 59)

# 单个时间窗口的天数(轮询时按此切片 from start 累加到 end)
CURRENT_SEARCH_WINDOW_DAYS_6: int = 1

# -----------------------------
# 7. find_return_order_in_list_poll 轮询查找退单
# -----------------------------
# 当前操作的 brandId(对应 DOUYIN_SETTINGS 中的 key)
CURRENT_BRAND_ID_7: int = 7135
# 轮询查找时的目标退单号(用于 find_return_order_in_list_poll)
CURRENT_TARGET_AFTER_SALE_ID_7: str = "147345526818070576"

# 退单列表查询的起始时间(用于 find_return_order_in_list_poll)
CURRENT_LAST_END_DATE_7: datetime = datetime(2026, 8, 29, 0, 0, 0)
# 轮询查找时的时间窗口终点(用于 find_return_order_in_list_poll)
CURRENT_SEARCH_END_DATE_7: datetime = datetime(2026, 9, 21, 23, 59, 59)

# 单个时间窗口的天数(轮询时按此切片 from start 累加到 end)
CURRENT_SEARCH_WINDOW_DAYS_7: int = 1



# -----------------------------
# 其他一些全局配置
# -----------------------------

# 东八区时区(抖音订单时间按北京时间)
TZ_BJ = timezone(timedelta(hours=8))

# 找到目标订单后,日志文件保存目录(相对当前工作目录)
CURRENT_LOG_DIR: str = r"D:\Github\py-proj\抖音会员通\调用抖音官方接口\logs"

# 控制台输出详细级别:
#   "silent"    -> 不打印接口返回的 JSON,只打印进度/命中/日志路径
#   "summary"   -> 打印摘要(默认):返回条数 / 关键字段 / 不打印完整 JSON
#   "full"      -> 完整打印接口返回的 JSON(等同于之前的全量输出)
CURRENT_VERBOSE: str = "summary"

# 仅当 CURRENT_VERBOSE == "full" 时生效:完整 JSON 单条最大打印字符数
CURRENT_FULL_PRINT_LIMIT: int = 4000

# 命中日志文件名前缀:订单轮询 vs 退单轮询,避免相互覆盖
FOUND_LOG_PREFIX_ORDER: str = "found"
FOUND_LOG_PREFIX_RETURN: str = "after_sale"


# -----------------------------
# 配置:品牌抖音店铺信息
# -----------------------------
# 订单列表默认 order_status 过滤值(逗号分隔字符串,如 "105,2,101,3,5")
DEFAULT_ORDER_STATUS: str = "105,2,101,3,5"


@dataclass
class DouyinShopSettings:
    """抖音店铺配置"""
    douyin_url: str        # ed_base_brand_crm_cfg.DouyinUrl
    app_key: str           # ed_base_brand_bytedance_cfg.AppKey
    app_secret: str        # ed_base_brand_bytedance_cfg.AppSecret
    shop_id: str           # ed_base_brand_bytedance_cfg.DouyinShopId
    access_token: str = "" # 在EZR.OP.InnerApi.ServerHost应用里面查询抖音的接口请求,会有access_token参数
    # 订单列表查询时使用的 order_status 过滤值
    # 留空时调用方按 brand_id 取 DOUYIN_SETTINGS[brand_id].order_status_filter
    # 仍为空则用全局 DEFAULT_ORDER_STATUS
    order_status_filter: str = DEFAULT_ORDER_STATUS


DOUYIN_SETTINGS: Dict[int, DouyinShopSettings] = {
    190: DouyinShopSettings(
        douyin_url="https://openapi-fxg.jinritemai.com",
        app_key="7148979446169470494",
        app_secret="586da46c-e64f-474b-996d-96854fc5bf4f",
        shop_id="19764997",
        access_token="2ms0v71qmv1lginp9aj6gx20002ydl3c-11",
    ),
    976: DouyinShopSettings(
        douyin_url="https://openapi-fxg.jinritemai.com",
        app_key="7562830598130157094",
        app_secret="4ea34290-54cc-456f-a629-baf42f6a5a9a",
        shop_id="178673160",
        access_token="2ms0v71qmv1lginp9aj6gx20002ydl3c-11",
    ),
    1149: DouyinShopSettings(
        douyin_url="https://dy.canadagoose.cn",
        app_key="7596136690915165742",
        app_secret="51a62346-10f3-4b5d-8fe3-199e7154c1a3",
        shop_id="168922479",
        access_token="",
    ),
    7036: DouyinShopSettings(
        douyin_url="https://openapi-fxg.jinritemai.com",
        app_key="7497064745401484863",
        app_secret="069ce6b7-3a61-41c3-b54a-19366c5929dc",
        shop_id="211280779",
        access_token="",
    ),
    7126: DouyinShopSettings(
        douyin_url="https://ezr.marius.vip",
        app_key="7445145796279879231",
        app_secret="c5d80ebc-b070-423a-8415-f83694fa62ba",
        shop_id="55863475",
        access_token="oof0xp0jtw1kkbvx5oh2b7j0000x9cj7-11",
    ),
    7135: DouyinShopSettings(
        douyin_url="https://dy.iphsleep.cn",
        app_key="7524250745286411816",
        app_secret="2a078e18-bf22-4762-9f2b-85cb1546abbd",
        shop_id="36205089", # [216288864, 36205089]
        access_token="clj0gwpd5p1l5ysa9kian8o0000lk00x-11",
        # 7135 仅支持 order_status=5
        order_status_filter="5",
    ),
}


# -----------------------------
# 公共工具方法
# -----------------------------
def get_timestamp_seconds() -> int:
    """获取当前秒级 Unix 时间戳"""
    return int(time.time())


def convert_datetime_to_long(dt: datetime) -> int:
    """
    将 DateTime 时间格式转换为 Unix 时间戳(秒)
    原 C# 逻辑:(time.ToUniversalTime().Ticks - 1970年Ticks) / 10000000
    抖音接口要求秒级时间戳
    """
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    utc_dt = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return int((utc_dt - epoch).total_seconds())


def hmac_sha256_hex(plain_text: str, app_secret: str) -> str:
    """计算 HMAC-SHA256 并以小写 hex 字符串返回"""
    h = hmac.new(app_secret.encode("utf-8"), plain_text.encode("utf-8"), hashlib.sha256)
    return h.hexdigest()


def sign(app_key: str, app_secret: str, method: str, timestamp: str, param_json: str) -> str:
    """
    计算抖音接口签名
    原 C# 实现:
        paramPattern = "app_key{appKey}method{method}param_json{paramJson}timestamp{timestamp}v2"
        signPattern = appSecret + paramPattern + appSecret
        return Hmac(signPattern, appSecret)
    """
    param_pattern = (
        f"app_key{app_key}"
        f"method{method}"
        f"param_json{param_json}"
        f"timestamp{timestamp}"
        "v2"
    )
    sign_pattern = app_secret + param_pattern + app_secret
    return hmac_sha256_hex(sign_pattern, app_secret)


def _object_sort(obj: Any, deep_sort_array: bool = False) -> Any:
    """
    递归按 key 排序字典(对象层级)
    深排序模式:对数组中的字典也进行排序(EzrObejctSort 行为)
    """
    if isinstance(obj, dict):
        return {k: _object_sort(obj[k], deep_sort_array) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [_object_sort(item, deep_sort_array) for item in obj]
    return obj


def marshal(obj: Any, is_ezr_push: bool = False) -> str:
    """
    序列化参数(保持 key 有序、数值不带多余小数点、转义逻辑一致)
    实现对应 C# 的 ObejctSort / EzrObejctSort + ToJson
    """
    raw = json.loads(json.dumps(obj, ensure_ascii=False))
    sorted_obj = _object_sort(raw, deep_sort_array=is_ezr_push)
    # ensure_ascii=False + 不允许多余空格,保证与 C# 序列化结果一致
    return json.dumps(sorted_obj, ensure_ascii=False, separators=(",", ":"))


# -----------------------------
# 请求 / 响应模型
# -----------------------------
@dataclass
class AccessTokenParamJson:
    """获取 access_token 入参"""
    code: str = ""
    grant_type: str = "authorization_self"
    shop_id: str = ""


@dataclass
class DouyinStatus:
    """订单状态组合"""
    main_status: Optional[str] = None
    order_status: Optional[str] = None


@dataclass
class DouyinReturnOrderRequest:
    """获取退单明细请求参数"""
    after_sale_id: Optional[str] = None
    standard_aftersale_status: Optional[List[int]] = None
    update_start_time: Optional[int] = None
    update_end_time: Optional[int] = None
    size: Optional[int] = None
    page: Optional[int] = None
    combine_status: Optional[List[DouyinStatus]] = None


@dataclass
class OrderGetListRequest:
    """获取订单列表请求参数"""
    update_time_start: Optional[int] = None
    update_time_end: Optional[int] = None
    size: Optional[int] = None
    page: Optional[int] = None
    b_type: int = 2  # 2=抖音
    combine_status: Optional[List[DouyinStatus]] = None


@dataclass
class DouyinOrderDetailRequest:
    """订单详情请求参数"""
    shop_order_id: str = ""


@dataclass
class DouyinRequestBase:
    """抖音请求基础结构"""
    app_key: str
    app_secret: str
    method: str
    param_json: Any
    timestamp: str = ""
    shop_id: str = ""
    v: str = "2"


# -----------------------------
# 抖音接口客户端
# -----------------------------
class DouyinClient:
    """抖音开放接口客户端(对应 C# 中的 IDouyinHttpClient 调用逻辑)"""

    def __init__(self, http_session: Optional["requests.Session"] = None, timeout: int = 30):
        self._timeout = timeout
        if _HAS_REQUESTS:
            self._session = http_session or requests.Session()
        else:
            self._session = http_session  # 仅为占位,实际走 _post_via_urllib

    def _post(self, url: str, body: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """统一 POST 入口,优先使用 requests,缺失时回退 urllib"""
        if _HAS_REQUESTS:
            resp = self._session.post(url, data=body, headers=headers, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()

        # urllib 兜底
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                payload = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:  # noqa: F821
            err_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"抖音接口 HTTP {exc.code}: {err_body}") from exc
        return json.loads(payload)

    # ---------------- access_token ----------------
    def get_access_token(
        self,
        app_key: str,
        app_secret: str,
        shop_id: str,
        brand_id: int = 0,
        is_get_new: bool = False,
    ) -> str:
        """
        调用抖音 token.create 接口获取 access_token

        Args:
            app_key:    抖音应用 AppKey
            app_secret: 抖音应用 AppSecret
            shop_id:    抖音店铺 ID
            brand_id:   品牌 ID(用于路由 DOUYIN_SETTINGS 取 douyin_url)
            is_get_new: True=强制调用接口刷新;False=优先使用 DOUYIN_SETTINGS[brand_id].access_token 缓存

        Returns:
            access_token 字符串

        Raises:
            RuntimeError: 接口返回 code != 10000 或响应无 data 时抛出
        """
        if not is_get_new and brand_id in DOUYIN_SETTINGS:
            cached = DOUYIN_SETTINGS[brand_id].access_token
            if cached:
                return cached

        ts = str(get_timestamp_seconds())
        param_json = marshal({
            "code": "",
            "grant_type": "authorization_self",
            "shop_id": shop_id,
        })

        url_str = DOUYIN_SETTINGS[brand_id].douyin_url if brand_id in DOUYIN_SETTINGS else ""
        url = (
            f"{url_str}/token/create?"
            f"app_key={urllib.parse.quote(app_key)}"
            f"&method={urllib.parse.quote('token.create')}"
            f"&param_json={urllib.parse.quote(param_json)}"
            f"&timestamp={urllib.parse.quote(ts)}"
            f"&v={urllib.parse.quote('2')}"
            f"&sign={urllib.parse.quote(sign(app_key, app_secret, 'token.create', ts, param_json))}"
            f"&sign_method={urllib.parse.quote('hmac-sha256')}"
        )

        headers = {"Accept": "*/*", "Content-Type": "application/json;charset=UTF-8"}
        body = self._post(url, param_json.encode("utf-8"), headers)
        if body.get("code") == 10000 and body.get("data"):
            access_token = body["data"].get("access_token", "")
            # 实际生产应写入缓存(CacheShardFactory.GetOPPCache),这里仅返回
            return access_token
        raise RuntimeError(f"获取抖音 access_token 失败: {body}")

    # ---------------- 通用执行 ----------------
    def do_execute(
        self,
        request: DouyinRequestBase,
        is_ezr_push: bool = False,
        brand_id: int = 0,
    ) -> Dict[str, Any]:
        """
        通用抖音开放接口请求(对应 C# DoExecuteAsync)

        自动完成:
          1. 生成秒级时间戳
          2. 序列化 param_json(默认按 key 字典序排序;is_ezr_push=True 时数组层也排序)
          3. 取/刷新 access_token
          4. 按 method(斜杠转点)拼接 URL,附带签名
          5. POST 请求,body 为 param_json 原文

        Args:
            request:    DouyinRequestBase 请求体(method / param_json / app_key / app_secret / shop_id)
            is_ezr_push: 是否走 EZR Push 模式(数组层字典也排序)
            brand_id:   品牌 ID(用于路由 douyin_url 与 access_token)

        Returns:
            接口响应 JSON 字典,通常含 code / data / msg / sub_code 等字段
        """
        request.timestamp = str(get_timestamp_seconds())
        param_json = marshal(request.param_json, is_ezr_push=is_ezr_push)

        access_token = self.get_access_token(
            app_key=request.app_key,
            app_secret=request.app_secret,
            shop_id=request.shop_id,
            brand_id=brand_id,
        )

        url_str = DOUYIN_SETTINGS[brand_id].douyin_url if brand_id in DOUYIN_SETTINGS else ""
        method_dot = request.method.replace("/", ".")
        url = (
            f"{url_str}/{request.method}?"
            f"method={urllib.parse.quote(method_dot)}"
            f"&app_key={urllib.parse.quote(request.app_key)}"
            f"&access_token={urllib.parse.quote(access_token)}"
            f"&param_json={urllib.parse.quote(param_json)}"
            f"&timestamp={urllib.parse.quote(request.timestamp)}"
            f"&v={urllib.parse.quote(request.v)}"
            f"&sign={urllib.parse.quote(sign(request.app_key, request.app_secret, method_dot, request.timestamp, param_json))}"
            f"&sign_method={urllib.parse.quote('hmac-sha256')}"
        )

        headers = {"Accept": "*/*", "Content-Type": "application/json;charset=UTF-8"}
        return self._post(url, param_json.encode("utf-8"), headers)

    # ---------------- 业务接口 ----------------
    def get_douyin_return_order_detail(
        self,
        app_key: str,
        app_secret: str,
        shop_id: str,
        last_end_date: int,
        brand_id: int = 0,
        after_sale_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        调用抖音 afterSale/Detail 接口获取退单明细

        Args:
            app_key:       抖音应用 AppKey
            app_secret:    抖音应用 AppSecret
            shop_id:       抖音店铺 ID
            last_end_date: 申请时间起始点(秒级时间戳)
            brand_id:      品牌 ID
            after_sale_id: 售后单 ID(可选;非空时与时间区间同时传给抖音)

        Returns:
            退单列表(跨页聚合结果)
        """
        all_orders: List[Dict[str, Any]] = []
        page = 1
        page_size = 50

        while True:
            request = DouyinRequestBase(
                app_key=app_key,
                app_secret=app_secret,
                method="afterSale/Detail",
                shop_id=shop_id,
                param_json={
                    "after_sale_id": after_sale_id,
                    "update_start_time": last_end_date,
                    "update_end_time": convert_datetime_to_long(datetime.now(TZ_BJ)),
                    "size": page_size,
                    "page": page - 1,  # 抖音接口 page 从 0 开始
                    "standard_aftersale_status": [12], # 12(售后关闭)
                },
            )
            response = self.do_execute(request, is_ezr_push=False, brand_id=brand_id)
            if response.get("code") != 10000:
                break

            data = response.get("data") or {}
            items = data.get("items") or []
            all_orders.extend(items)

            total = data.get("total", 0) or 0
            total_pages = total // page_size + (1 if total % page_size else 0)
            if page >= max(total_pages, 1):
                break
            page += 1

        return all_orders

    def get_douyin_return_order_list(
        self,
        app_key: str,
        app_secret: str,
        shop_id: str,
        last_end_date: int,
        brand_id: int = 0,
        end_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        对应 C# GetDouyinReturnOrderList，调用 afterSale/List 查询退款订单列表。

        接口 page 从 0 开始，方法内部自动按 total 分页聚合；请求失败或参数不完整时返回已获取的数据。
        """
        if not app_key or not app_secret or not shop_id:
            return []
        if end_time is None:
            end_time = convert_datetime_to_long(datetime.now(TZ_BJ))

        all_orders: List[Dict[str, Any]] = []
        page_size = 50
        page_count = 1
        page_index = 0

        while page_index < page_count:
            request = DouyinRequestBase(
                app_key=app_key,
                app_secret=app_secret,
                method="afterSale/List",
                shop_id=shop_id,
                param_json={
                    "update_start_time": last_end_date,
                    "update_end_time": end_time,
                    "size": page_size,
                    "page": page_index,
                    "standard_aftersale_status": [12], # 12(售后关闭)
                },
            )
            response = self.do_execute(request, is_ezr_push=False, brand_id=brand_id)
            if response.get("code") != 10000:
                break

            data = response.get("data") or {}
            items = data.get("items") or []
            if not items:
                break
            all_orders.extend(items)

            total = data.get("total", 0) or 0
            page_count = total // page_size + (1 if total % page_size else 0)
            page_index += 1

        return all_orders

    def get_douyin_order_detail(
        self,
        order_id: str,
        app_key: str,
        app_secret: str,
        shop_id: str,
        brand_id: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """根据抖音订单 ID 获取订单详情"""
        request = DouyinRequestBase(
            app_key=app_key,
            app_secret=app_secret,
            method="order/orderDetail",
            shop_id=shop_id,
            param_json={"shop_order_id": order_id},
        )
        response = self.do_execute(request, is_ezr_push=False, brand_id=brand_id)
        if not response.get("data"):
            return None
        return response["data"].get("shop_order_detail")

    def get_douyin_order_list(
        self,
        app_key: str,
        app_secret: str,
        shop_id: str,
        last_end_date: int,
        brand_id: int = 0,
        page: int = 1,
        end_time: Optional[int] = None,
        order_status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        调用抖音 order/searchList 接口,按时间区间与订单状态查询订单列表(单页)

        Args:
            app_key:       抖音应用 AppKey
            app_secret:    抖音应用 AppSecret
            shop_id:       抖音店铺 ID
            last_end_date: 订单修改起始时间(秒级时间戳,对应 update_time_start)
            brand_id:      品牌 ID
            page:          页码(从 1 开始,内部转为抖音要求的 0 基)
            end_time:      订单修改结束时间(秒级时间戳,对应 update_time_end);
                           None 时默认明天 0 点(北京时间)
            order_status:  combine_status 内的 order_status 过滤值;
                           None 时按 brand_id 自动解析
                           (7135 默认 "5",其它品牌默认 "105,2,101,3,5")

        Returns:
            当前页订单列表(shop_order_list);为空时返回 []
        """
        if end_time is None:
            end_time = convert_datetime_to_long(datetime.now(TZ_BJ) + timedelta(days=1))
        if order_status is None:
            settings = DOUYIN_SETTINGS.get(brand_id) if brand_id else None
            order_status = (
                settings.order_status_filter
                if settings is not None and settings.order_status_filter
                else DEFAULT_ORDER_STATUS
            )
        request = DouyinRequestBase(
            app_key=app_key,
            app_secret=app_secret,
            method="order/searchList",
            shop_id=shop_id,
            param_json={
                "update_time_start": last_end_date,
                "update_time_end": end_time,
                "size": 50,
                "page": page,
                "b_type": 2,
                "combine_status": [{"order_status": order_status}],
            },
        )
        response = self.do_execute(request, is_ezr_push=False, brand_id=brand_id)
        data = response.get("data") or {}
        return data.get("shop_order_list") or []


# -----------------------------
# 测试用例方法(对应 C# Fact)
# -----------------------------
def douyin_point_deduction_ignore_open_id_test() -> bool:
    """
    对应 C# Douyin_PointDeduction_IgnoreOpenIdTest
    模拟从配置中心(Apollo)读取积分扣减时需要忽略的 OpenID 列表,
    判断指定 OpenID("aaa")是否在忽略列表中。
    真实生产应通过 Apollo/配置中心获取 ignore_open_ids。
    """
    ignore_open_ids: List[str] = []
    return "aaa" in ignore_open_ids


def get_access_token(
    brand_id: int = CURRENT_BRAND_ID,
    is_get_new: bool = CURRENT_FORCE_REFRESH_TOKEN,
) -> str:
    """
    对应 C# GetAccessToken 单元测试方法
    根据 brand_id 取 DOUYIN_SETTINGS 配置,调用 DouyinClient.get_access_token
    """
    settings = DOUYIN_SETTINGS[brand_id]
    client = DouyinClient()
    return client.get_access_token(
        app_key=settings.app_key,
        app_secret=settings.app_secret,
        shop_id=settings.shop_id,
        brand_id=brand_id,
        is_get_new=is_get_new,
    )


def get_douyin_return_order_detail(
    brand_id: int = CURRENT_BRAND_ID,
    after_sale_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    对应 C# GetDouyinReturnOrderDetail
    以当前时间为 update_end_time,DEFAULT_AFTER_SALE_ID 为 after_sale_id 查询退单
    """
    settings = DOUYIN_SETTINGS[brand_id]
    client = DouyinClient()
    return client.get_douyin_return_order_detail(
        app_key=settings.app_key,
        app_secret=settings.app_secret,
        shop_id=settings.shop_id,
        last_end_date=convert_datetime_to_long(datetime.now(TZ_BJ)),
        brand_id=brand_id,
        after_sale_id=after_sale_id or CURRENT_AFTER_SALE_ID,
    )


def get_douyin_return_order_list(
    brand_id: int = CURRENT_BRAND_ID,
    last_end_date: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    对应 C# GetDouyinReturnOrderList，按更新时间查询并聚合全部退款订单。
    """
    if last_end_date is None:
        last_end_date = CURRENT_LAST_END_DATE
    settings = DOUYIN_SETTINGS[brand_id]
    client = DouyinClient()
    start_time = (
        last_end_date.replace(tzinfo=TZ_BJ)
        if last_end_date.tzinfo is None
        else last_end_date
    )
    return client.get_douyin_return_order_list(
        app_key=settings.app_key,
        app_secret=settings.app_secret,
        shop_id=settings.shop_id,
        last_end_date=convert_datetime_to_long(start_time),
        brand_id=brand_id,
    )


def get_douyin_order_detail(
    brand_id: int = CURRENT_BRAND_ID,
    order_id: str = CURRENT_ORDER_ID,
) -> Optional[Dict[str, Any]]:
    """
    对应 C# GetDouyinOrderDetail
    根据抖音店铺订单 ID 查询单个订单详情,返回 shop_order_detail 对象(无则返回 None)
    """
    settings = DOUYIN_SETTINGS[brand_id]
    client = DouyinClient()
    return client.get_douyin_order_detail(
        order_id=order_id,
        app_key=settings.app_key,
        app_secret=settings.app_secret,
        shop_id=settings.shop_id,
        brand_id=brand_id,
    )


def get_douyin_order_list(
    brand_id: int = CURRENT_BRAND_ID,
    last_end_date: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    对应 C# GetDouyinOrderList
    按 CURRENT_LAST_END_DATE 为起点查订单列表(单页 50 条)
    """
    if last_end_date is None:
        last_end_date = CURRENT_LAST_END_DATE
    settings = DOUYIN_SETTINGS[brand_id]
    client = DouyinClient()
    return client.get_douyin_order_list(
        app_key=settings.app_key,
        app_secret=settings.app_secret,
        shop_id=settings.shop_id,
        last_end_date=convert_datetime_to_long(last_end_date.replace(tzinfo=TZ_BJ)),
        brand_id=brand_id,
    )


def get_douyin_order_list_111(
    brand_id: int = CURRENT_BRAND_ID,
    last_end_date: Optional[datetime] = None,
    page_index: int = CURRENT_PAGE_INDEX,
) -> List[Dict[str, Any]]:
    """
    对应 C# GetDouyinOrderList111
    单页请求(按 CURRENT_PAGE_INDEX),请求完休眠 3 秒防抖音限流
    """
    if last_end_date is None:
        last_end_date = CURRENT_LAST_END_DATE
    settings = DOUYIN_SETTINGS[brand_id]
    client = DouyinClient()
    data = client.get_douyin_order_list(
        app_key=settings.app_key,
        app_secret=settings.app_secret,
        shop_id=settings.shop_id,
        last_end_date=convert_datetime_to_long(last_end_date.replace(tzinfo=TZ_BJ)),
        brand_id=brand_id,
        page=page_index,
    )
    # 每次分页间隔 3 秒,避免触发抖音限流
    time.sleep(3)
    return data


def find_order_in_list_poll(
    brand_id: int = CURRENT_BRAND_ID_6,
    target_order_id: str = CURRENT_TARGET_ORDER_ID_6,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    window_days: int = CURRENT_SEARCH_WINDOW_DAYS_6,
    log_dir: str = CURRENT_LOG_DIR,
) -> Optional[Dict[str, Any]]:
    """
    按时间窗口轮询订单列表,直到命中 target_order_id

    Args:
        brand_id:        品牌 ID
        target_order_id: 要查找的目标店铺订单号
        start_date:      查询起点;None 时取 CURRENT_LAST_END_DATE_6
        end_date:        查询终点;None 时取 CURRENT_SEARCH_END_DATE_6
        window_days:     单个时间窗口的天数,None 时取 CURRENT_SEARCH_WINDOW_DAYS_6
        log_dir:         命中后写入日志的目录;None 时取 CURRENT_LOG_DIR

    Returns:
        命中的订单对象(dict);遍历全部窗口仍未命中则返回 None

    流程:
      1. 从 start_date 起按 window_days 切片,逐步推进到 end_date
      2. 每个窗口内按 page=0,1,2...翻页查询(每页 50 条,
         翻页之间 sleep 3s 防限流,窗口之间 sleep 1s)
      3. 命中目标订单号(order_id 顶层字段)即停,
         并把本次请求参数 + 命中订单信息写到 log_dir/found_{订单号}_{ts}.json
    """
    if start_date is None:
        start_date = CURRENT_LAST_END_DATE_6
    if end_date is None:
        end_date = CURRENT_SEARCH_END_DATE_6

    if not target_order_id:
        raise ValueError("target_order_id 不能为空")

    settings = DOUYIN_SETTINGS[brand_id]
    client = DouyinClient()
    # 直接读取店铺配置;若为空则走全局 DEFAULT_ORDER_STATUS
    order_status = settings.order_status_filter or DEFAULT_ORDER_STATUS

    # 时区归一化(均为北京时间)
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=TZ_BJ)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=TZ_BJ)

    total_span = end_date - start_date
    total_windows = max(1, (total_span.days + window_days - 1) // window_days)
    print(f"[开始] 目标订单={target_order_id} 品牌={brand_id}", flush=True)
    print(f"[区间] {start_date} -> {end_date} (共 {total_span.days} 天, 预计 {total_windows} 个窗口, 窗口大小={window_days} 天)", flush=True)
    print(f"[店铺] {settings.douyin_url}  shop_id={settings.shop_id}  order_status='{order_status}'", flush=True)
    print("-" * 60, flush=True)

    window = timedelta(days=window_days)
    cursor = start_date
    window_index = 0
    t_start = time.time()

    while cursor < end_date:
        window_index += 1
        window_end = min(cursor + window, end_date)
        window_start_ts = convert_datetime_to_long(cursor)
        window_end_ts = convert_datetime_to_long(window_end)
        elapsed = int(time.time() - t_start)
        print(
            f"[窗口 {window_index}/{total_windows}] {cursor} -> {window_end}  "
            f"start_ts={window_start_ts}  end_ts={window_end_ts}  "
            f"已耗时={elapsed}s",
            flush=True,
        )

        page = 0
        page_count = 0
        while True:
            page_t0 = time.time()
            print(
                f"  └─ 请求 page={page} ... ",
                end="",
                flush=True,
            )
            try:
                order_list = client.get_douyin_order_list(
                    app_key=settings.app_key,
                    app_secret=settings.app_secret,
                    shop_id=settings.shop_id,
                    last_end_date=window_start_ts,
                    end_time=window_end_ts,
                    brand_id=brand_id,
                    page=page,
                    order_status=order_status,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"异常: {exc!r}", flush=True)
                break

            # 防御性编程:接口异常时跳过本窗口
            if order_list is None:
                print("返回空,跳过本窗口", flush=True)
                break

            page_count += 1
            page_cost_ms = int((time.time() - page_t0) * 1000)
            print(
                f"返回 {len(order_list)} 条, 耗时 {page_cost_ms}ms",
                flush=True,
            )

            for idx, item in enumerate(order_list):
                # 抖音订单列表接口字段约定:
                #   顶层:order_id(店铺订单号)、shop_id
                #   嵌套:sku_order_list[].order_id / parent_order_id / master_sku_order_id
                # 详情接口字段:shop_order_id(防御性兜底,列表接口通常不存在)
                # 命中条件:任一字段与目标订单号相等
                candidate_ids = _extract_candidate_order_ids(item)
                if str(target_order_id) in candidate_ids:
                    print(
                        f"  ✓ 在 page={page} 第 {idx} 条命中订单 {target_order_id} (匹配字段: {candidate_ids[str(target_order_id)]})",
                        flush=True,
                    )
                    _save_found_log(
                        log_dir=log_dir,
                        target_order_id=target_order_id,
                        window_start=cursor,
                        window_end=window_end,
                        page=page,
                        request_params={
                            "update_time_start": window_start_ts,
                            "update_time_end": window_end_ts,
                            "size": 50,
                            "page": page,
                            "b_type": 2,
                            "combine_status": [{"order_status": order_status}],
                        },
                        brand_id=brand_id,
                        matched_order=item,
                        file_prefix=FOUND_LOG_PREFIX_ORDER,
                    )
                    total_cost = int(time.time() - t_start)
                    print(f"[完成] 总耗时 {total_cost}s", flush=True)
                    return item

            # 本页没命中,翻页
            if len(order_list) < 50:
                # 不足一页说明本窗口已无更多
                print(f"  · 本窗口已无更多数据 (累计 {page_count} 页)", flush=True)
                break
            page += 1
            print(f"  · 本页未命中,翻到 page={page}, 等待 3s 防限流 ...", flush=True)
            time.sleep(3)  # 防限流

        # 进入下一个窗口前,提示一下避免以为卡死
        progress_pct = min(100, int(window_index / total_windows * 100))
        print(f"[进度] {progress_pct}%  ({window_index}/{total_windows})", flush=True)
        cursor = window_end
        time.sleep(1)

    total_cost = int(time.time() - t_start)
    print("-" * 60, flush=True)
    print(f"[结束] 在 {start_date} ~ {end_date} 区间未找到订单 {target_order_id}  总耗时 {total_cost}s", flush=True)
    return None


def _extract_candidate_order_ids(item: Dict[str, Any]) -> Dict[str, str]:
    """
    从订单列表项的顶层字段中提取订单号,返回 {订单号: 来源字段} 的映射。

    抖音订单列表接口(order/searchList)响应顶层字段:
      - order_id        店铺订单号(实际接口使用此字段)

    Args:
        item: shop_order_list 中的单个订单字典

    Returns:
        {订单号字符串: 来源字段名};空字符串和 None 会被忽略
    """
    candidates: Dict[str, str] = {}

    def _put(value: Any, source: str) -> None:
        if value is None:
            return
        s = str(value).strip()
        if s and s not in candidates:
            candidates[s] = source

    # 仅取顶层字段
    _put(item.get("order_id"), "order_id")

    return candidates


def _extract_candidate_after_sale_ids(item: Dict[str, Any]) -> Dict[str, str]:
    """
    从退单列表项的顶层字段中提取退单号,返回 {退单号: 来源字段} 的映射。

    抖音退单列表接口(afterSale/List)响应顶层字段:
      - after_sale_id  售后单号(实际接口使用此字段)

    Args:
        item: items 中的单个退单字典

    Returns:
        {退单号字符串: 来源字段名};空字符串和 None 会被忽略
    """
    candidates: Dict[str, str] = {}

    def _put(value: Any, source: str) -> None:
        if value is None:
            return
        s = str(value).strip()
        if s and s not in candidates:
            candidates[s] = source

    # 仅取顶层字段(退单号统一以 after_sale_id 标识)
    _put(item.get("after_sale_id"), "after_sale_id")

    return candidates


def find_return_order_in_list_poll(
    brand_id: int = CURRENT_BRAND_ID_7,
    target_after_sale_id: str = CURRENT_TARGET_AFTER_SALE_ID_7,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    window_days: int = CURRENT_SEARCH_WINDOW_DAYS_7,
    log_dir: str = CURRENT_LOG_DIR,
) -> Optional[Dict[str, Any]]:
    """
    按时间窗口轮询退单列表,直到命中 target_after_sale_id
    与 find_order_in_list_poll 对称,但:
      - 数据源: get_douyin_return_order_list(afterSale/List)
      - 命中字段: 顶层 after_sale_id
      - 日志文件名前缀: after_sale_{id}_{ts}.json(与订单轮询相互区分)

    Args:
        brand_id:               品牌 ID
        target_after_sale_id:   要查找的目标退单号
        start_date:             查询起点;None 时取 CURRENT_LAST_END_DATE_7
        end_date:               查询终点;None 时取 CURRENT_SEARCH_END_DATE_7
        window_days:            单个时间窗口的天数;None 时取 CURRENT_SEARCH_WINDOW_DAYS_7
        log_dir:                命中后写入日志的目录;None 时取 CURRENT_LOG_DIR

    Returns:
        命中的退单对象(dict);遍历全部窗口仍未命中则返回 None

    流程:
      1. 从 start_date 起按 window_days 切片,逐步推进到 end_date
      2. 每个窗口内按 page=0,1,2...翻页查询(内部 get_douyin_return_order_list
         已按 total 自动翻页聚合,这里再次切片主要是为了 sleep 防限流 + 命中即时返回)
      3. 命中目标退单号(顶层 after_sale_id)即停,
         并把本次请求参数 + 命中退单信息写到 log_dir/after_sale_{id}_{ts}.json
    """
    if start_date is None:
        start_date = CURRENT_LAST_END_DATE_7
    if end_date is None:
        end_date = CURRENT_SEARCH_END_DATE_7

    if not target_after_sale_id:
        raise ValueError("target_after_sale_id 不能为空")

    settings = DOUYIN_SETTINGS[brand_id]
    client = DouyinClient()

    # 时区归一化(均为北京时间)
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=TZ_BJ)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=TZ_BJ)

    total_span = end_date - start_date
    total_windows = max(1, (total_span.days + window_days - 1) // window_days)
    print(f"[开始] 目标退单={target_after_sale_id} 品牌={brand_id}", flush=True)
    print(f"[区间] {start_date} -> {end_date} (共 {total_span.days} 天, 预计 {total_windows} 个窗口, 窗口大小={window_days} 天)", flush=True)
    print(f"[店铺] {settings.douyin_url}  shop_id={settings.shop_id}", flush=True)
    print("-" * 60, flush=True)

    window = timedelta(days=window_days)
    cursor = start_date
    window_index = 0
    t_start = time.time()

    while cursor < end_date:
        window_index += 1
        window_end = min(cursor + window, end_date)
        window_start_ts = convert_datetime_to_long(cursor)
        window_end_ts = convert_datetime_to_long(window_end)
        elapsed = int(time.time() - t_start)
        print(
            f"[窗口 {window_index}/{total_windows}] {cursor} -> {window_end}  "
            f"start_ts={window_start_ts}  end_ts={window_end_ts}  "
            f"已耗时={elapsed}s",
            flush=True,
        )

        # get_douyin_return_order_list 内部已按 total 自动翻页聚合整窗口,
        # 这里直接拿到本窗口的全部退单,再用字段提取判断命中后立即返回
        try:
            return_orders = client.get_douyin_return_order_list(
                app_key=settings.app_key,
                app_secret=settings.app_secret,
                shop_id=settings.shop_id,
                last_end_date=window_start_ts,
                end_time=window_end_ts,
                brand_id=brand_id,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"异常: {exc!r}", flush=True)
            cursor = window_end
            time.sleep(1)
            continue

        # 防御性编程:接口异常/返回为空时跳过本窗口
        if not return_orders:
            print("  · 本窗口无退单数据,跳过", flush=True)
            cursor = window_end
            time.sleep(1)
            continue

        print(f"  · 本窗口共 {len(return_orders)} 条退单,逐条匹配 ...", flush=True)
        for idx, item in enumerate(return_orders):
            # 抖音退单列表接口字段约定:
            #   顶层:after_sale_id(售后单号)、shop_id
            # 命中条件:after_sale_id 与目标退单号相等
            candidate_ids = _extract_candidate_after_sale_ids(item)
            if str(target_after_sale_id) in candidate_ids:
                print(
                    f"  ✓ 在第 {idx} 条命中退单 {target_after_sale_id} (匹配字段: {candidate_ids[str(target_after_sale_id)]})",
                    flush=True,
                )
                _save_found_log(
                    log_dir=log_dir,
                    target_order_id=target_after_sale_id,
                    window_start=cursor,
                    window_end=window_end,
                    page=0,
                    request_params={
                        "update_start_time": window_start_ts,
                        "update_end_time": window_end_ts,
                        "standard_aftersale_status": [12],
                    },
                    brand_id=brand_id,
                    matched_order=item,
                    file_prefix=FOUND_LOG_PREFIX_RETURN,
                )
                total_cost = int(time.time() - t_start)
                print(f"[完成] 总耗时 {total_cost}s", flush=True)
                return item

        # 进入下一个窗口前,提示一下避免以为卡死
        progress_pct = min(100, int(window_index / total_windows * 100))
        print(f"[进度] {progress_pct}%  ({window_index}/{total_windows})", flush=True)
        cursor = window_end
        time.sleep(1)

    total_cost = int(time.time() - t_start)
    print("-" * 60, flush=True)
    print(f"[结束] 在 {start_date} ~ {end_date} 区间未找到退单 {target_after_sale_id}  总耗时 {total_cost}s", flush=True)
    return None


def _save_found_log(
    log_dir: str,
    target_order_id: str,
    window_start: datetime,
    window_end: datetime,
    page: int,
    request_params: Dict[str, Any],
    brand_id: int,
    matched_order: Dict[str, Any],
    file_prefix: str = FOUND_LOG_PREFIX_ORDER,
) -> str:
    """
    将 find_*_in_list_poll 命中时刻的请求参数与命中对象信息写入本地 JSON 文件。

    Args:
        log_dir:          日志输出目录(不存在会自动创建)
        target_order_id:  目标订单号/退单号(写入文件名)
        window_start:     命中窗口的起始时间
        window_end:       命中窗口的结束时间
        page:             命中时的页码
        request_params:   实际请求抖音接口时使用的参数(快照)
        brand_id:         品牌 ID
        matched_order:    抖音接口返回的命中对象
        file_prefix:      日志文件名前缀;默认 FOUND_LOG_PREFIX_ORDER (= "found"),
                          退单轮询传入 FOUND_LOG_PREFIX_RETURN (= "after_sale")

    Returns:
        写入文件的绝对路径
    """
    import os
    os.makedirs(log_dir, exist_ok=True)
    file_path = os.path.join(
        log_dir,
        f"{file_prefix}_{target_order_id}_{int(time.time())}.json",
    )
    payload = {
        "target_order_id": target_order_id,
        "brand_id": brand_id,
        "found_at": datetime.now(TZ_BJ).isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "page": page,
        "request_params": request_params,
        "matched_order": matched_order,
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"  · 命中日志已写入: {file_path}")
    return file_path


def _print_result(label: str, result: Any) -> None:
    """
    按 CURRENT_VERBOSE 级别打印接口结果

    Args:
        label:  步骤中文标签,如 "订单详情" / "订单列表" / "access_token"
        result: 接口返回的数据(dict / list / str / None)

    行为:
        CURRENT_VERBOSE == "silent"  -> 仅打印"[{label}] 已返回数据(verbose=silent,不打印内容)"
        CURRENT_VERBOSE == "summary" -> 打印类型、条数、关键字段(order_id / order_status / code / msg / total)
                                         字符串超过 80 字符时按 "{前8}***{后4} (长度 N, 已脱敏)" 形式输出,token 不会完整泄露
        CURRENT_VERBOSE == "full"    -> 完整 JSON,超出 CURRENT_FULL_PRINT_LIMIT 自动截断
    """
    mode = (CURRENT_VERBOSE or "summary").lower()

    if result is None:
        print(f"[{label}] (空结果)", flush=True)
        return

    if mode == "silent":
        print(f"[{label}] 已返回数据(verbose=silent,不打印内容)", flush=True)
        return

    if isinstance(result, list):
        if mode == "summary":
            print(f"[{label}] 共 {len(result)} 条", flush=True)
            if result:
                first = result[0]
                if isinstance(first, dict):
                    keys = list(first.keys())[:6]
                    print(f"  · 首条字段(前6个): {keys}", flush=True)
                    sample = {k: first.get(k) for k in keys}
                    print(f"  · 首条预览: {json.dumps(sample, ensure_ascii=False)}", flush=True)
        else:  # full
            text = json.dumps(result, ensure_ascii=False, indent=2)
            if len(text) > CURRENT_FULL_PRINT_LIMIT:
                text = text[:CURRENT_FULL_PRINT_LIMIT] + f"\n... (已截断,总长 {len(text)} 字符)"
            print(text, flush=True)
        return

    if isinstance(result, dict):
        if mode == "summary":
            keys = list(result.keys())
            print(f"[{label}] 字典 {len(keys)} 个字段: {keys[:8]}{'...' if len(keys) > 8 else ''}", flush=True)
            # 关键字段摘要
            for k in ("order_id", "shop_order_id", "order_status", "code", "msg", "total"):
                if k in result:
                    print(f"  · {k} = {result[k]}", flush=True)
        else:
            text = json.dumps(result, ensure_ascii=False, indent=2)
            if len(text) > CURRENT_FULL_PRINT_LIMIT:
                text = text[:CURRENT_FULL_PRINT_LIMIT] + f"\n... (已截断,总长 {len(text)} 字符)"
            print(text, flush=True)
        return

    # 其它类型(str/token 等)
    s = str(result)
    if mode == "summary" and len(s) > 80:
        print(f"[{label}] {s[:8]}***{s[-4:]} (长度 {len(s)}, 已脱敏)", flush=True)
    else:
        print(f"[{label}] {s}", flush=True)


# -----------------------------
# 入口
# -----------------------------
if __name__ == "__main__":
    # 按顶部全局配置执行,执行前请手动修改 CURRENT_* 配置项
    if CURRENT_BRAND_ID not in DOUYIN_SETTINGS:
        raise KeyError(
            f"CURRENT_BRAND_ID={CURRENT_BRAND_ID} 不在 DOUYIN_SETTINGS 中,可选: {list(DOUYIN_SETTINGS.keys())}"
        )

    settings = DOUYIN_SETTINGS[CURRENT_BRAND_ID]
    print(f"当前品牌: {CURRENT_BRAND_ID} ({settings.douyin_url})")
    print(f"目标订单: {CURRENT_ORDER_ID or '(未填)'}")
    print(f"起始时间: {CURRENT_LAST_END_DATE}")
    print(f"刷新Token: {CURRENT_FORCE_REFRESH_TOKEN}")
    print(f"执行方法: {CURRENT_ACTION or '(全部依次执行)'}")
    print(f"输出级别: {CURRENT_VERBOSE}\n")

    # 方法路由:留空则按顺序执行全部,否则只执行指定方法
    ACTION_MAP = {
        "get_access_token": ("获取 access_token", get_access_token),
        "get_douyin_order_detail": ("查询订单详情", get_douyin_order_detail),
        "get_douyin_order_list": ("查询订单列表", get_douyin_order_list),
        "get_douyin_order_list_111": ("查询订单列表-分页", get_douyin_order_list_111),
        "get_douyin_return_order_detail": ("查询退单明细", get_douyin_return_order_detail),
        "find_order_in_list_poll": ("轮询列表查找订单", find_order_in_list_poll),
        "find_return_order_in_list_poll": ("轮询列表查找退单", find_return_order_in_list_poll),
    }

    if CURRENT_ACTION:
        # 单方法模式
        action = ACTION_MAP.get(CURRENT_ACTION)
        if action is None:
            raise ValueError(
                f"CURRENT_ACTION={CURRENT_ACTION!r} 不合法,可选: {list(ACTION_MAP.keys())} 或留空"
            )
        print(f"[执行] {action[0]} ...", flush=True)
        result = action[1]()
        _print_result(action[0], result)
    else:
        # 全量模式:按顺序执行
        print("[1] 获取 access_token ...", flush=True)
        token = get_access_token()
        _print_result("access_token", token)
        print()

        print("[2] 查询订单详情 ...", flush=True)
        detail = get_douyin_order_detail()
        _print_result("订单详情", detail)
        print()

        print("[3] 查询订单列表 ...", flush=True)
        order_list = get_douyin_order_list()
        _print_result("订单列表", order_list)
        print()

        print(f"[4] 查询订单列表-分页 page={CURRENT_PAGE_INDEX} ...", flush=True)
        page_list = get_douyin_order_list_111()
        _print_result("订单列表-分页", page_list)
        print()

        print(f"[5] 查询退单明细 after_sale_id={CURRENT_AFTER_SALE_ID} ...", flush=True)
        return_orders = get_douyin_return_order_detail()
        _print_result("退单明细", return_orders)
        print()

        print(f"[6] 轮询列表查找订单 {CURRENT_TARGET_ORDER_ID} ...", flush=True)
        found = find_order_in_list_poll()
        _print_result("轮询结果", found)
        print()

        print(f"[7] 轮询列表查找退单 {CURRENT_TARGET_AFTER_SALE_ID} ...", flush=True)
        return_found = find_return_order_in_list_poll()
        _print_result("退单轮询结果", return_found)

