#!/usr/bin/env python3
"""
报告生成脚本
支持生成随机IP、随机用户名和告警统计报告
"""

import argparse
import random
import sys
from datetime import datetime, timedelta
from typing import List, Tuple


class ReportGenerator:
    """报告生成器"""

    # 预定义的IP地址段
    IP_PREFIXES = [
        '192.168.1', '10.0.0', '172.16.0', '192.168.0',
        '10.1.1', '172.31.0', '203.0.113', '198.51.100'
    ]

    # 预定义的用户名列表
    USERNAMES = [
        'john_doe', 'jane_smith', 'admin_user', 'developer1', 'tester2',
        'alice_wang', 'bob_zhang', 'carol_liu', 'david_chen', 'emma_huang',
        'frank_lin', 'grace_ma', 'henry_zhou', 'iris_wu', 'jack_zheng',
        'kelly_xu', 'leo_sun', 'mia_jiang', 'nick_guo', 'olivia_bao'
    ]

    # 姓氏列表
    LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones',
                  'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']

    # 名字列表
    FIRST_NAMES = ['James', 'Mary', 'John', 'Patricia', 'Robert',
                   'Jennifer', 'Michael', 'Linda', 'William', 'Elizabeth']

    # 数字后缀（用于生成唯一用户名）
    DIGITS = list(range(1, 1000))

    @classmethod
    def get_current_date(cls) -> str:
        """
        获取当前系统日期

        Returns:
            当前日期字符串（YYYY-MM-DD格式）
        """
        return datetime.now().strftime('%Y-%m-%d')

    @classmethod
    def generate_random_ip(cls) -> str:
        """
        生成随机IP地址

        Returns:
            随机生成的IP地址字符串
        """
        # 随机选择IP前缀
        prefix = random.choice(cls.IP_PREFIXES)
        # 生成后两位
        last_octet = random.randint(1, 254)

        # 如果前缀不完整，补充完整
        if prefix.count('.') == 2:
            # 前缀已经是3段，补充最后一段
            return f"{prefix}.{last_octet}"
        elif prefix.count('.') == 1:
            # 前缀只有2段，补充两段
            second_octet = random.randint(1, 254)
            return f"{prefix}.{second_octet}.{last_octet}"
        else:
            # 完整生成IP
            return f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{last_octet}"

    @classmethod
    def generate_random_count(cls) -> int:
        """
        生成随机数量

        Returns:
            随机数量（1-1000之间）
        """
        return random.randint(1, 1000)

    @classmethod
    def generate_random_username(cls) -> str:
        """
        生成随机用户名

        Returns:
            随机生成的用户名字符串
        """
        # 随机选择生成方式
        method = random.choice(['simple', 'first_last', 'name_digit'])

        if method == 'simple':
            # 从预定义列表中选择
            return random.choice(cls.USERNAMES)
        elif method == 'first_last':
            # 组合姓和名
            first = random.choice(cls.FIRST_NAMES).lower()
            last = random.choice(cls.LAST_NAMES).lower()
            return f"{first}.{last}"
        else:
            # 姓名加数字
            name = random.choice(cls.FIRST_NAMES + cls.LAST_NAMES).lower()
            digit = random.choice(cls.DIGITS)
            return f"{name}{digit}"

    @classmethod
    def generate_alerts(cls, days: int) -> List[Tuple[str, int]]:
        """
        生成指定天数的告警统计数据

        Args:
            days: 天数

        Returns:
            (日期, 告警数量) 元组列表
        """
        alerts = []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        for i in range(days):
            # 往前推 i 天
            date = today - timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')

            # 生成随机告警数量（范围：0-100，使数据更真实）
            # 增加一些趋势效果：越近的日期告警可能越多
            if i == 0:
                # 今天
                alert_count = random.randint(5, 50)
            elif i <= 2:
                # 近3天
                alert_count = random.randint(10, 60)
            elif i <= 5:
                # 中间几天
                alert_count = random.randint(20, 80)
            else:
                # 更早的几天
                alert_count = random.randint(15, 70)

            # 添加一些随机波动
            alert_count = max(0, alert_count + random.randint(-10, 10))

            alerts.append((date_str, alert_count))

        return alerts

    @classmethod
    def get_ips_with_count(cls, count: int) -> List[Tuple[str, int]]:
        """
        获取指定数量的随机IP及对应数量

        Args:
            count: IP数量

        Returns:
            (IP地址, 数量) 元组列表
        """
        ip_list = []
        for i in range(count):
            ip = cls.generate_random_ip()
            num = cls.generate_random_count()
            ip_list.append((ip, num))
        return ip_list

    @classmethod
    def get_usernames(cls, count: int) -> List[str]:
        """
        获取指定数量的随机用户名列表

        Args:
            count: 用户名数量

        Returns:
            用户名列表
        """
        usernames = []
        for i in range(count):
            usernames.append(cls.generate_random_username())
        return usernames

    @classmethod
    def print_ips_with_count(cls, count: int):
        """
        打印指定数量的随机IP及对应数量

        Args:
            count: IP数量
        """
        ip_list = cls.get_ips_with_count(count)
        for ip, num in ip_list:
            print(f"{ip},{num}")

    @classmethod
    def print_usernames(cls, count: int):
        """
        打印指定数量的随机用户名

        Args:
            count: 用户名数量
        """
        for i in range(count):
            username = cls.generate_random_username()
            print(username)

    @classmethod
    def print_alerts(cls, days: int):
        """
        打印告警统计数据

        Args:
            days: 天数
        """
        alerts = cls.generate_alerts(days)

        for date, count in alerts:
            print(f"{date},{count}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='报告生成工具 - 生成随机IP、用户名和告警统计'
    )

    parser.add_argument('--ip', type=int, metavar='N',
                        help='生成N个随机IP地址及对应数量（格式：IP,数量）')
    parser.add_argument('--user', type=int, metavar='N',
                        help='生成N个随机用户名')
    parser.add_argument('--alert', type=int, metavar='DAYS',
                        help='生成最近DAYS天的告警统计（格式：日期,数量）')
    parser.add_argument('--date', action='store_true',
                        help='获取当前系统日期（格式：YYYY-MM-DD）')
    parser.add_argument('--seed', type=int, default=None,
                        help='设置随机种子，用于结果复现')

    args = parser.parse_args()

    # 检查是否至少指定了一个选项
    if args.ip is None and args.user is None and args.alert is None and not args.date:
        print("错误：请至少指定 --ip、--user、--alert 或 --date 中的一个参数", file=sys.stderr)
        sys.exit(1)

    # 设置随机种子（如果提供）
    if args.seed is not None:
        random.seed(args.seed)

    try:
        # 获取当前日期
        if args.date:
            print(ReportGenerator.get_current_date())

        # 生成IP地址及对应数量
        if args.ip:
            if args.ip <= 0:
                print("错误：IP数量必须大于0", file=sys.stderr)
                sys.exit(1)
            ReportGenerator.print_ips_with_count(args.ip)

        # 生成用户名
        if args.user:
            if args.user <= 0:
                print("错误：用户名数量必须大于0", file=sys.stderr)
                sys.exit(1)
            ReportGenerator.print_usernames(args.user)

        # 生成告警统计
        if args.alert:
            if args.alert <= 0:
                print("错误：天数必须大于0", file=sys.stderr)
                sys.exit(1)
            ReportGenerator.print_alerts(args.alert)

    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()