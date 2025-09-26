# -* - coding: UTF-8 -* -
#! /usr/bin/python
import requests
import json

# 测试HTTP POST请求
url = "http://10.0.6.139:9200/_reindex?refresh&wait_for_completion=false"

headers = {
    "Content-Type": "application/json"
}

payload = {
    "conflicts": "proceed",
    "source": {
        "remote": {
            "host": "http://10.0.2.35:9200"
        },
        "index": "xxd_cusorder",
        "size": 5000
    },
    "dest": {
        "index": "xxd_cusorder"
    }
}

def test_reindex_request():
    """测试Elasticsearch reindex请求"""
    try:
        print("正在发送reindex请求...")
        print(f"目标URL: {url}")
        print(f"源主机: {payload['source']['remote']['host']}")
        print(f"索引: {payload['source']['index']}")
        
        # 使用更短的超时时间进行测试
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        print(f"\n响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ 请求成功!")
            try:
                result = response.json()
                print(f"任务ID: {result.get('task')}")
                print(f"是否完成: {result.get('completed', False)}")
            except json.JSONDecodeError:
                print("响应不是有效的JSON格式")
        else:
            print(f"\n❌ 请求失败，状态码: {response.status_code}")
            
    except requests.exceptions.ConnectTimeout:
        print("\n❌ 连接超时 - 无法连接到目标服务器 10.0.6.139:9200")
        print("可能的原因:")
        print("1. 目标服务器未启动或网络不可达")
        print("2. 防火墙阻止了连接")
        print("3. IP地址或端口号错误")
        print("4. 网络配置问题")
    except requests.exceptions.ConnectionError:
        print("\n❌ 连接错误 - 无法建立网络连接")
        print("请检查网络连接和服务器状态")
    except requests.exceptions.Timeout:
        print("\n❌ 请求超时 - 服务器响应时间过长")
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 请求异常: {e}")
    except Exception as e:
        print(f"\n❌ 其他异常: {e}")

if __name__ == "__main__":
    test_reindex_request()