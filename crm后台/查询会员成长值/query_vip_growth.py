"""
# CRM会员成长值查询工具
  - 目前提供给 GAP(6919) 特供
# 根据VIP ID列表批量查询会员成长值和等级信息，并导出为CSV文件
# 等级列表：
  - 50001: 蓝卡 - 0~600
  - 50002: 银卡 - 600~1500
  - 50003: 金卡 - >=1500
# 现有变量
  - BrandId: 6919
  - cookie
  - vip_ids
  - 等级规则
"""

import requests
import csv
import json
import os
from typing import Dict, List, Any
import time


class VipGrowthQuery:
    """会员成长值查询类"""

    def __init__(self):
        """初始化配置"""
        self.base_url = "https://crm-tp.ezrpro.com/api/crm/Vip/Info/Get"
        self.output_dir = r"D:\Github\py-proj\crm后台\查询会员成长值"
        self.headers = {
            'content-type': 'application/json; charset=utf-8',
            'cookie': 'pcl_sid=DF26432B50574892B103CE1F868B36CB; pcl_brandid=186; pcl_buid=501087; lite_type=0; pcl_sid_cross=840A6BF104E448169118E14983304FE5; pcl_sid=840A6BF104E448169118E14983304FE5; pcl_brandid=6919; pcl_brandid=6919; pcl_buid=1541242; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2214347356%22%2C%22%24device_id%22%3A%2219c0413983ca1c-02d3a6beb872ef8-26011051-2073600-19c0413983d1722%22%2C%22props%22%3A%7B%22%24latest_referrer%22%3A%22%22%2C%22%24latest_referrer_host%22%3A%22%22%7D%2C%22first_id%22%3A%2219c0413983ca1c-02d3a6beb872ef8-26011051-2073600-19c0413983d1722%22%7D; closed-1541242-6919=true',
            'user-agent': 'vscode-restclient',
            'v': 'DDapCatzbrTLTmGIwXyunBhqto28y7hcVVEvm3iwpxFiPVDlE/G/VVqrI7qaLnxCJBucZfC7jn2y+0PBVCfWgucJVZ1hL0GaAxCGYflOjNhtEdIS4kjujCm65DAznRYVW4vabZD9855r5jTKQvrsY2YB6tF8/JIPlzbgKo50kmlYYA+wNa96a33gNaW87WGOm5wPSsVMteE9lGDmOpYH/qcnjJS56+WyTeLAjw+Uq/9VD0qeb+olEQAB+ekJres5aoJKxof7DIn00IvJkH8c5TrFtGy15SbPRXp3bSE8xQ7rVTOvxBkVp8S3yMnfyYk+2FMbFI+Xs87BR1qEgg/A3Q=='
        }

        # VIP ID列表
        self.vip_ids = [
            1660000, 1666902, 2187791, 2719485, 3687732, 8669417, 11021264, 12295103,
            14707518, 15734873, 33624738, 34357319, 35127964, 35166798, 36989743,
            37476811, 37477707, 37477819, 37478953, 37481280, 37481335, 37483000,
            37489053, 37489821, 37495415, 37504638, 37517770, 37517802, 37521767,
            37524357, 37530382, 37533429, 37558995, 37562375, 37566042, 37573153,
            37603210, 37609141, 37611459, 37625694, 37634984, 37643172, 37649287,
            37652503, 37656168, 37656288, 37658311, 37661618, 37661812, 37662670,
            37663100, 37678643, 37681205, 37693706, 37711727, 37720708, 37722025,
            37725401, 37728247, 37750534, 37784646, 37788562, 37814667, 37851528,
            37852268, 37852487, 37856324, 37857408, 37859679, 37890309, 37890799,
            37903562, 37903771
        ]

    def calculate_target_grade(self, buy_money_total: float) -> int:
        """
        根据成长值计算目标等级

        参数:
            buy_money_total: 会员成长值

        返回:
            目标等级ID
        """
        if buy_money_total < 600:
            return 50001
        elif buy_money_total >= 600 and buy_money_total < 1500:
            return 50002
        else:  # buy_money_total >= 1500
            return 50003

    def get_vip_info(self, vip_id: int) -> Dict[str, Any]:
        """
        获取单个会员信息

        参数:
            vip_id: 会员ID

        返回:
            包含会员信息的字典
        """
        params = {
            'Id': vip_id,
            'readPlaintext': 'false'
        }

        try:
            response = requests.get(self.base_url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()

            data = response.json()

            # 检查响应状态
            if data.get('IsError'):
                print(f"VIP ID {vip_id} 查询失败: {data.get('ErrorMsg')}")
                return None

            # 提取所需信息
            info = data.get('Data', {}).get('Info', {})
            consume = data.get('Data', {}).get('Consume', {})

            current_grade_id = info.get('GradeId')
            buy_money_total = consume.get('BuyMoneyTotal', 0.0)
            target_grade_id = self.calculate_target_grade(buy_money_total)

            return {
                'VipId': vip_id,
                'CurrentGradeId': current_grade_id,
                'BuyMoneyTotal': buy_money_total,
                'TargetGradeId': target_grade_id
            }

        except requests.exceptions.RequestException as e:
            print(f"VIP ID {vip_id} 请求失败: {str(e)}")
            return None
        except Exception as e:
            print(f"VIP ID {vip_id} 处理失败: {str(e)}")
            return None

    def query_all_vips(self) -> List[Dict[str, Any]]:
        """
        批量查询所有会员信息

        返回:
            会员信息列表
        """
        results = []
        total = len(self.vip_ids)

        print(f"开始查询 {total} 个会员信息...")

        for index, vip_id in enumerate(self.vip_ids, 1):
            print(f"正在查询 {index}/{total}: VIP ID {vip_id}")

            vip_info = self.get_vip_info(vip_id)

            if vip_info:
                results.append(vip_info)
                print(f"  成功: 成长值={vip_info['BuyMoneyTotal']}, "
                      f"当前等级={vip_info['CurrentGradeId']}, "
                      f"目标等级={vip_info['TargetGradeId']}")

            # 添加延迟避免请求过快
            if index < total:
                time.sleep(0.5)

        print(f"\n查询完成，成功获取 {len(results)}/{total} 个会员信息")
        return results

    def export_to_csv(self, data: List[Dict[str, Any]], filename: str = 'vip_growth_result.csv'):
        """
        导出数据到CSV文件

        参数:
            data: 会员信息列表
            filename: 输出文件名
        """
        if not data:
            print("没有数据可导出")
            return

        # 构建完整的输出路径
        output_path = os.path.join(self.output_dir, filename)

        fieldnames = ['VipId', 'CurrentGradeId', 'BuyMoneyTotal', 'TargetGradeId']

        try:
            with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)

            print(f"\n数据已成功导出到: {output_path}")
            print(f"总计 {len(data)} 条记录")

        except Exception as e:
            print(f"导出CSV文件失败: {str(e)}")

    def run(self):
        """执行完整的查询和导出流程"""
        print("=" * 60)
        print("CRM会员成长值查询工具")
        print("=" * 60)

        # 查询所有会员信息
        results = self.query_all_vips()

        # 导出到CSV
        if results:
            self.export_to_csv(results)

            # 统计等级分布
            self.print_statistics(results)

    def print_statistics(self, data: List[Dict[str, Any]]):
        """
        打印统计信息

        参数:
            data: 会员信息列表
        """
        print("\n" + "=" * 60)
        print("统计信息")
        print("=" * 60)

        # 统计目标等级分布
        grade_count = {}
        grade_mismatch = 0

        for item in data:
            target_grade = item['TargetGradeId']
            grade_count[target_grade] = grade_count.get(target_grade, 0) + 1

            # 统计等级不匹配数量
            if item['CurrentGradeId'] != item['TargetGradeId']:
                grade_mismatch += 1

        print("\n目标等级分布:")
        grade_names = {
            50001: '蓝卡会员',
            50002: '银卡会员',
            50003: '金卡会员'
        }

        for grade_id in sorted(grade_count.keys()):
            count = grade_count[grade_id]
            grade_name = grade_names.get(grade_id, f'等级{grade_id}')
            print(f"  {grade_name}({grade_id}): {count} 人")

        print(f"\n等级不匹配数量: {grade_mismatch} 人")
        print(f"等级匹配数量: {len(data) - grade_mismatch} 人")


def main():
    """主函数"""
    query = VipGrowthQuery()
    query.run()


if __name__ == '__main__':
    main()
