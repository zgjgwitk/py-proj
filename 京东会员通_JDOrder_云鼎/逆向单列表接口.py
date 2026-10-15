r"""
需求: 实现一个http请求的py脚本, 请求京东云鼎逆向订单列表接口
netcore代码实现, 请参考 D:\.ezr-dev-code\京东会员通Omid订单切换(d6583)\code\ezr.oplatform.innerapi\EZR.OP.InnerApi.Bussiness\JDOrder\JdOmidYdManager.cs->RequestJdRtnOrder;

- authInfo 的生成方法: D:\.ezr-dev-code\京东会员通Omid订单切换(d6583)\code\ezr.oplatform.innerapi\EZR.OP.InnerApi.Bussiness\JDOrder\JdOrderAddManager.cs -> getAuthInfo;
  getAuthInfo的参数改成全局变量, 并且做下简化, 直接为值类型(目前先做全局变量占位值,我后面会补上), 不要保留对象
"""

import json
import logging
import time
import base64
import os
import requests
from typing import Optional
# ↓↓↓ 京东云鼎接口需要的应用配置在 jd_config.py 中修改
from jd_config import APP_KEY, APP_SECRET, BRAND_CONFIGS, AUTH_SECRET, get_jd_api_url, get_service_step

# ============================================================
# 全局变量(占位值,后续由用户补全)
# ============================================================

# 当前运行的品牌 ID(修改这里切换品牌)  <----- 运行前确认品牌, 可以根据需要切换
TARGET_BRAND_ID: int = 1149
TARGET_HOST_TYPE: str = "Test2" # Pro1:京东云鼎1.0, Test2:京东云鼎2.0测试, Pro2:京东云鼎2.0正式

# 请求参数(参考 RequestJdRtnOrder 入参)
START_DATE: str = "2026-10-01 00:00:00"        # 查询开始时间
END_DATE: str = "2026-10-02 00:00:00"          # 查询结束时间
PAGE_INDEX: int = 1                            # 页码(从 1 开始)
PAGE_SIZE: int = 10                            # 每页条数
# SERVICE_STEP 根据 TARGET_HOST_TYPE 动态确定: Pro1(云鼎1.0)="50", Test2/Pro2(云鼎2.0)="100"
RETURN_ORIGINAL_ORDER: str = "true"            # 返回关联的正向信息
CHANGE_UNION_ID: str = "true"                  # 关联单是否 pin 转 unionid

# HTTP 请求超时(秒)
HTTP_TIMEOUT: int = 10

# ============================================================
# 日志
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("JdOrder.GetRtnOrderList")

# 完整日志(无截断)输出到独立文件,每次请求覆盖
LOG_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ConsoleLog")
LOG_FILE_PATH: str = os.path.join(LOG_DIR, "testLogRtn.txt")
file_logger = logging.getLogger("JdOrder.GetRtnOrderList.File")
file_logger.setLevel(logging.INFO)
file_logger.propagate = False  # 不冒泡到 root,避免重复输出到控制台
file_logger.handlers.clear()    # 防止重复加载时叠加 handler


def _build_file_handler() -> logging.FileHandler:
    """构建覆盖式 FileHandler(每次新建实例前先清空文件)"""
    os.makedirs(LOG_DIR, exist_ok=True)
    # 先清空旧内容
    with open(LOG_FILE_PATH, "w", encoding="utf-8"):
        pass
    fh = logging.FileHandler(LOG_FILE_PATH, mode="w", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    return fh


# 启动时立即安装一次,保证异常路径也能产出文件
file_logger.addHandler(_build_file_handler())


# ============================================================
# AES 加解密(参考 AesHelper.AesEncrypt)
# ============================================================

def _pkcs7_pad(data: bytes, block_size: int = 16) -> bytes:
    """PKCS7 填充"""
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)


def aes_encrypt(plain_text: str, key: str) -> str:
    """
    AES ECB 加密 + Base64 编码。
    完全对齐 C# AesHelper.AesEncrypt:
        1) Key = SHA1(SHA1(UTF8(key))) 取前 16 字节
        2) Mode = ECB, Padding = PKCS7
        3) 输出 Base64
    :param plain_text: 待加密的明文
    :param key: 密钥明文(将被两次 SHA1 后取前 16 字节)
    :return: Base64 编码后的密文
    """
    try:
        from Crypto.Cipher import AES
        import hashlib
    except ImportError as e:
        raise ImportError("请先安装 pycryptodome: pip install pycryptodome") from e

    # 1. 派生 16 字节 Key: 两次 SHA1 嵌套, 取前 16 字节
    seed = key.encode("utf-8")
    inner = hashlib.sha1(seed).digest()
    key_bytes = hashlib.sha1(inner).digest()[:16]

    # 2. AES-128-ECB + PKCS7
    cipher = AES.new(key_bytes, AES.MODE_ECB)
    plain_bytes = _pkcs7_pad(plain_text.encode("utf-8"))
    encrypted = cipher.encrypt(plain_bytes)

    # 3. Base64
    return base64.b64encode(encrypted).decode("utf-8")


def get_auth_info(app_key: str, app_secret: str, access_token: str, bu_id: str) -> str:
    """
    生成云鼎授权信息 AuthInfo(对应 JdOrderAddManager.getAuthInfo)。
    将入参改为值类型全局变量传入,内部组装 JSON 后 AES 加密。
    """
    auth_json = {
        "appKey": app_key,
        "appSecret": app_secret,
        "accessToken": access_token,
        "buId": bu_id,
    }
    auth_info_str = aes_encrypt(json.dumps(auth_json, ensure_ascii=False), AUTH_SECRET)
    logger.info("生成 AuthInfo 成功(长度=%d)", len(auth_info_str))
    return auth_info_str


def load_brand_config(brand_id: int) -> tuple[int, str, str]:
    """
    根据品牌 ID 从全局配置表 BRAND_CONFIGS 中加载对应的品牌配置。
    :param brand_id: EZR 品牌 ID
    :return: (brand_id, access_token, vender_id)
    """
    if brand_id not in BRAND_CONFIGS:
        available = list(BRAND_CONFIGS.keys())
        raise ValueError(f"未找到品牌ID={brand_id}的配置, 可用品牌: {available}")
    access_token, vender_id = BRAND_CONFIGS[brand_id]
    logger.info("加载品牌配置成功 brand_id=%s access_token_len=%d vender_id=%s",
                brand_id, len(access_token), vender_id)
    return brand_id, access_token, vender_id


# ============================================================
# 业务请求(对应 JdOmidYdManager.RequestJdRtnOrder)
# ============================================================

def request_jd_rtn_order(
    brand_id: int,
    auth_info: str,
    start_date: str,
    end_date: str,
    page_index: int,
    page_size: int,
) -> Optional[dict]:
    """
    调用京东云鼎 GetRtnOrderList 获取逆向订单。
    对应 C# 实现:
        Dictionary<string,string> postData = new ...
        var resultData = new CommonHttpClient().DoPostByFrom<>(url, postData, timeout: 10);
    """
    # 根据 TARGET_HOST_TYPE 动态获取接口地址与 serviceStep(配置在 jd_config.py)
    request_url = get_jd_api_url(TARGET_HOST_TYPE, "GetRtnOrderList")
    service_step = get_service_step(TARGET_HOST_TYPE)

    post_data = {
        "AuthInfo": auth_info,
        "BrandId": str(brand_id),
        "startDate": start_date,
        "endDate": end_date,
        "pageIndex": str(page_index),
        "pageSize": str(page_size),
        "serviceStep": service_step,
        "returnOriginalOrder": RETURN_ORIGINAL_ORDER,
        "changeUnionId": CHANGE_UNION_ID,
    }

    logger.info(
        "请求京东云鼎逆向订单 品牌=%s 时间段=%s~%s 页=%s 每页=%s",
        brand_id, start_date, end_date, page_index, page_size,
    )
    logger.info("POST %s", request_url)
    logger.info("请求 body=%s", json.dumps(post_data, ensure_ascii=False)[:500])

    # 完整请求体写入文件(无截断)
    file_logger.info("请求京东云鼎逆向订单 品牌=%s 时间段=%s~%s 页=%s 每页=%s",
                     brand_id, start_date, end_date, page_index, page_size)
    file_logger.info("POST %s", request_url)
    file_logger.info("请求 body=%s", json.dumps(post_data, ensure_ascii=False))

    try:
        resp = requests.post(request_url, data=post_data, timeout=HTTP_TIMEOUT)
    except requests.RequestException as ex:
        logger.error("品牌:%s,调用云鼎拉取逆向订单-异常", brand_id, exc_info=ex)
        return None

    if resp.status_code != 200:
        logger.error("品牌:%s,云鼎响应 HTTP 状态码非 200: %s, 响应体:%s",
                     brand_id, resp.status_code, resp.text[:500])
        file_logger.error("品牌:%s,云鼎响应 HTTP 状态码非 200: %s, 响应体:%s",
                          brand_id, resp.status_code, resp.text)
        return None

    try:
        result = resp.json()
    except json.JSONDecodeError:
        logger.error("品牌:%s,云鼎响应非 JSON: %s", brand_id, resp.text[:500])
        file_logger.error("品牌:%s,云鼎响应非 JSON: %s", brand_id, resp.text)
        return None

    return result


# ============================================================
# 入口
# ============================================================

def main() -> None:
    """脚本入口: 组装 AuthInfo 后调用 GetRtnOrderList"""
    started = time.time()

    # 每次请求前清空并重建文件 handler,保证 testLogRtn.txt 为本次请求的完整日志(覆盖式)
    file_logger.handlers.clear()
    file_logger.addHandler(_build_file_handler())

    # 防御性校验:占位值未替换时直接退出
    placeholder_values = (APP_KEY, APP_SECRET)
    if any(v.startswith("PLACEHOLDER_") for v in placeholder_values):
        logger.warning(
            "检测到 getAuthInfo 的全局变量仍为占位值:%s, 请补全后再执行。",
            {k: v for k, v in zip(
                ("APP_KEY", "APP_SECRET"), placeholder_values)},
        )
        return

    # 1. 根据品牌 ID 加载对应配置
    brand_id, access_token, vender_id = load_brand_config(TARGET_BRAND_ID)

    # 2. 生成 AuthInfo
    auth_info = get_auth_info(
        app_key=APP_KEY,
        app_secret=APP_SECRET,
        access_token=access_token,
        bu_id=vender_id,
    )

    # 3. 调用京东云鼎 GetRtnOrderList
    result = request_jd_rtn_order(
        brand_id=brand_id,
        auth_info=auth_info,
        start_date=START_DATE,
        end_date=END_DATE,
        page_index=PAGE_INDEX,
        page_size=PAGE_SIZE,
    )

    if result is None:
        logger.error("品牌:%s,调用云鼎拉取逆向订单-失败,无有效响应", brand_id)
        return

    elapsed = time.time() - started
    response_text = json.dumps(result, ensure_ascii=False, indent=2)
    logger.info(
        "品牌:%s,调用云鼎拉取逆向订单-完成, 耗时=%.2fs, 响应=\n%s",
        brand_id, elapsed, response_text[:1000],
    )
    file_logger.info(
        "品牌:%s,调用云鼎拉取逆向订单-完成, 耗时=%.2fs, 响应=\n%s",
        brand_id, elapsed, response_text,
    )


if __name__ == "__main__":
    main()
