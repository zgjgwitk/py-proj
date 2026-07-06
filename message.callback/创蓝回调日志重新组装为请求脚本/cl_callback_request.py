"""
创蓝回调日志重新组装请求脚本
功能：读取日志Excel文件，解析日志内容并调用对应回调接口，将响应回填到Excel
"""
import json
import re
from typing import Optional
import pandas as pd
import requests
from urllib.parse import urlencode


class ClCallbackRequest:
    """创蓝回调请求处理类"""

    # 接口路由映射
    ROUTES = {
        "ClSmsResult": "/api/callback/ClSmsResult",
        "ClInterSmsResult": "/api/callback/ClInterSmsResult",
        "ClVideoResult": "/api/callback/ClVideoResult",
        "ClSmsReply": "/api/callback/ClSmsReply",
    }

    def __init__(self, base_url: str = None):
        if base_url:
            self.BASE_URL = base_url

    def parse_json_params(self, log_content: str) -> dict:
        """从日志内容中提取JSON参数字符串"""
        # 匹配冒号后面的JSON内容（数组或对象）
        json_match = re.search(r':(\[.*\]|\{.*\})', log_content, re.DOTALL)
        if not json_match:
            return {}

        json_str = json_match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {}

    def analyse_cl_sms_result(self, log_content: str) -> Optional[requests.Response]:
        """
        解析创蓝国内短信结果回调
        接口: GET /api/callback/ClSmsResult
        参数: receiver, pswd, msgid, reportTime, mobile, status, notifyTime, statusDesc, uid, length, brandId
        """
        # 提取JSON参数
        params = self.parse_json_params(log_content)
        if not params or not isinstance(params, dict):
            return None

        # 构建请求参数
        request_params = {
            "receiver": params.get("receiver", ""),
            "pswd": params.get("pswd", ""),
            "msgid": params.get("msgid", ""),
            "reportTime": params.get("reportTime", ""),
            "mobile": params.get("mobile", ""),
            "status": params.get("status", ""),
            "notifyTime": params.get("notifyTime", ""),
            "statusDesc": params.get("statusDesc", ""),
            "uid": params.get("uid", ""),
            "length": params.get("length", 0),
            "brandId": params.get("brandId", 0),
        }

        url = self.BASE_URL + self.ROUTES["ClSmsResult"]
        return requests.get(url, params=request_params)

    def analyse_inter_cl_sms_result(self, log_content: str) -> Optional[requests.Response]:
        """
        解析创蓝国际短信结果回调
        接口: GET /api/callback/ClInterSmsResult
        参数: receiver, pswd, msgid, reportTime, notifyTime, mobile, status, batchSeq, brandId
        """
        params = self.parse_json_params(log_content)
        if not params or not isinstance(params, dict):
            return None

        request_params = {
            "receiver": params.get("receiver", ""),
            "pswd": params.get("pswd", ""),
            "msgid": params.get("msgid", ""),
            "reportTime": params.get("reportTime", ""),
            "notifyTime": params.get("notifyTime", ""),
            "mobile": params.get("mobile", ""),
            "status": params.get("status", ""),
            "batchSeq": params.get("uid", ""),  # 日志中是uid，接口用batchSeq
            "brandId": params.get("brandId", 0),
        }

        url = self.BASE_URL + self.ROUTES["ClInterSmsResult"]
        return requests.get(url, params=request_params)

    def analyse_cl_video_result(self, log_content: str) -> Optional[requests.Response]:
        """
        解析创蓝视频短信回调
        接口: POST /api/callback/ClVideoResult
        参数: List<ClVideoCallbackInfo> reqData
        """
        req_data = self.parse_json_params(log_content)
        if not req_data:
            return None

        url = self.BASE_URL + self.ROUTES["ClVideoResult"]
        headers = {"Content-Type": "application/json"}
        return requests.post(url, json=req_data, headers=headers)

    def analyse_cl_sms_reply(self, log_content: str) -> Optional[requests.Response]:
        """
        解析创蓝国内短信回送上行明细回调
        接口: GET /api/callback/ClSmsReply
        参数: receiver, pswd, moTime, mobile, msg, destcode, spCode, notifyTime, extend
        """
        params = self.parse_json_params(log_content)
        if not params or not isinstance(params, dict):
            return None

        request_params = {
            "receiver": params.get("receiver", ""),
            "pswd": params.get("pswd", ""),
            "moTime": params.get("moTime", ""),
            "mobile": params.get("mobile", ""),
            "msg": params.get("msg", ""),
            "destcode": params.get("destcode", ""),
            "spCode": params.get("spCode", ""),
            "notifyTime": params.get("notifyTime", ""),
            "extend": params.get("extend", ""),
        }

        url = self.BASE_URL + self.ROUTES["ClSmsReply"]
        return requests.get(url, params=request_params)

    def dispatch(self, log_content: str) -> str:
        """根据日志内容分发到对应的解析方法"""
        if not log_content:
            return "空日志"

        try:
            if "创蓝国内短信结果回调-ClSmsResult:" in log_content:
                resp = self.analyse_cl_sms_result(log_content)
            elif "创蓝国际短信结果回调-ClSmsResult:" in log_content:
                resp = self.analyse_inter_cl_sms_result(log_content)
            elif "创蓝视频短信回调接口-ClVideoResult:" in log_content:
                resp = self.analyse_cl_video_result(log_content)
            elif "创蓝国内短信回送上行明细回调-ClSmsReply:" in log_content:
                resp = self.analyse_cl_sms_reply(log_content)
            else:
                return f"未匹配的类型: {log_content[:50]}..."

            if resp is None:
                return "解析失败: 无法提取参数"

            return f"{resp.status_code} - {resp.text}"
        except Exception as e:
            return f"请求异常: {str(e)}"


def process_excel(input_file: str, output_file: str = None, base_url: str = None):
    """
    处理Excel文件中的日志

    Args:
        input_file: 输入Excel文件路径
        output_file: 输出Excel文件路径（默认为覆盖原文件）
        base_url: 回调接口基地址
    """
    if output_file is None:
        output_file = input_file

    # 读取Excel
    df = pd.read_excel(input_file)

    # 确保存在 Response 列，并转换为字符串类型
    if "Response" not in df.columns:
        df["Response"] = ""
    df["Response"] = df["Response"].astype(str)

    # 初始化请求处理器
    handler = ClCallbackRequest(base_url)

    # 处理每行日志
    for idx, row in df.iterrows():
        log_info = str(row.get("LogInfo", ""))
        print(f"处理第 {idx + 1} 行: {log_info[:60]}...")

        # 调用对应的回调接口
        response = handler.dispatch(log_info)
        df.at[idx, "Response"] = response

    # 保存结果
    df.to_excel(output_file, index=False)
    print(f"处理完成，结果已保存到: {output_file}")


if __name__ == "__main__":
    import os

    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    excel_file = os.path.join(script_dir, "msg_callback_log.xlsx")

    # 配置参数
    # BASE_URL = "https://msg-callback-q1.ezrpro.com"  # 根据实际环境修改
    BASE_URL = "https://msg-callback-tp.ezrpro.com" # 生产环境地址

    # 执行处理
    process_excel(excel_file, base_url=BASE_URL)
