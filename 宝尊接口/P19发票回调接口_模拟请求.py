r"""
模拟宝尊发票回调 P19 请求脚本(参考 RopHelper.PostRequest)
路由: POST {BASE_URL}?version=...&requestTime=...&methodName=...&sourceApp=...&interfaceType=1&sign=...
Body: AES 加密后的 XML 明文 (Content-Type: application/json)

签名规则: MD5( AppSecret + 排序后的 k1v1 + k2v2 + ... + body + AppSecret ) -> 大写16进制
字段顺序: interfaceType, methodName, requestTime, sourceApp, version (字典序)

加密: AES/CBC/PKCS7, IV 全 0
  key = UTF-8( Base64( MD5(AppSecret) ) )
"""

import base64
import hashlib
from datetime import datetime
from urllib.parse import quote

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

APP_SECRET = "N9sbXKr8GZMwXVaSRT6+VxI2H6qBW3K41kHoFvqPXlO4See/JCKt7L49qPL5BVZw6zSSGvA2gDPqFfn+BxeGDw=="
SOURCE_APP = "9d61afae42c548619e5528d7a024ef8d"
METHOD_NAME = "platform_invoice_notify"
INTERFACE_TYPE = "1"
VERSION = "1.0"
BASE_URL = "https://cust-q1.ezrpro.com/cust/burton/open/platform/oms"


def build_aes_key(app_secret: str) -> bytes:
    """生成 AES 密钥: MD5(AppSecret) -> Base64 字符串 -> UTF-8 字节。"""
    md5_digest = hashlib.md5(app_secret.encode("utf-8")).digest()
    base64_str = base64.b64encode(md5_digest).decode("utf-8")
    return base64_str.encode("utf-8")


def aes_encrypt(plain_text: str, key_bytes: bytes) -> str:
    """AES/CBC/PKCS7 加密,IV 全 0,无 BOM UTF-8 编码,返回 Base64 字符串。"""
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv=b"\x00" * 16)
    plain_bytes = plain_text.encode("utf-8")
    encrypted = cipher.encrypt(pad(plain_bytes, AES.block_size))
    return base64.b64encode(encrypted).decode("utf-8")


def build_signature(app_secret: str, sign_params: dict, body: str) -> str:
    """按 ROP 协议生成签名: MD5( AppSecret + 字典序 k1v1 + ... + body + AppSecret ) -> 大写。"""
    sorted_items = sorted(sign_params.items(), key=lambda item: item[0])
    sb_parts = [app_secret]
    for key, value in sorted_items:
        sb_parts.append(f"{key}{value}")
    sb_parts.append(body)
    sb_parts.append(app_secret)
    raw = "".join(sb_parts)
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest().upper()
    return digest


def build_invoice_xml() -> str:
    """构造 P19 开票回调 XML 明文(单条 invoiceInfo,双 invoiceItem)。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<invoiceInfos> <sourceMarkCode>MOFAN_INVOICE</sourceMarkCode> <invoiceInfo> <storeCode>BURTONSH01</storeCode> <platformSource>MOFAN</platformSource> <bsOrderCode>E0717958929726092450003</bsOrderCode> <customerOrderCode>E0717958929726092450003</customerOrderCode> <invoicePfOrderCode>50002</invoicePfOrderCode> <eInvoiceUrl>https://bztic-gs-files-sit.oss-cn-shanghai.aliyuncs.com/uat/ecs-oms4-ei-service/20260928/265890253/202609/BURTONSH01/E0717958929726092450003-HX166133517.pdf</eInvoiceUrl> <remark></remark> <payeeRegisterNo>14030119960616554255</payeeRegisterNo> <payeeName>测试公司4255</payeeName> <invoiceType>3</invoiceType> <invoiceTitle>刘良</invoiceTitle> <businessType>1</businessType> <taxPayerId></taxPayerId> <taxPayerAddress></taxPayerAddress> <taxPayerTel></taxPayerTel> <invoiceMakeType>0</invoiceMakeType> <invoiceAmount>1.10</invoiceAmount> <skuAmount>0.97</skuAmount> <tax>13.00</tax> <taxAmount>0.13</taxAmount> <invoiceCode>99912000000053662879</invoiceCode> <invoiceNo>99912000000053662879</invoiceNo> <drawer>开票人</drawer> <invoiceDate>2026-09-28 15:09:02</invoiceDate> <checkSum></checkSum> <payerPhone></payerPhone> <payerAddress></payerAddress> <payerBankAccount></payerBankAccount> <needLogistic>false</needLogistic> <receiver> <receiverPhone></receiverPhone> <receiverEmail></receiverEmail> <remark></remark> </receiver> <invoiceItems> <itemName>W RIDGE PANT TRUE BLACK</itemName> <itemNo>1040303020000000000</itemNo> <specification>23261100001</specification> <unit>件</unit> <quantity>11</quantity> <price>0.088182</price> <taxRate>0.13</taxRate> <tax>0.13</tax> <sumPrice>0.97</sumPrice> <amount>1.10</amount> <rowType>0</rowType> </invoiceItems> </invoiceInfo> </invoiceInfos>"""


def main() -> None:
    # 1. 构造 XML 明文
    xml_plain = build_invoice_xml()
    print("=== XML 明文 ===")
    print(xml_plain)
    print()

    # 2. AES 加密 body
    aes_key = build_aes_key(APP_SECRET)
    cipher_body = aes_encrypt(xml_plain, aes_key)
    print("=== 加密 body(Base64) ===")
    print(cipher_body)
    # 落盘密文,便于本地解密自验证
    with open("last_cipher.txt", "w", encoding="utf-8") as fp:
        fp.write(cipher_body)
    print()

    # 3. 生成签名
    request_time = datetime.now().strftime("%Y%m%d%H%M%S")
    sign_params = {
        "version": VERSION,
        "requestTime": request_time,
        "methodName": METHOD_NAME,
        "sourceApp": SOURCE_APP,
        "interfaceType": INTERFACE_TYPE,
    }
    sign = build_signature(APP_SECRET, sign_params, cipher_body)
    print(f"=== requestTime: {request_time} ===")
    print(f"=== sign: {sign} ===")
    print()

    # 4. 拼接 URL(参数 URL-encode)
    full_params = dict(sign_params)
    full_params["sign"] = sign
    query_string = "&".join(
        f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in full_params.items()
    )
    full_url = f"{BASE_URL}?{query_string}"
    print("=== 完整 URL ===")
    print(full_url)
    print()

    # 5. 发送请求
    headers = {
        "Accept": "application/json",
        "Content-Type": "text/plain;charset=UTF-8",
        "ezr-env-tag": "d6547",
        "ezr-brand-id": "7179",
        "Content-Length": str(len(cipher_body.encode("utf-8"))),
    }
    print("=== 发送请求 ===")
    resp = requests.post(full_url, data=cipher_body.encode("utf-8"), headers=headers, timeout=30)
    print(f"HTTP Status: {resp.status_code}")
    print(f"Response Headers: {dict(resp.headers)}")
    print(f"Response Body:\n{resp.text}")


if __name__ == "__main__":
    main()