"""
创蓝短信测试数据生成脚本

功能:
为 cl_fix_callback_result_by_total.py 准备测试数据。
- 按 ES_HOST / ES_INDEX / BRAND_ID / SMS_CHAN / SERVICE_TYPES 维度
- 写入 TARGET_TOTAL 条文档, 默认分布:
    * 5 条 resStatus=3 成功
    * 2 条 resStatus=4 失败
    * 15 条 resStatus=1 未知 (供主脚本补足)
- 跑完 cl_fix_callback_result_by_total.py 后, 统计应达到:
    * 15 成功 / 3 失败 / 4 未知
"""

import random
import string
import time
from datetime import datetime, timedelta

from elasticsearch import Elasticsearch

# ============== 脚本配置 ==============
ES_HOST = "http://192.168.128.142:9200/"  # ES 地址
ES_INDEX = "esmsgsms2307"  # ES 索引名
BRAND_ID = 1
SMS_CHAN = 20  # 创蓝渠道
SERVICE_TYPES = [5]  # 视频短信

# 目标数量 (与生产场景 23335/3163/214 等比例放大到 5000 总量)
# 原始: 15/3/4 = 22 -> 放大 5000/22 倍 = 227.27x
# 保留整数: 3409/681/910 = 5000
TARGET_SUCCESS = 3409
TARGET_FAILED = 681
TARGET_UNKNOWN = 910
TARGET_TOTAL = TARGET_SUCCESS + TARGET_FAILED + TARGET_UNKNOWN  # 5000

# 测试数据初始分布 (与目标数的差额 = 需要由主脚本补足的数量)
# 写入总数 = TARGET_TOTAL, 保证主脚本的"总数校验"能通过
# 但成功/失败不达标, 留出大量未知供主脚本去补
# 故意留出 1409 + 381 = 1790 条待更新, 超过 BATCH_SIZE=500, 触发 search_after 多轮分页
INITIAL_SUCCESS = 2000
INITIAL_FAILED = 300
INITIAL_UNKNOWN = TARGET_TOTAL - INITIAL_SUCCESS - INITIAL_FAILED  # 2700
INITIAL_TOTAL = TARGET_TOTAL  # 5000

# 执行控制
FORCE_RECREATE = False  # True=已存在测试数据时强制清空重建; False=已存在则询问
BATCH_SIZE = 500  # bulk 每批写入条数

# 状态码常量
STATUS_UNKNOWN = 1
STATUS_SUCCESS = 3
STATUS_FAILED = 4

# 样例文档模板 (从实际 ES 文档中提取)
SAMPLE_DOC = {
    "resTime": "2025-07-01T16:31:37.8540000",
    "reqTimeDay": 20230701,
    "reqTime": "2025-07-01T16:31:37.7530000",
    "execUser": 0,
    "toUser": 121543,
    "brandId": 1,
    "id": "5EB06FAB1F0EC9DBC64751133D1B52A5",
    "type": "MA",
    "typeKey": "",
    "typeValue": "MAc21aa3c3607944da8c4cd745eabdaf64Activity_Nx0755n",
    "toClient": "18918127007",
    "resStatusMsg": "短信网关成功",
    "resStatusCode": "200",
    "body": 'tempcfgId = 1495, args = {"会员姓名":"施正佶"}',
    "chargeNum": 1,
    "resStatus": 1,
    "gatewayId": "1939965102144987136",
    "serviceType": 5,
    "smsChan": 20,
    "ezrAcc": "1_CL_1",
    "replyTime": "0001-01-01T00:00:00",
}


def connect_es() -> Elasticsearch:
    """连接 ES"""
    return Elasticsearch([ES_HOST], timeout=30, max_retries=3, retry_on_timeout=True)


def random_id() -> str:
    """生成 32 位大写十六进制 ID"""
    return "".join(random.choices(string.hexdigits.upper(), k=32))


def random_gateway_id() -> str:
    """生成 19 位数字 gatewayId"""
    return "".join(random.choices(string.digits, k=19))


def random_phone() -> str:
    """生成 11 位手机号 (1[3-9] 开头)"""
    return "1" + random.choice("3456789") + "".join(random.choices(string.digits, k=9))


def random_req_time() -> datetime:
    """生成 2023-07 月内的随机时间, 避免全部聚集"""
    start = datetime(2023, 7, 1, 0, 0, 0)
    end = datetime(2023, 7, 31, 23, 59, 59)
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def build_doc(seq: int, status: int) -> dict:
    """
    基于样例文档构造一条测试数据

    Args:
        seq: 序号, 用于生成不同的 ID/手机号/reqTime
        status: 目标 resStatus (1=未知, 3=成功, 4=失败)
    """
    doc = dict(SAMPLE_DOC)  # 浅拷贝, 避免修改全局
    doc["id"] = random_id()
    doc["gatewayId"] = random_gateway_id()
    doc["toClient"] = random_phone()
    doc["brandId"] = BRAND_ID
    doc["smsChan"] = SMS_CHAN
    doc["serviceType"] = SERVICE_TYPES[0]  # 单条 serviceType
    doc["resStatus"] = status
    doc["resStatusCode"] = "SUCCESS" if status == STATUS_SUCCESS else ("500" if status == STATUS_FAILED else "200")
    doc["resStatusMsg"] = "发送成功" if status == STATUS_SUCCESS else ("发送失败" if status == STATUS_FAILED else "短信网关成功")

    req_time = random_req_time()
    # 模拟样例里的时间格式 (毫秒精度, 7 位)
    doc["reqTime"] = req_time.strftime("%Y-%m-%dT%H:%M:%S.") + f"{random.randint(0, 999):03d}0000"
    doc["resTime"] = (req_time + timedelta(milliseconds=random.randint(50, 500))).strftime(
        "%Y-%m-%dT%H:%M:%S."
    ) + f"{random.randint(0, 999):03d}0000"
    doc["reqTimeDay"] = int(req_time.strftime("%Y%m%d"))

    # 替换 body 中的会员姓名, 方便辨识
    doc["body"] = f'tempcfgId = 1495, args = {{"会员姓名":"测试用户{seq:04d}"}}'

    return doc


def build_bulk_body(docs: list, index: str) -> list:
    """构造 bulk 写入的请求体 (使用 random_id 作为 _id, 避免重复)"""
    body = []
    for doc in docs:
        body.append({"index": {"_index": index, "_id": doc["id"]}})
        body.append(doc)
    return body


def count_existing(es: Elasticsearch) -> int:
    """统计当前 ES 中已存在的测试数据条数"""
    query = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"brandId": BRAND_ID}},
                    {"term": {"smsChan": SMS_CHAN}},
                    {"terms": {"serviceType": SERVICE_TYPES}},
                ]
            }
        }
    }
    resp = es.search(index=ES_INDEX, size=0, track_total_hits=True, body=query)
    return resp["hits"]["total"]["value"]


def delete_existing(es: Elasticsearch) -> int:
    """按 brandId + smsChan + serviceType 维度删除所有已存在的测试数据"""
    query = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"brandId": BRAND_ID}},
                    {"term": {"smsChan": SMS_CHAN}},
                    {"terms": {"serviceType": SERVICE_TYPES}},
                ]
            }
        }
    }
    resp = es.delete_by_query(
        index=ES_INDEX,
        body=query,
        conflicts="proceed",
        refresh=True,
    )
    return resp.get("deleted", 0)


def main():
    print("=" * 60)
    print("创蓝短信测试数据生成脚本")
    print("=" * 60)
    print(f"ES 地址:    {ES_HOST}")
    print(f"ES 索引:    {ES_INDEX}")
    print(f"brandId:    {BRAND_ID}")
    print(f"smsChan:    {SMS_CHAN} (创蓝)")
    print(f"serviceType:{SERVICE_TYPES}")
    print()
    print(f"目标分布:  成功 {TARGET_SUCCESS} / 失败 {TARGET_FAILED} / 未知 {TARGET_UNKNOWN} / 总数 {TARGET_TOTAL}")
    print(f"本次写入:  成功 {INITIAL_SUCCESS} / 失败 {INITIAL_FAILED} / 未知 {INITIAL_UNKNOWN} / 写入 {INITIAL_TOTAL}")
    print(f"主脚本将补足: 成功 {TARGET_SUCCESS - INITIAL_SUCCESS} / 失败 {TARGET_FAILED - INITIAL_FAILED}")

    # 连接 ES
    es = connect_es()
    print(f"\n已连接到 ES: {ES_HOST}")

    # 检查索引是否存在
    if not es.indices.exists(index=ES_INDEX):
        print(f"\n[警告] 索引 {ES_INDEX} 不存在, 尝试自动创建...")
        # 模拟实际 mapping 里的常见字段类型
        mapping = {
            "mappings": {
                "properties": {
                    "resTime": {"type": "date"},
                    "reqTime": {"type": "date"},
                    "reqTimeDay": {"type": "long"},
                    "execUser": {"type": "long"},
                    "toUser": {"type": "long"},
                    "brandId": {"type": "long"},
                    "id": {"type": "keyword"},
                    "type": {"type": "keyword"},
                    "typeKey": {"type": "keyword"},
                    "typeValue": {"type": "keyword"},
                    "toClient": {"type": "keyword"},
                    "resStatusMsg": {"type": "text"},
                    "resStatusCode": {"type": "keyword"},
                    "body": {"type": "text"},
                    "chargeNum": {"type": "long"},
                    "resStatus": {"type": "long"},
                    "gatewayId": {"type": "keyword"},
                    "serviceType": {"type": "long"},
                    "smsChan": {"type": "long"},
                    "ezrAcc": {"type": "keyword"},
                    "replyTime": {"type": "date"},
                }
            }
        }
        es.indices.create(index=ES_INDEX, body=mapping)
        print(f"  索引 {ES_INDEX} 创建成功")

    # 检查已有数据
    existing = count_existing(es)
    if existing > 0:
        print(f"\n[提示] 已存在 {existing} 条 brandId={BRAND_ID} + smsChan={SMS_CHAN} + serviceType={SERVICE_TYPES} 的数据")
        if FORCE_RECREATE:
            print("  FORCE_RECREATE=True, 直接清空重建")
            deleted = delete_existing(es)
            print(f"  已删除 {deleted} 条")
        else:
            try:
                ans = input("  是否清空后重建? (y/n, 默认 n): ").strip().lower()
            except EOFError:
                ans = "n"
            if ans == "y":
                deleted = delete_existing(es)
                print(f"  已删除 {deleted} 条")
            else:
                print("  保留已有数据, 退出")
                return

    # 构造测试数据
    print(f"\n开始生成 {INITIAL_TOTAL} 条测试数据...")
    docs = []
    seq = 1
    # 成功
    for _ in range(INITIAL_SUCCESS):
        docs.append(build_doc(seq, STATUS_SUCCESS))
        seq += 1
    # 失败
    for _ in range(INITIAL_FAILED):
        docs.append(build_doc(seq, STATUS_FAILED))
        seq += 1
    # 未知
    for _ in range(INITIAL_UNKNOWN):
        docs.append(build_doc(seq, STATUS_UNKNOWN))
        seq += 1

    print(f"已构造 {len(docs)} 条文档")

    # 写入 ES
    print(f"\n开始写入 ES, 每批 {BATCH_SIZE} 条...")
    total_indexed = 0
    total_failed = 0
    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i : i + BATCH_SIZE]
        bulk_body = build_bulk_body(batch, ES_INDEX)
        resp = es.bulk(body=bulk_body, refresh=True)
        for item in resp.get("items", []):
            index_info = item.get("index", {})
            status_code = index_info.get("status", 0)
            if 200 <= status_code < 300:
                total_indexed += 1
            else:
                total_failed += 1
                error = index_info.get("error", {})
                print(f"  [写入失败] _id={index_info.get('_id')}, status={status_code}, error={error}")

    print(f"\n[写入完成] 成功={total_indexed}, 失败={total_failed}")

    # 等待 ES refresh 完成, 确保后续查询可见
    time.sleep(1)

    # 复核
    print("\n--- 写入后统计 ---")
    for status, label in [(STATUS_SUCCESS, "成功"), (STATUS_FAILED, "失败"), (STATUS_UNKNOWN, "未知")]:
        query = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"brandId": BRAND_ID}},
                        {"term": {"smsChan": SMS_CHAN}},
                        {"terms": {"serviceType": SERVICE_TYPES}},
                        {"term": {"resStatus": status}},
                    ]
                }
            }
        }
        resp = es.search(index=ES_INDEX, size=0, track_total_hits=True, body=query)
        print(f"  resStatus={status} ({label}): {resp['hits']['total']['value']}")

    total = count_existing(es)
    print(f"  总数: {total}")

    print("\n[提示] 现在可以运行 cl_fix_callback_result_by_total.py 进行补足")
    print(f"  期望结果: 成功={TARGET_SUCCESS}, 失败={TARGET_FAILED}, 未知={TARGET_UNKNOWN}")


if __name__ == "__main__":
    main()
