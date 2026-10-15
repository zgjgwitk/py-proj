"""验算: 期望 AuthInfo 解码字节数 + 明文 JSON 字节数"""
import json
import importlib.util
import logging
import base64

logging.disable(logging.CRITICAL)
spec = importlib.util.spec_from_file_location("jd_target", "正向单列表接口.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

expected = ("OwaNl033DeDqqXn3IEEZir77HotNS+moSCJ/ZhwKtCZtdA3zWDwINMYFRIupq7XyqD"
            "A1mpRqRctgl0RJkr4CbJxWhls8/C5M/t0o1lSfEkWFYT/9d1hHpM/xrbUOqYOLd5y"
            "B6+tiRvWsP95AJhYZ7o9HMi4WUnghBkLQES8b6ifvnm4Au3iGyp89G8qG51niolR"
            "vkrgUO962FcnteUUQaUo2/FJzs0BNwKMB7MCSF3Y=")

print(f"期望 base64 字符数: {len(expected)}")
print(f"期望 base64 解码字节数: {len(base64.b64decode(expected))}")
print(f"期望是否为 16 倍数: {len(base64.b64decode(expected)) % 16 == 0}")

# 重算明文 JSON 字节数
plain = json.dumps(
    {"appKey": mod.APP_KEY, "appSecret": mod.APP_SECRET,
     "accessToken": mod.ACCESS_TOKEN, "buId": mod.VENDER_ID},
    ensure_ascii=False,
)
plain_bytes = plain.encode("utf-8")
print(f"\n明文 JSON 字符数: {len(plain)}")
print(f"明文 JSON 字节数: {len(plain_bytes)}")
print(f"明文 PKCS7 填充后字节数: {(16 - len(plain_bytes) % 16) + len(plain_bytes)}")
print(f"\n明文内容: {plain}")
