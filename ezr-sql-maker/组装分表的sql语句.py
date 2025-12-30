# -*- coding: UTF-8 -*-
#! /usr/bin/python
# 需求: 我想要实现一个自由组装分表SQL查询语句的功能, 我们的分表规则是 table_name${i}
#   例如我提供原sql: SELECT * FROM crm_vip_info${4} WHERE vipId = 123456 , ${4} 表示分表数量
#     需要生成
#     SELECT * FROM crm_vip_info1 WHERE vipId = 123456
#     UNION ALL
#     SELECT * FROM crm_vip_info2 WHERE vipId = 123456
#     UNION ALL
#     SELECT * FROM crm_vip_info3 WHERE vipId = 123456
#     UNION ALL
#     SELECT * FROM crm_vip_info4 WHERE vipId = 123456
#     ;
import re

# 常用表名
vip_info = "crm_vip_info"
vip_bindold = "crm_vip_info_bindold"
vip_sale = "crm_sal_vip_sale"
vip_bonud = "crm_vip_info_bonus"

# 示例 SQL 模板
# 你可以在这里修改或从输入读取
TABLE_SPLIT = "${8}"
INPUT_SQL = f"SELECT * FROM {vip_sale}{TABLE_SPLIT} WHERE BrandId=63 AND VipId = 118846407"
# INPUT_SQL = f"SELECT * FROM {vip_sale}{TABLE_SPLIT} WHERE BrandId=63 AND SaleNo IN ('6949219130798380089')"
# INPUT_SQL = f"SELECT * FROM {vip_info}{TABLE_SPLIT} WHERE BrandId=63 AND Id = 118756994"
# INPUT_SQL = f"SELECT * FROM {vip_info}{TABLE_SPLIT} WHERE BrandId=63 AND MobileNo='17753465841'"
# INPUT_SQL = f"SELECT * FROM {vip_bindold}{TABLE_SPLIT} WHERE BrandId=6887 AND (OldVipId=922399 OR NewVipId=922399)"

def generate_sharded_sql(sql_template):
    # 正则表达式查找模式如 table_name${number}
    # 它会捕获：
    # 1. ${...} 之前的前缀
    # 2. ${...} 中的数字
    # 3. ${...} 之后的后缀
    # 但是，我们可能有多个出现或者只有一个。
    # 用户示例："SELECT * FROM crm_vip_info${10} WHERE vipId = 123456"
    # 我们希望将 ${10} 替换为 1, 2, ..., 10 并用 UNION ALL 连接。
    
    # 查找分片计数模式：${number}
    match = re.search(r'\$\{(\d+)\}', sql_template)
    
    if not match:
        print("未找到分片模式（例如 ${10}）。返回原始 SQL。")
        return [sql_template]
    
    shard_count = int(match.group(1))
    
    # 我们需要将整个 ${number} 替换为循环索引
    # 但如果存在多个表具有分片，这种简单逻辑可能需要调整。
    # 假设现在只有一个分片模式决定了整个查询的循环。
    
    generated_sqls = []
    for i in range(1, shard_count + 1):
        # 将 ${number} 替换为当前索引 i
        # 我们使用 re.sub 来替换特定匹配项，或者如果唯一的话使用简单的字符串替换
        # 为了安全起见，我们专门替换匹配的组
        
        # 实际上，如果我们有 "tableA${10} JOIN tableB${10}"，我们可能希望它们匹配索引？
        # 或者也许用户只是放了一个占位符。
        # 根据需求 "table_name${i}"，似乎我们应该将 ${N} 替换为 i。
        
        current_sql = sql_template.replace(f"${{{shard_count}}}", str(i))
        generated_sqls.append(current_sql)
        
    return generated_sqls

if __name__ == "__main__":
    # 你可以在这里更改 INPUT_SQL 或修改上面的变量
    sqls = generate_sharded_sql(INPUT_SQL)
    
    print("-- 生成的 SQL:")
    print(" UNION ALL\n".join(sqls) + ";")
