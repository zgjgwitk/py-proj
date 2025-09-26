import requests
import hashlib
import datetime

appId = 'AppId'
appSystem = 'MSG'
token = 'ezpasd334remaquqkjam,xa^^^@#$!@@' 

timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

encryStr = f"AppId={appId}&AppSystem={appSystem}&Timestamp={timestamp}&Token={token}"
encrySign = hashlib.sha1(encryStr.encode('utf-8')).hexdigest().upper()

url = 'http://msg-tp.ezrpro.com/api/msg/SendNotifyByEzr'

data = {
  "ArgDatas": {
    "IsFast": True,
    "ToUser": 0, 
    "ToClient": "13402661708",
    "ToZone": None,
    "Content": "【驿氪新零售】亲爱的用户，您绑定手机号的验证码为071111，5分钟内有效",
    "MsgId":"",
    "MsgTime":"",
    "Args":None,
    "TempCfgId":0,
    "AccountCode":None,
    "ExecUser": 0,
    "NeedDelay": False, 
    "DelayTime": "2021-02-24 23:00:00",
    "NeedRetry": 0,
    "MsgType": "EZRAI",
    "MsgTypeKey": "Register",
    "MsgTypeValue": None,
    "BrandId": 1,
    "System":""
  },
  "AppId": appId,
  "AppSystem": appSystem,
  "Timestamp": timestamp,
  "Sign": encrySign,
  "Args": None
}

response = requests.post(url, json=data)

print(response.text)