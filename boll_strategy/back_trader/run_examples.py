#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
回测示例运行脚本
提供几个常用的回测场景
"""

import subprocess
import sys
from datetime import datetime, timedelta


def run_command(cmd):
    """运行命令并打印输出"""
    print(f"\n{'='*60}")
    print(f"执行命令: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


def quick_test():
    """快速测试 - 只回测最近一个月"""
    print("\n### 快速测试 - 回测最近一个月 ###")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    cmd = [
        sys.executable, 'boll_backtest.py',
        '--start', start_date.strftime('%Y-%m-%d'),
        '--end', end_date.strftime('%Y-%m-%d')
    ]
    
    return run_command(cmd)


def yearly_test(year):
    """年度回测"""
    print(f"\n### {year}年度回测 ###")
    
    cmd = [
        sys.executable, 'boll_backtest.py',
        '--start', f'{year}-01-01',
        '--end', f'{year}-12-31'
    ]
    
    return run_command(cmd)


def recent_years_test(years=3):
    """最近N年回测"""
    print(f"\n### 最近{years}年回测 ###")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*years)
    
    cmd = [
        sys.executable, 'boll_backtest.py',
        '--start', start_date.strftime('%Y-%m-%d'),
        '--end', end_date.strftime('%Y-%m-%d'),
        '--cash', '200000'
    ]
    
    return run_command(cmd)


def custom_test():
    """自定义回测"""
    print("\n### 自定义回测 ###")
    
    start = input("请输入开始日期 (YYYY-MM-DD): ")
    end = input("请输入结束日期 (YYYY-MM-DD): ")
    cash = input("请输入初始资金 (默认100000): ") or "100000"
    commission = input("请输入手续费率 (默认0.0001): ") or "0.0001"
    
    cmd = [
        sys.executable, 'boll_backtest.py',
        '--start', start,
        '--end', end,
        '--cash', cash,
        '--commission', commission
    ]
    
    return run_command(cmd)


def main():
    """主菜单"""
    while True:
        print("\n" + "="*60)
        print("布林线策略回测 - 示例运行脚本")
        print("="*60)
        print("1. 快速测试（最近30天）")
        print("2. 2023年度回测")
        print("3. 2022年度回测")
        print("4. 最近3年回测")
        print("5. 自定义回测")
        print("0. 退出")
        print("-"*60)
        
        choice = input("请选择 (0-5): ")
        
        if choice == '0':
            print("退出程序")
            break
        elif choice == '1':
            quick_test()
        elif choice == '2':
            yearly_test(2023)
        elif choice == '3':
            yearly_test(2022)
        elif choice == '4':
            recent_years_test(3)
        elif choice == '5':
            custom_test()
        else:
            print("无效选择，请重新输入")
        
        input("\n按回车键继续...")


if __name__ == '__main__':
    main()