# -* - coding: UTF-8 -* -
#! /usr/bin/python
import requests
import json
import time

# Elasticsearch reindex 配置
# TARGET_URL = "http://10.0.6.139:9200/_reindex?refresh&wait_for_completion=true"
# SOURCE_HOST = "http://10.0.2.35:9200"
BATCH_SIZE = 5000
TARGET_URL = "http://192.168.128.142:9200/_reindex?refresh&wait_for_completion=true"
SOURCE_HOST = "http://192.168.128.142:9200"

# 索引名称列表
# INDEX_NAMES = [
#     "uniontradedetail",
#     "esuser731db3",
#     "esuser3224db1",
#     "esmsgsms2412",
#     "esmsgsms2411",
#     "esmsgwxas2509",
#     "esmsgwxas2508",
#     "essalecmmt10000db1",
#     "esuser2454db1",
#     "esmsgsms2308",
#     "esmsgsms2307",
#     "esmsgsms2306",
#     "esmsgsms2305",
#     "esmsgsms2304",
#     "esmsgsms2303",
#     "esmsgsms2302",
#     "esmsgsms2301",
#     "esmsgalt2508",
#     "esmsgalt2509",
#     "omcrorderdtl1db1",
#     "unionvipinfo",
#     "omcrorderdtl1db2",
#     "esmsgsms2309",
#     "essalecmmt3224db1",
#     "omcrorder739db1",
#     "esarch429db1",
#     "esuser99998db1",
#     "unionzbdetail",
#     "esmsgsms2407",
#     "esmsgsms2406",
#     "esmsgsms2405",
#     "esmsgsms2404",
#     "esmsgsms2403",
#     "esmsgsms2402",
#     "esmsgsms2409",
#     "esmsgsms2408",
#     "esmsgsms2212",
#     "esmsgsms2211",
#     "esmsgsms2210",
#     "esmsgeml2509",
#     "esmsgeml2508",
#     "opapidoc1",
#     "omcrfxshareeffect99999db1",
#     "omcrpay10000db1",
#     "esmsgsms2109",
#     "esmsgsms2311",
#     "esmsgsms2310",
#     "opapidoc",
#     "esuser429db2",
#     "esuser429db3",
#     "esuser429db1",
#     "essalecmmt1db1",
#     "ezphelparticlelite",
#     "esmsgsms2312",
#     "esuser591db1",
#     "esmsgsms2201",
#     "esmsgsms2209",
#     "esmsgsms2208",
#     "esmsgsms2207",
#     "esmsgsms2206",
#     "esmsgsms2205",
#     "esmsgsms2204",
#     "essalecmmt739db1",
#     "esmsgsms2203",
#     "esmsgsms2202",
#     "omcrorder1db1",
#     "esuser20000db1",
#     "esuser20000db2",
#     "omcrfxorder1db1",
#     "omcrorder2db1",
#     "esmsgmqb2309",
#     "esmsgwxa2508",
#     "esmsgwxa2509",
#     "esmsgmqb2308",
#     "omcrorderrate1db1",
#     "esuser740db1",
#     "esmsgmqb2307",
#     "esuser740db3",
#     "ezphelparticle",
#     "esuser3233db1",
#     "esmsgmqb2312",
#     "esmsgmqb2311",
#     "unioncouponlist",
#     "esmsgmqb2310",
#     "essalecmmt3233db1",
#     "esuser10000db2",
#     "unionnewvip",
#     "esmsgsms2112",
#     "esmsgsms2111",
#     "esmsgsms2110",
#     "esmsgsapp2509",
#     "esmsgsapp2508",
#     "esmsgmqb2402",
#     "esmsgmqb2401",
#     "esmsgmqb2408",
#     "esmsgmqb2407",
#     "esmsgmqs2508",
#     "esmsgmqb2409",
#     "esmsgmqb2404",
#     "esmsgmqb2403",
#     "esmsgmqb2406",
#     "esmsgmqb2405",
#     "esmsgmqs2509",
#     "esmsgmqb2411",
#     "esmsgmqb2410",
#     "esmsgmqb2412",
#     "omcrorderaftersale99999db1",
#     "omcrfxshareeffect1db1",
#     "esuser739db1",
#     "esuser739db2",
#     "esuser739db3",
#     "posshopproductsale",
#     "esmsgwxqy2508",
#     "esmsgwxqy2509",
#     "posrlndtlinfo",
#     "esmsgmqb2501",
#     "esmsgmqb2508",
#     "esmsgmqb2509",
#     "esmsgmqb2506",
#     "esmsgmqb2507",
#     "esmsgmqb2504",
#     "esmsgmqb2505",
#     "esmsgmqb2502",
#     "esmsgmqb2503",
#     "omcrfxorderquery740db1",
#     "esmsgxqt2508",
#     "unionpurchaseorder",
#     "esmsgxqt2509",
#     "omcrfxorderquery10000db1",
#     "esmsgsms2506",
#     "esmsgsms2505",
#     "esmsgmqt2509",
#     "esmsgsms2504",
#     "esmsgsms2503",
#     "esmsgmqt2508",
#     "esmsgsms2502",
#     "esmsgsms2501",
#     "omcrfxorder2db1",
#     "esmsgsms2509",
#     "esmsgsms2508",
#     "essalecmmt2454db1",
#     "esmsgsms2507",
#     "unionvipbonus",
#     "essalecmmt9db1",
#     "omcrorderaftersale10000db1",
#     "omcrfxorderquery99999db1",
#     "unioncouponcode",
#     "omcrfxsgsharelog1db1",
#     "omcrorderdtl739db1",
#     "essalecmmt3179db1",
#     "esvip429db1",
#     "esmallproductfullinfo",
#     "esuser3179db1"
# ]

INDEX_NAMES = [ "xxd_cusorder" ]

def reindex_index(index_name):
    """执行单个索引的reindex操作"""
    payload = {
        "conflicts": "proceed",
        "source": {
            "remote": {
                "host": SOURCE_HOST
            },
            "index": index_name,
            "size": BATCH_SIZE
        },
        "dest": {
            "index": index_name
        }
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    print("\n\n>>> 正在发送reindex请求...")
    print(f"目标URL: {TARGET_URL}")
    print(f"源主机: {payload['source']['remote']['host']}")
    print(f"索引: {payload['source']['index']}")

    json_str = json.dumps(payload, ensure_ascii=False, indent=2)
    print(f"\n Body内容: {json_str}")

    try:
        response = requests.post(TARGET_URL, headers=headers, json=payload, timeout=600)
        response.raise_for_status()
        
        print(f"\n响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ 请求成功!")
            try:
                result = response.json()
                print(f"索引 {index_name} reindex 任务已提交")
            except json.JSONDecodeError:
                print("\n❌ 响应不是有效的JSON格式")
        else:
            print(f"\n❌ 请求失败，状态码: {response.status_code}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 索引 {index_name} reindex 失败: {e}")
        return False
    except ValueError as e:
        print(f"\n❌ JSON 解析失败: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 其他异常: {e}")
        return False


def sync_reindex_all():
    """同步执行所有索引的reindex操作"""
    print(f"开始执行 {len(INDEX_NAMES)} 个索引的reindex操作...")
    
    success_count = 0
    failed_count = 0
    
    for index_name in INDEX_NAMES:
        print(f"正在处理索引: {index_name}")
        
        if reindex_index(index_name):
            success_count += 1
        else:
            failed_count += 1
        
        # 添加短暂延迟避免请求过于频繁
        time.sleep(0.5)
    
    print(f"\nreindex操作完成!")
    print(f"成功: {success_count}, 失败: {failed_count}")


if __name__ == "__main__":
    sync_reindex_all()