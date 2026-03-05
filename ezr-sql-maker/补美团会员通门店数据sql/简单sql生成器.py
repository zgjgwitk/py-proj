"""
简单SQL生成器
使用说明:
1. 修改下面的配置字段值
2. 运行脚本
3. 查看生成的 output.txt 文件
"""

# ============ 配置区域 - 修改这里的值 ============
crm_start_id = 24784111  # 起始Id
brand_id_val = 6685  # 品牌Id
cop_id_val = 6146  # 公司Id
mt_shop_id = '16607267'  # 美团门店Id
shop_name = '山东泰安泰山万达店'  # 门店名称
app_id = '123791'  # AppId
app_secret = 'c1826d880a6b055b5e52fbe36851dd4a'  # AppSecret
shop_id = 25462501  # 注册门店Id
shop_code = 'W0873'  # 门店编码
userId = 13181241  # 用户Id
# ================================================

# 输出文件路径
output_file = 'output.txt'

def generate_sql():
    """生成门店Id查询SQL语句"""
    sql = "SELECT * FROM `ed_base_shop` where BrandId={} AND Name='{}'".format(brand_id_val, shop_name)
    print("生成的门店Id查询SQL语句:")
    print(sql)
    print()

    """生成美团门店SQL语句"""
    sql = "INSERT INTO `ezp-crm`.`crm_act_meituan_vip_cfg` (`Id`, `BrandId`, `CopId`, `MTShopId`, `AppName`, `AppId`, `AppSecret`, `RegShopId`, `Remark`, `Status`, `CreateUser`, `CreateDate`, `LastModifiedUser`, `LastModifiedDate`) VALUES ({}, {}, {}, '{}', '{}', '{}', '{}', {}, '{}', 1, '{}', now(), '{}', now());".format(
        crm_start_id, brand_id_val, cop_id_val, mt_shop_id, shop_name, app_id, app_secret, shop_id, shop_code, userId, userId)

    print("生成的美团门店SQL语句:")
    print(sql)
    print()

if __name__ == "__main__":
    generate_sql()
