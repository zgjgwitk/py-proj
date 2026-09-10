# 京东会员通接口调用

## 发起请求

```powershell
python .\query_member_point.py --account 1376513_jd
```

脚本内已配置 `DEFAULT_APP_SECRET`，会自动生成请求体 token，以及直连版要求的 `source`、`timestamp`、`auth` 请求头。生产环境建议通过环境变量 `JD_APP_SECRET` 覆盖配置。时间戳默认取当前毫秒时间戳，也可以用 `--timestamp` 指定请求体中的固定值。

## 使用 AppSecret 自动计算 token

不要将 AppSecret 写入代码或提交到 Git，可通过环境变量传入：

```powershell
$env:JD_APP_SECRET = "你的AppSecret"
python .\query_member_point.py --account 1376513_jd
```

也支持 `--app-secret`、`--brand-id`、`--appkey`、`--ruid`、`--url` 和 `--timeout` 参数。接口返回内容会以格式化 JSON 输出；返回 `code` 为 `0` 时进程退出码为 `0`，否则为 `1`。
