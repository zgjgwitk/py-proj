# -*- coding: utf-8 -*-
import hashlib
from typing import Dict, Any

class MeituanSigner:
    """
    美团接口签名计算器
    参考文档: https://tscc.meituan.com/home/guide/market/10683
    """
    
    def __init__(self, app_secret: str):
        """
        初始化签名器
        :param app_secret: 应用的 App Secret
        """
        if not app_secret:
            raise ValueError("App Secret 不能为空")
        self._app_secret = app_secret

    def generate_signature(self, url: str, params: Dict[str, Any]) -> str:
        """
        计算签名
        :param url: 请求的 URL (不包含参数部分)
        :param params: 请求参数字典。注意：如果是 JSON 类型的参数，请先转换为 JSON 字符串传入
        :return: 32位小写 MD5 签名
        """
        if not url:
            raise ValueError("URL 不能为空")
        
        # 1. 过滤掉 sig 参数，并处理 None 值
        filtered_params = {
            k: str(v) for k, v in params.items() 
            if k != "sig" and v is not None
        }
        
        # 2. 将参数按键名升序排序
        sorted_keys = sorted(filtered_params.keys())
        
        # 3. 拼接参数字符串 key=value&key=value
        param_list = []
        for key in sorted_keys:
            # 文档说明：参数中若包含中文，中文保持原文即可，无需对其单独编码
            value = filtered_params[key]
            param_list.append(f"{key}={value}")
            
        param_str = "&".join(param_list)
        
        # 4. 拼接完整字符串: url + ? + sorted_params + app_secret
        # 按照文档说明：请求url + ? + 排序后的参数 + app secret
        raw_str = f"{url}?{param_str}{self._app_secret}"
        
        # 5. MD5 加密
        # 将字符串转换为 utf-8 字节流进行 MD5 计算
        print(f"raw_str: {raw_str}")
        try:
            raw_bytes = raw_str.encode("utf-8")
        except UnicodeError as e:
            raise ValueError(f"编码转换失败: {e}")

        md5 = hashlib.md5()
        md5.update(raw_bytes)
        signature = md5.hexdigest()
        
        return signature

if __name__ == "__main__":
    # 测试案例
    # 参考文档中的示例数据
    # https://waimaiopen.meituan.com/api/v1/member/level/save?app_id=143183&app_poi_code=29594172&level_code=50001&level_index=1&level_name=微卡&timestamp=1767176941
    # TEST_URL = "https://waimaiopen.meituan.com/api/v1/order/getorderdayseq"
    TEST_URL = "https://waimaiopen.meituan.com/api/v1/member/level/save"
    TEST_PARAMS = {
        "app_id":"143184",
        "app_poi_code":"29594172",
        "level_code":"50001",
        "level_index":1,
        "level_name":"微卡",
        "timestamp":"1767494147"
        # "app_id":"0000",
        # "app_poi_code":"31号测试店",
        # "timestamp":"1389751221"
    }
    TEST_SECRET = "6a301058a5c8df27c9e28e39048123cc"
    EXPECTED_SIG = "dbb4d444d68596d03dbcb79a4e4a4e3f"
    
    try:
        signer = MeituanSigner(TEST_SECRET)
        calculated_sig = signer.generate_signature(TEST_URL, TEST_PARAMS)
        print(f"Calculated Signature: {calculated_sig}")
        print(f"Expected Signature:   {EXPECTED_SIG}")
        
        if calculated_sig == EXPECTED_SIG:
            print("Verification Success: 签名计算匹配")
        else:
            print("Verification Result: 签名不匹配 (常见原因：文档示例可能过期或存在隐藏字符)")
            print(f"Computed: {calculated_sig}")
            print(f"Expected: {EXPECTED_SIG}")
            
    except Exception as e:
        print(f"Error: {e}")
