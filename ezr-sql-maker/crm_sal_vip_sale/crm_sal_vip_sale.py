# -* - coding: UTF-8 -* -
#! /usr/bin/python
# 功能: 根据基础的 SQL, 拼接成多个 SQL, 
#  1-每个 SQL 对应一批 VipId(1000个, 如果总数超过1000,就分批处理)
#  2-每个 SQL 对应一个表, 表名是 crm_sal_vip_sale${i}, 其中 ${i} 是从 1 ~ 16 的序号
import os

# vipids 放在 'crm_sal_vip_sale.input.txt' 文件中, 每个 VipId 占一行
SQL = '''
SELECT id,ShopId,SaleNo, VipId,SaleDate FROM `crm_sal_vip_sale${i}` 
WHERE BrandId=6919 AND DataOrigin=23 AND OriginVipId=0 AND VipId in (${vipids})
'''

def generate_sqls():
    input_file = "crm_sal_vip_sale.input.txt"
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(current_dir, input_file)
    
    if not os.path.exists(input_path):
        print(f"Input file not found: {input_path}")
        return []

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}")
        return []

    # Parse VipIds
    # Filter out empty lines just in case
    vip_ids = [line.strip() for line in content.strip().split('\n') if line.strip()]
    
    if not vip_ids:
        print("No VipIds found.")
        return []

    # Deduplicate VipIds
    # Using dict.fromkeys to preserve order, though order doesn't strictly matter for SQL IN clause
    original_count = len(vip_ids)
    vip_ids = list(dict.fromkeys(vip_ids))
    unique_count = len(vip_ids)
    
    if original_count != unique_count:
        print(f"Removed {original_count - unique_count} duplicate VipIds. Processing {unique_count} unique IDs.")

    batch_size = 1000
    # Create batches
    batches = [vip_ids[i:i + batch_size] for i in range(0, len(vip_ids), batch_size)]
    
    generated_sqls = []
    
    # Generate SQLs for each table (1-16) and each batch
    for i in range(1, 17):
        for batch in batches:
            vip_ids_str = ",".join(batch)
            # Replace placeholders
            current_sql = SQL.replace("${i}", str(i)).replace("${vipids}", vip_ids_str)
            generated_sqls.append(current_sql.strip())

    return generated_sqls

if __name__ == "__main__":
    sqls = generate_sqls()
    
    if sqls:
        output_file = "crm_sal_vip_sale.output.txt"
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(current_dir, output_file)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # f.write(f"-- Generated {len(sqls)} SQL statements\n")
                for sql in sqls:
                    f.write(sql + "\n union all\n")
            print(f"Successfully generated {len(sqls)} SQL statements to {output_path}")
        except Exception as e:
            print(f"Error writing to output file: {e}")
