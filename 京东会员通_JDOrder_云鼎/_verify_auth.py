"""
临时: 用 16/24/32 字节 Key 分别加密,对比期望 AuthInfo。
不输出密钥字面值,只输出"哪种长度匹配"。
"""
import json
import base64
import importlib.util
import logging
from Crypto.Cipher import AES

logging.disable(logging.CRITICAL)
spec = importlib.util.spec_from_file_location("jd_target", "正向单列表接口.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def pkcs7_pad(data, block_size=16):
    n = block_size - len(data) % block_size
    return data + bytes([n] * n)


def aes_encrypt(plain_text, key_str, key_len):
    # 取 key_str 前 key_len 字节,不足则右填充 \0
    kb = key_str.encode("utf-8")[:key_len].ljust(key_len, b"\0")
    cipher = AES.new(kb, AES.MODE_ECB)
    return base64.b64encode(cipher.encrypt(pkcs7_pad(plain_text.encode("utf-8")))).decode("utf-8")


plain = json.dumps(
    {"appKey": mod.APP_KEY, "appSecret": mod.APP_SECRET,
     "accessToken": mod.ACCESS_TOKEN, "buId": mod.VENDER_ID},
    ensure_ascii=False,
)

expected = ("OwaNl033DeDqqXn3IEEZir77HotNS+moSCJ/ZhwKtCZtdA3zWDwINMYFRIupq7XyqD"
            "A1mpRqRctgl0RJkr4CbJxWhls8/C5M/t0o1lSfEkWFYT/9d1hHpM/xrbUOqYOLd5y"
            "B6+tiRvWsP95AJhYZ7o9HMi4WUnghBkLQES8b6ifvnm4Au3iGyp89G8qG51niolR"
            "vkrgUO962FcnteUUQaUo2/FJzs0BNwKMB7MCSF3Y=")

for kl in (16, 24, 32):
    out = aes_encrypt(plain, mod.AUTH_SECRET, kl)
    match = "✓ 匹配" if out == expected else "✗"
    print(f"Key 长度={kl:2d} 字节: {out[:40]}...{out[-20:]}  {match}")

print(f"\n明文 JSON 字节数: {len(plain.encode('utf-8'))}")
print(f"期望 base64 字节数: {len(base64.b64decode(expected))}")
