# -*- coding: utf-8 -*-
"""
读取 requestContent_dedup.csv,
按行将 requestContent 字段作为查询串、brandId 作为 header (ezr-brand-id)
重推到 https://open-tp.ezrpro.com/api/JdVipMatchVersion/MemberRegisterCdpToCrm
"""

import csv
import os
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, Tuple


# 接口基础地址
BASE_URL = "https://open-tp.ezrpro.com/api/JdVipMatchVersion/MemberRegisterCdpToCrm"

# 输入文件
INPUT_FILE = r"D:\Github\py-proj\京东会员通bugfix\获取日志requestContent\requestContent_dedup.csv"

# 重推结果输出文件(便于后续人工核查)
RESULT_FILE = r"D:\Github\py-proj\京东会员通bugfix\获取日志requestContent\重推结果.csv"

# 单次请求超时(秒)
REQUEST_TIMEOUT = 30

# 每行重推间隔(秒),避免压垮下游
SLEEP_INTERVAL = 0.3

# header 中环境标签(curl 示例使用 d6583,保持一致)
ENV_TAG = "ezr-main"


def build_url(request_content: str) -> str:
    """拼接完整 URL:基础地址 + ? + requestContent 内容。"""
    return f"{BASE_URL}?{request_content}"


def build_headers(brand_id: str) -> Dict[str, str]:
    """构造请求 header 集合。"""
    return {
        "content-type": "application/x-www-form-urlencoded",
        "ezr-brand-id": brand_id,
        "ezr-env-tag": ENV_TAG,
        "user-agent": "python-retry-script",
    }


def push_one(request_content: str, brand_id: str, session_id: str) -> Tuple[int, str]:
    """
    重推单条记录。
    :return: (http_status, response_body) 元组。
    """
    url = build_url(request_content)
    headers = build_headers(brand_id)
    req = urllib.request.Request(
        url=url,
        headers=headers,
        method="POST",
        # POST body 置空,curl 示例中 --data 也未提供
        data=b"",
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            return status, body
    except urllib.error.HTTPError as e:
        # HTTP 错误(4xx/5xx)也属于"已发起",记录原因
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, body
    except urllib.error.URLError as e:
        return -1, f"URLError:{e.reason}"
    except Exception as e:  # noqa: BLE001
        return -2, f"Exception:{type(e).__name__}:{e}"


def main() -> None:
    if not os.path.exists(INPUT_FILE):
        print(f"输入文件不存在:{INPUT_FILE}")
        sys.exit(1)

    rows: list[Dict[str, str]] = []
    with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            rows.append(row)

    total = len(rows)
    if total == 0:
        print("CSV 中没有可重推的记录")
        return

    print(f"待重推记录数:{total}")

    # 写出结果文件,逐行追加,便于中断后查看进度
    result_fields = ["sessionId", "brandId", "httpStatus", "ok", "response"]
    with open(RESULT_FILE, "w", encoding="utf-8-sig", newline="") as result_fp:
        writer = csv.DictWriter(result_fp, fieldnames=result_fields)
        writer.writeheader()

        success_count = 0
        fail_count = 0
        for idx, row in enumerate(rows, start=1):
            session_id = row.get("sessionId", "")
            brand_id = row.get("brandId", "")
            request_content = row.get("requestContent", "")

            if not request_content or not brand_id:
                fail_count += 1
                writer.writerow({
                    "sessionId": session_id,
                    "brandId": brand_id,
                    "httpStatus": "-3",
                    "ok": "false",
                    "response": "缺少 requestContent 或 brandId",
                })
                print(f"[{idx}/{total}] sessionId={session_id} 跳过(字段缺失)")
                continue

            status, body = push_one(request_content, brand_id, session_id)
            ok = "true" if 200 <= status < 300 else "false"
            if ok == "true":
                success_count += 1
            else:
                fail_count += 1

            writer.writerow({
                "sessionId": session_id,
                "brandId": brand_id,
                "httpStatus": status,
                "ok": ok,
                "response": body[:500],  # 截断,避免结果文件过大
            })
            result_fp.flush()

            print(f"[{idx}/{total}] sessionId={session_id} status={status}")

            # 节流:最后一行不再 sleep
            if idx < total:
                time.sleep(SLEEP_INTERVAL)

    print("重推完成")
    print(f"  成功:{success_count}")
    print(f"  失败:{fail_count}")
    print(f"  结果文件:{RESULT_FILE}")


if __name__ == "__main__":
    main()