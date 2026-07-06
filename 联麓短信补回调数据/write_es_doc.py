"""
写入单条 ES 文档
"""

from elasticsearch import Elasticsearch

ES_HOST = "http://192.168.12.124:88/@q1cloud:base.es.biz-10.10.0.8:9200/"
ES_INDEX = "esmsgsms2605"

doc = {
"id": "16727243506154841_35061548",
"resTime": "2026-05-25T20:00:13.6060000",
"reqTimeDay": 20260525,
"reqTime": "2026-05-25T20:00:11",
"execUser": 14691906,
"toUser": 1672724,
"brandId": 7148,
"type": "ActivityTaskTM",
"typeKey": "50004_50004_35061548",
"typeValue": "ActivityTaskTM50004",
"toClient": "18119663176",
"resStatusMsg": "接口调用成功",
"resStatusCode": "200",
"body": "【JOYMARK】🎪六一硬核宠粉 买168元团单即赠百元正品玩具🎈 每日两场限时秒杀速兑👉🏻 ni7.cn/5hLWe 拒收请回复R",
"chargeNum": 1,
"resStatus": 1,
"gatewayId": "202605251020007807925",
"serviceType": 2,
"smsChan": 40,
"ezrAcc": "7148_LL_12971",
"replyTime": "0001-01-01T00:00:00"
}

def main():
    es = Elasticsearch([ES_HOST])
    doc_id = doc["id"]

    result = es.index(index=ES_INDEX, id=doc_id, body=doc)
    print(f"写入结果: {result}")


if __name__ == "__main__":
    main()
