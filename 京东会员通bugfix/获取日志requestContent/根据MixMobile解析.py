"""
读取 csv 中的 [brandId, requestContent] 字段
解析 requestContent 中的 MixPhone, 按 brandId 匹配密钥进行 AES-CBC 解密
将解密后的手机号回写到 csv 新列中
"""

import csv
import json
import urllib.parse

# 优先使用 cryptography(更现代), 缺失时回退到 pycryptodome
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.backends import default_backend
    _CRYPTO_BACKEND = "cryptography"
except ImportError:
    from Crypto.Cipher import AES  # noqa: F401
    from Crypto.Util.Padding import unpad  # noqa: F401
    _CRYPTO_BACKEND = "pycryptodome"

# 京东解密密钥配置(按 brandId 匹配 Key)
BRAND_MOBILE_ENCRYPT_KEY_LIST = [
    {"BrandId": 1106, "Key": "1cf013935fd05a88d90267213cd435ed"},
    {"BrandId": 3956, "Key": "24d2138851351de6c8f8c88908a26f03"},
    {"BrandId": 6827, "Key": "873b41546bbb6d17de7647c26201b825"},
    {"BrandId": 6794, "Key": "69dcf1cd2a868ebc95c1a23b975cac0d"},
    {"BrandId": 6012, "Key": "24d2138851351de6c8f8c88908a26f03"},
    {"BrandId": 184,  "Key": "545ac035e10a6710caf7330737541194"},
    {"BrandId": 6887, "Key": "1cf013935fd05a88d90267213cd435ed"},
    {"BrandId": 6973, "Key": "84c612a3c3e9e7fb18c9c9ea067b0c16"},
    {"BrandId": 280,  "Key": "1a0ab486966926ca4cca312ddf3b8d02"},
    {"BrandId": 6959, "Key": "df1177eb5c127412211bf7fba42078e9"},
    {"BrandId": 1012, "Key": "7d11419604a2c18c258e6f640631efc1"},
    {"BrandId": 5882, "Key": "31512778b2956946c879c049d592ae9e"},
    {"BrandId": 6930, "Key": "b425ca0b45800f7d3cbd656ae9903af8"},
    {"BrandId": 7099, "Key": "b87a9bbcc3c5129783a895bb386280ec"},
]

# AES-CBC 解密所需 IV(与 C# 一致)
JD_DECRYPT_IV = "popCrm0000000000"

# 源 csv 路径(全局变量, 按需修改)
SOURCE_CSV_PATH = r"D:\Github\py-proj\京东会员通bugfix\20260615-unionid\requestContent_2026-09-28.csv"
# 解密后输出 csv 路径(全局变量, 按需修改)
OUTPUT_CSV_PATH = r"D:\Github\py-proj\京东会员通bugfix\获取日志requestContent\requestContent_2026-09-28_decrypted.csv"


def get_decrypt_key(brand_id: int):
    """根据 brandId 获取解密密钥"""
    for item in BRAND_MOBILE_ENCRYPT_KEY_LIST:
        if item["BrandId"] == brand_id:
            return item["Key"]
    return None


def str_to_hex_byte(hex_string: str) -> bytes:
    """Hex 字符串转字节数组(对齐 C# 的 StrToHexByte)"""
    hex_string = hex_string.replace(" ", "")
    if len(hex_string) % 2 != 0:
        hex_string += " "
    return bytes.fromhex(hex_string)


def decrypt_mix_phone(encrypted_data: str, key_str: str) -> str:
    """AES-CBC + PKCS7 解密 MixPhone, 对齐 JdVipConnectionMatchVersionManager.Decrypt"""
    iv_bytes = JD_DECRYPT_IV.encode("utf-8")
    key_bytes = key_str.encode("utf-8")
    data_bytes = str_to_hex_byte(encrypted_data)

    if _CRYPTO_BACKEND == "cryptography":
        cipher = Cipher(
            algorithms.AES(key_bytes),
            modes.CBC(iv_bytes),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(data_bytes) + decryptor.finalize()

        # 去除 PKCS7 填充
        unpadder = padding.PKCS7(128).unpadder()
        decrypted = unpadder.update(decrypted) + unpadder.finalize()
    else:
        # pycryptodome 路径
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
        decrypted = cipher.decrypt(data_bytes)
        decrypted = unpad(decrypted, AES.block_size)

    return decrypted.decode("utf-8")


def extract_mix_phone(request_content: str):
    """从 requestContent 中提取 MixPhone 字段值"""
    # Args 是 URL 编码的 JSON, 先定位 Args=
    args_prefix = "Args="
    args_index = request_content.find(args_prefix)
    if args_index < 0:
        return None
    encoded_args = request_content[args_index + len(args_prefix):]
    # Args 值可能延伸到下一个 &, 但本样本里是末尾, 简单按 '&' 截断
    if "&" in encoded_args:
        encoded_args = encoded_args.split("&", 1)[0]
    decoded_args = urllib.parse.unquote(encoded_args)
    args_obj = json.loads(decoded_args)
    return args_obj.get("MixPhone")


def process_csv(input_path: str, output_path: str):
    """读取 csv, 解析并回写解密手机号"""
    with open(input_path, "r", encoding="utf-8-sig", newline="") as f_in, \
         open(output_path, "w", encoding="utf-8-sig", newline="") as f_out:
        reader = csv.DictReader(f_in)
        fieldnames = list(reader.fieldnames or [])
        new_column = "decryptMobileNo"
        if new_column not in fieldnames:
            fieldnames.append(new_column)
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        success_count = 0
        fail_count = 0
        for row in reader:
            brand_id_raw = row.get("brandId", "")
            request_content = row.get("requestContent", "")
            mobile_no = ""
            try:
                brand_id = int(brand_id_raw)
                key = get_decrypt_key(brand_id)
                if not key:
                    print(f"[WARN] brandId={brand_id} 未配置解密密钥, 跳过")
                    fail_count += 1
                else:
                    mix_phone = extract_mix_phone(request_content)
                    if not mix_phone:
                        print(f"[WARN] 未解析到 MixPhone, brandId={brand_id}")
                        fail_count += 1
                    else:
                        mobile_no = decrypt_mix_phone(mix_phone, key)
                        success_count += 1
            except Exception as e:
                print(f"[ERROR] 处理失败 brandId={brand_id_raw}: {e}")
                fail_count += 1

            row[new_column] = mobile_no
            writer.writerow(row)

    print(f"[INFO] 完成: 成功 {success_count} 条, 失败 {fail_count} 条")
    print(f"[INFO] 输出文件: {output_path}")


if __name__ == "__main__":
    process_csv(SOURCE_CSV_PATH, OUTPUT_CSV_PATH)