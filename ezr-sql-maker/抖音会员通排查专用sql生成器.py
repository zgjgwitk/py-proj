# -*- coding: UTF-8 -*-
import json
import re

# ==========================================
# 1. 参数配置 (在这里修改查询条件)
# ==========================================
'''
{
    "BrandId": 429,
    "MobileNo": "",
    "OpenId": "",
    "SaleNo": "",
    "VipId": 0,
    "OldVipId": 0
}
# OldVipId 查询掩码会员信息
# VipId 和 OldVipId 同时有值, 会生成 `crm_vip_info_bindold`: VipId=1 AND OldVipId=2
## 没有值的参数不会生成相关的sql
'''
PARAMS_JSON = """
{
    "BrandId": 429,
    "MobileNo": "",
    "OpenId": "",
    "SaleNo": "",
    "VipId": 4802076,
    "OldVipId": 0
}
"""

# ==========================================
# 1.5 分表策略配置 (BrandId -> Table -> Count)
# ==========================================
# 针对特定 BrandId 定义分表数量，未定义的表默认 Count=1
BRAND_SHARD_CONFIG = {
    63: {
        "crm_sal_vip_sale": 8,
        "crm_vip_info": 8
    }
}

# ==========================================
# 2. 表结构配置 (在这里修改表和SQL模板)
# ==========================================
TABLE_CONFIG_JSON = """
[
    {
        "Desc": "crm会员",
        "Table": "crm_vip_info",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND MobileNo='{MobileNo}'"
    },
    {
        "Desc": "crm会员",
        "Table": "crm_vip_info",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND Id={VipId}"
    },
    {
        "Desc": "crm券",
        "Table": "crm_coupon_list",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND VipId={VipId}"
    },
    {
        "Desc": "第三方微信小程序授权信息",
        "Table": "crm_vip_info_third_party_wxapp",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND OpenId='{OpenId}'"
    },
    {
        "Desc": "crm订单表",
        "Table": "crm_sal_vip_sale",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND SaleNo='{SaleNo}' AND DataOrigin=23"
    },
    {
        "Desc": "crm订单表",
        "Table": "crm_sal_vip_sale",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND VipId = {VipId} AND DataOrigin=23"
    },
    {
        "Desc": "crm合卡记录",
        "Table": "crm_vip_info_bindold",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND NewVipId={VipId}"
    },
    {
        "Desc": "crm合卡记录",
        "Table": "crm_vip_info_bindold",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND (NewVipId={VipId} OR OldVipId={OldVipId})"
    },
    {
        "Desc": "crm积分表",
        "Table": "crm_vip_info_bonus",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND VipId = {VipId}"
    },
    {
        "Desc": "根据抖音Open查询订单",
        "Table": "mall_sales_oth_order",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND BuyerCode='{OpenId}'"
    },
    {
        "Desc": "抖音订单",
        "Table": "mall_sales_oth_order",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND Code='{SaleNo}'"
    },
    {
        "Desc": "第三方平台会员绑定关系",
        "Table": "crm_vip_info_third_party_bind",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND CustomerIdentity='{OpenId}'"
    },
    {
        "Desc": "全域会员通绑定/解绑记录表",
        "Table": "crm_vip_info_third_party_bind_log",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND CustomerIdentity='{OpenId}'"
    },
    {
        "Desc": "根据抖音OpenId查询掩码会员",
        "Table": "crm_douyin_vip_openid",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND OpenId='{OpenId}'"
    },
    {
        "Desc": "查询掩码会员信息",
        "Table": "crm_douyin_vip_openid",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND FandsId={OldVipId}"
    },
    {
        "Desc": "抖音平台券",
        "Table": "crm_act_douyin_coupon_bind",
        "Sql": "SELECT * FROM {Table}{Count} WHERE BrandId={BrandId} AND CertificateId='{SaleNo}'"
    }
]
"""

def check_params_valid(sql_template, params):
    """
    检查 SQL 模板中引用的参数是否有效：
    1. 字符串类型参数不能为空字符串
    2. 数字类型参数不能为 0
    3. 如果参数不存在于 params 中，视为无效
    
    返回: (bool, missing_param_name)
    """
    # 提取模板中的参数名，如 {VipId}, {SaleNo}
    # 忽略 {Table} 和 {Count}，它们是系统内置的
    required_keys = re.findall(r'\{(\w+)\}', sql_template)
    
    for key in required_keys:
        if key in ["Table", "Count"]:
            continue
            
        val = params.get(key)
        
        # 1. 参数不存在
        if val is None:
            return False, key
            
        # 2. 字符串类型为空
        if isinstance(val, str) and val.strip() == "":
            return False, key
            
        # 3. 数字类型为 0
        if isinstance(val, (int, float)) and val == 0:
            return False, key
            
    return True, None

def generate_sqls():
    try:
        params = json.loads(PARAMS_JSON)
        tables = json.loads(TABLE_CONFIG_JSON)
    except json.JSONDecodeError as e:
        print(f"JSON 配置解析错误: {e}")
        return

    print("--- 开始生成 SQL ---\n")
    
    # 获取当前 BrandId 的分表配置
    current_brand_id = params.get("BrandId")
    shard_map = BRAND_SHARD_CONFIG.get(current_brand_id, {})
    if shard_map:
        print(f"--- 检测到 BrandId={current_brand_id}，应用特殊分表策略 ---")
        print(f"--- 策略: {shard_map} ---\n")

    for config in tables:
        desc = config.get("Desc", "")
        table = config.get("Table", "")
        # 默认使用配置中的 Count (通常为1)，如果 Brand 配置中有定义则覆盖
        default_count = config.get("Count", 1)
        count = shard_map.get(table, default_count)
        
        sql_template = config.get("Sql", "")
        
        # --- 校验参数有效性 ---
        is_valid, missing_key = check_params_valid(sql_template, params)
        if not is_valid:
            # 如果校验不通过，跳过该表
            continue

        generated_sqls = []

        # 逻辑判断：单表 vs 分表
        if count > 1:
            # 分表模式：循环生成 1 到 Count
            for i in range(1, count + 1):
                # 准备替换字典
                # 1. 基础参数 (BrandId, VipId 等)
                format_args = params.copy()
                # 2. 特殊参数 (Table, Count)
                format_args["Table"] = table
                format_args["Count"] = str(i) # 分表后缀
                
                try:
                    current_sql = sql_template.format(**format_args)
                    generated_sqls.append(current_sql)
                except KeyError as e:
                    # print(f"-- [错误] 模板中包含未定义的参数: {e}")
                    break
        else:
            # 单表模式：Count 替换为空字符串
            format_args = params.copy()
            format_args["Table"] = table
            format_args["Count"] = "" # 单表无后缀
            
            try:
                current_sql = sql_template.format(**format_args)
                generated_sqls.append(current_sql)
            except KeyError as e:
                # print(f"-- [错误] 模板中包含未定义的参数: {e}")
                pass

        # 输出 SQL
        if generated_sqls:
            # 只有当成功生成了 SQL 才打印 Header 和内容
            header = f"-- {desc} Table: {table}" if desc else f"-- Table: {table}"
            print(header)
            
            # 用 UNION ALL 连接，最后加分号
            full_sql = " UNION ALL\n".join(generated_sqls) + ";"
            print(full_sql)
            print() # 空行分隔

if __name__ == "__main__":
    generate_sqls()
