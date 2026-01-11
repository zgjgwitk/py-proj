import pandas as pd
import os

# 使用教程
# 1. 原始门店数据.xls 和 门店info.xls 按照模板填写这两个文件
#    1.1. 使用前需要填写 crm_start_id 和 ed_start_id 的值
#    1.2. crm_act_meituan_vip_cfg 表的起始 Id 值在 50000 以下就不会影响发号器
#    1.3. ed_base_third_party_seller 表的 Id 没用发号器，自己定义即可
# 2. 运行本脚本，会在ezr-sql-maker/补美团会员通门店数据sql目录下生成 output.txt 文件，包含所有生成的SQL语句
# 3. 检查output.txt文件，SQL 语句分为两部分: 
#    3.1. 第一部分是 CRM 库的 SQL 语句，
#    3.2. 第二部分是 ED 库的 SQL 语句，用于门店信息缓存的，所有品牌数据都在这个表里

# 全局变量配置
BrandId = 6964  # 可根据实际需求修改
CopId = 6330    # 可根据实际需求修改
crm_start_id = 1  # CRM表Id的起始值
ed_start_id = 1  # ED表Id的起始值
userId = 0

_orignDataFile = 'ezr-sql-maker/补美团会员通门店数据sql/原始门店数据.xls'
_ShopDataFile = 'ezr-sql-maker/补美团会员通门店数据sql/门店info.xls'
_outputFile = 'ezr-sql-maker/补美团会员通门店数据sql/output.txt'
_errorFile = 'ezr-sql-maker/补美团会员通门店数据sql/error.txt'

def generate_sql():
    global crm_start_id
    global ed_start_id
    try:
        # 读取Excel文件
        tb1 = pd.read_excel(_orignDataFile)
        tb2 = pd.read_excel(_ShopDataFile)
        
        print("读取文件成功")
        print("tb1 shape:", tb1.shape)
        print("tb2 shape:", tb2.shape)
        
        # 根据ShopCode进行数据匹配并合并
        merged_data = pd.merge(tb1, tb2[['ShopCode', 'ShopId']], on='ShopCode', how='left')
        
        print("合并后数据形状:", merged_data.shape)
        
        # 生成SQL语句
        sql_statements = []
        error_lines = []
        
        # 写crm库 crm_act_meituan_vip_cfg
        for index, row in merged_data.iterrows():
            try:
                # 获取各个字段的值，处理空值情况
                mt_shop_id = row.get('MTShopId', '') if pd.notna(row.get('MTShopId')) else ''
                shop_name = row.get('ShopName', '') if pd.notna(row.get('ShopName')) else ''
                app_id = row.get('AppId', '') if pd.notna(row.get('AppId')) else ''
                app_secret = row.get('AppSecret', '') if pd.notna(row.get('AppSecret')) else ''
                shop_code = row.get('ShopCode', '') if pd.notna(row.get('ShopCode')) else ''
                
                # 检查是否匹配成功（ShopId应该有值）
                shop_id = row.get('ShopId', None)
                if pd.isna(shop_id):
                    # 如果没有匹配到ShopId，记录错误行
                    error_lines.append(row)
                    continue
                
                # 确保shop_id是整型
                try:
                    shop_id = int(shop_id)
                except (ValueError, TypeError):
                    # 如果转换失败，也记录错误行
                    error_lines.append(row)
                    continue
                
                # 使用全局变量
                brand_id_val = BrandId
                cop_id_val = CopId
                
                # 构造SQL语句（使用单引号包围字符串）
                sql = "INSERT INTO `ezp-crm`.`crm_act_meituan_vip_cfg` (`Id`, `BrandId`, `CopId`, `MTShopId`, `AppName`, `AppId`, `AppSecret`, `RegShopId`, `Remark`, `Status`, `CreateUser`, `CreateDate`, `LastModifiedUser`, `LastModifiedDate`) VALUES ({}, {}, {}, '{}', '{}', '{}', '{}', {}, '{}', 1, '{}', now(), '{}', now());".format(
                    crm_start_id, brand_id_val, cop_id_val, mt_shop_id, shop_name, app_id, app_secret, shop_id, shop_code, userId, userId)
                
                sql_statements.append(sql)
                crm_start_id += 1  # 自增值递增
                
            except Exception as e:
                # 记录错误行
                error_lines.append(row)
                print(f"处理第{index}行时发生错误: {str(e)}")
                continue
        
        sql_statements.append('-------------------------------')
        sql_statements.append('### 以下是ed_base_third_party_seller 表的SQL语句 ###')
        sql_statements.append('-------------------------------')


        # 写 ed库 ed_base_third_party_seller
        for index, row in merged_data.iterrows():
            try:
                # 获取各个字段的值，处理空值情况
                mt_shop_id = row.get('MTShopId', '') if pd.notna(row.get('MTShopId')) else ''
                shop_name = row.get('ShopName', '') if pd.notna(row.get('ShopName')) else ''
                app_id = row.get('AppId', '') if pd.notna(row.get('AppId')) else ''
                app_secret = row.get('AppSecret', '') if pd.notna(row.get('AppSecret')) else ''
                shop_code = row.get('ShopCode', '') if pd.notna(row.get('ShopCode')) else ''
                
                # 检查是否匹配成功（ShopId应该有值）
                shop_id = row.get('ShopId', None)
                if pd.isna(shop_id):
                    # 如果没有匹配到ShopId，记录错误行
                    error_lines.append(row)
                    continue
                
                # 确保shop_id是整型
                try:
                    shop_id = int(shop_id)
                except (ValueError, TypeError):
                    # 如果转换失败，也记录错误行
                    error_lines.append(row)
                    continue
                
                # 使用全局变量
                brand_id_val = BrandId
                cop_id_val = CopId
                
                # 构造SQL语句（使用单引号包围字符串）
                sql = "INSERT INTO `ezp-ed`.`ed_base_third_party_seller` (`Id`, `BrandId`, `CopId`, `SellerIdentity`, `Name`, `SellerId`, `ThirdPartyId`, `CreateDate`, `LastModifiedDate`) VALUES ({}, {}, {}, '{}', '{}', '{}', 20, now(), now());".format(
                    ed_start_id, brand_id_val, cop_id_val, mt_shop_id, shop_name, shop_id)
                
                sql_statements.append(sql)
                ed_start_id += 1  # 自增值递增
                
            except Exception as e:
                # 记录错误行
                error_lines.append(row)
                print(f"处理第{index}行时发生错误: {str(e)}")
                continue

        # 写入到output.txt文件
        with open(_outputFile, 'w', encoding='utf-8') as f:
            for sql in sql_statements:
                f.write(sql + '\n')
        
        # 写入错误信息到error.txt文件
        if error_lines:
            with open(_errorFile, 'w', encoding='utf-8') as f:
                for error_line in error_lines:
                    # 将整行数据转换为字符串写入
                    f.write(str(error_line.to_dict()) + '\n')
            print(f"共发现 {len(error_lines)} 条匹配失败的数据，已写入到 {_errorFile}")
        
        print(f"SQL语句已成功写入到 {_outputFile}")
        print(f"共生成 {len(sql_statements)} 条SQL语句")
        
    except Exception as e:
        print(f"发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    generate_sql()