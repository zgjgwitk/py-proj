import hashlib
import json

def make_md5_sign(app_secret, appkey, sort_json, timestamp, method):
    """
    生成MD5签名
    
    Args:
        app_secret (str): 应用密钥
        appkey (str): 应用标识
        sort_json (dict): 排序后的参数字典
        timestamp (str): 时间戳
        method (str): 方法名
    
    Returns:
        str: MD5签名字符串
    """
    # 将字典转换为JSON字符串并排序
    param_json = json.dumps(sort_json, separators=(',', ':'), sort_keys=True)
    
    # 构造签名字符串
    sign_pattern = f"{app_secret}app_key{appkey}method{method}param_json{param_json}timestamp{timestamp}v2{app_secret}"
    
    # 计算MD5
    md5_hash = hashlib.md5(sign_pattern.encode('utf-8'))
    md5_str = md5_hash.hexdigest()
    
    return md5_str.upper()  # 返回大写形式

# 示例使用方法
if __name__ == "__main__":
    # 示例数据
    appSecret = "a559812f-ebb1-4864-ac95-4dcf0ecb3ab1"
    appkey = "7023295253708850700"
    timestamp = "1766547660"
    method = "member.mGetMemberInfoByOpenIdList"
    sort_json = {"app_id":1,"open_id_list":["1@#kq56DzCdqiRsMrr1ejSk9ZBWHBTkuNbOOIQuXJyyK9Vd7+aF3itXVhXZ8bAtevZtDV4p"]}
    # sort_json = {"app_id":1,"open_id_list":["1@#qy8OaQbDuNGHwcvAcHJsRbvXRrToPgmAtZ11EnBqfCImxwbf4M5M451pAXD9POTbv/Pt/3RV"],"extend_info_list":[{"open_id":"1@#qy8OaQbDuNGHwcvAcHJsRbvXRrToPgmAtZ11EnBqfCImxwbf4M5M451pAXD9POTbv/Pt/3RV","mask_mobile":"***0117****"}]}

    # 生成签名
    signature = make_md5_sign(appSecret, appkey, sort_json, timestamp, method)
    print(f"生成的MD5签名: {signature}")