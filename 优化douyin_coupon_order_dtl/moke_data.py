#!/usr/bin/env python3
"""批量向 crm_act_douyin_coupon_order_dtl_test_1 写入测试数据。

需求中的总数是 200 万；EzrStatus=1 的数量按 120 万处理（原需求中的
12000000 会令三个状态合计为 1280 万，与总数冲突）。

依赖：pip install pymysql

示例：
    python moke_data.py --host 127.0.0.1 --port 3306 \
        --user root --password your_password

先检查样例但不连接数据库：
    python 优化douyin_coupon_order_dtl/moke_data.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Iterator, Sequence, Tuple


DATABASE = "ezp-crm1"
TABLE = "crm_act_douyin_coupon_order_dtl_test_1"
TOTAL_COUNT = 2_000_000
STATUS_COUNTS = ((0, 100_000), (1, 1_200_000), (2, 700_000))
START_DATE = datetime(2026, 7, 1)
DAY_COUNT = 15

COLUMNS = (
    "CopId", "BrandId", "DouyinOrderId", "DouyinOrderTime",
    "DouyinOrderStatus", "DouyinProductName", "DouyinProductId",
    "EzrStatus", "FulfilTime", "SmsScheduledTime", "SmsSendTime",
    "SmsSendStatus", "CouponExpireTime", "OpenId", "MobileNo", "VipId",
    "CreateUserId", "CreateDate", "LastModifiedUserId", "LastModifiedDate",
    "DouyinLifeAccountId", "DouyinOrderDayInt",
)

INSERT_SQL = (
    f"INSERT INTO `{DATABASE}`.`{TABLE}` "
    f"({', '.join(f'`{column}`' for column in COLUMNS)}) "
    f"VALUES ({', '.join(['%s'] * len(COLUMNS))})"
)

Row = Tuple[object, ...]


def status_for_index(index: int) -> int:
    """根据全局序号返回状态，确保各状态数量精确符合要求。"""
    boundary = 0
    for status, count in STATUS_COUNTS:
        boundary += count
        if index < boundary:
            return status
    raise IndexError(f"数据序号越界: {index}")


def make_row(index: int) -> Row:
    """构造一行数据；日期轮询分配，使每天的数据量之差最多为 1。"""
    sequence = index + 1
    day_offset = index % DAY_COUNT
    second_offset = (index // DAY_COUNT) % 86_400
    order_time = START_DATE + timedelta(days=day_offset, seconds=second_offset)
    fulfil_time = order_time + timedelta(days=1, hours=1)
    sms_time = order_time + timedelta(days=4)
    expire_time = (order_time + timedelta(days=9)).replace(
        hour=23, minute=59, second=59
    )

    return (
        100,
        1,
        f"DY{sequence:016d}",
        order_time,
        1,
        "抖音优惠券B",
        f"DP{sequence:016d}",
        status_for_index(index),
        fulfil_time,
        sms_time,
        sms_time,
        1,
        expire_time,
        f"openid{sequence:016d}",
        f"1{sequence % 10_000_000_000:010d}",
        1_000_000 + sequence,
        456,
        order_time,
        456,
        order_time,
        "7092006059992156195",
        int(order_time.strftime("%Y%m%d")),
    )


def iter_batches(total: int, batch_size: int) -> Iterator[Sequence[Row]]:
    """逐批生成数据，避免将 200 万行全部放入内存。"""
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        yield [make_row(index) for index in range(start, end)]


def validate_config(total: int, batch_size: int) -> None:
    expected = sum(count for _, count in STATUS_COUNTS)
    if total != expected:
        raise ValueError(
            f"总数必须等于状态数量之和 {expected:,}，当前为 {total:,}"
        )
    if batch_size <= 0:
        raise ValueError("batch-size 必须大于 0")


def insert_data(args: argparse.Namespace) -> None:
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("缺少依赖，请先执行: pip install pymysql") from exc

    connection = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=DATABASE,
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=args.connect_timeout,
    )
    inserted = 0
    started_at = time.monotonic()
    try:
        with connection.cursor() as cursor:
            for batch in iter_batches(args.total, args.batch_size):
                cursor.executemany(INSERT_SQL, batch)
                connection.commit()
                inserted += len(batch)
                elapsed = max(time.monotonic() - started_at, 0.001)
                print(
                    f"已写入 {inserted:,}/{args.total:,} 行 "
                    f"({inserted / args.total:.1%})，平均 {inserted / elapsed:,.0f} 行/秒",
                    flush=True,
                )
    except BaseException:
        connection.rollback()
        print(f"写入失败；当前批次已回滚，之前已提交 {inserted:,} 行。", file=sys.stderr)
        raise
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量生成抖音券订单测试数据")
    parser.add_argument("--host", default=os.getenv("MYSQL_HOST", "192.168.12.82"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")))
    parser.add_argument("--user", default=os.getenv("MYSQL_USER", "ezwrite"))
    parser.add_argument("--password", default=os.getenv("MYSQL_PASSWORD", "33KlsXareQbsbrfhq2eJ"))
    parser.add_argument("--batch-size", type=int, default=2_000)
    parser.add_argument("--connect-timeout", type=int, default=10)
    parser.add_argument(
        "--total", type=int, default=TOTAL_COUNT,
        help=f"写入数量，必须为 {TOTAL_COUNT}",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="不连接数据库，仅校验配置并输出各状态的边界样例",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_config(args.total, args.batch_size)

    if args.dry_run:
        sample_indexes = (0, 99_999, 100_000, 1_299_999, 1_300_000, 1_999_999)
        print("配置校验通过，边界样例如下：")
        for index in sample_indexes:
            row = make_row(index)
            print(
                f"index={index}, order_id={row[2]}, order_time={row[3]}, "
                f"EzrStatus={row[7]}, DouyinOrderDayInt={row[21]}"
            )
        return 0

    insert_data(args)
    print(f"完成，共写入 {args.total:,} 行。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
