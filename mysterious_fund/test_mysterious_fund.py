#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
神秘资金监控功能测试脚本
"""

import requests
import time
import json
from datetime import datetime

def test_mysterious_fund_service():
    """测试神秘资金服务"""
    base_url = "http://localhost:5000"
    
    print("=== 神秘资金监控功能测试 ===")
    
    # 1. 测试健康检查
    print("\n1. 测试健康检查...")
    try:
        response = requests.get(f"{base_url}/mysterious_fund/health")
        if response.status_code == 200:
            print("✅ 健康检查通过")
            print(f"   响应: {response.json()}")
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 健康检查异常: {e}")
    
    # 2. 测试市场数据
    print("\n2. 测试市场数据...")
    try:
        response = requests.get(f"{base_url}/mysterious_fund/market_data")
        if response.status_code == 200:
            data = response.json()
            print("✅ 市场数据获取成功")
            print(f"   基金代码: {data.get('code', 'N/A')}")
            print(f"   基金名称: {data.get('name', 'N/A')}")
            print(f"   最新价: {data.get('price', 'N/A')}")
            print(f"   成交额(亿): {data.get('amount_yi', 'N/A')}")
        else:
            print(f"❌ 市场数据获取失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 市场数据异常: {e}")
    
    # 3. 测试异常提示
    print("\n3. 测试异常提示...")
    try:
        response = requests.get(f"{base_url}/mysterious_fund/alerts/recent?minutes=30")
        if response.status_code == 200:
            alerts = response.json()
            print("✅ 异常提示获取成功")
            print(f"   异常数量: {len(alerts)}")
            for i, alert in enumerate(alerts[:3]):  # 只显示前3个
                print(f"   异常{i+1}: {alert.get('message', 'N/A')}")
        else:
            print(f"❌ 异常提示获取失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 异常提示异常: {e}")
    
    # 4. 测试异常统计
    print("\n4. 测试异常统计...")
    try:
        response = requests.get(f"{base_url}/mysterious_fund/alerts/stats")
        if response.status_code == 200:
            stats = response.json()
            print("✅ 异常统计获取成功")
            print(f"   今日异常: {stats.get('today_alerts', 0)}")
            print(f"   总异常数: {stats.get('total_alerts', 0)}")
            print(f"   按类型统计: {stats.get('by_type', {})}")
        else:
            print(f"❌ 异常统计获取失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 异常统计异常: {e}")
    
    # 5. 测试服务统计
    print("\n5. 测试服务统计...")
    try:
        response = requests.get(f"{base_url}/mysterious_fund/service_stats")
        if response.status_code == 200:
            stats = response.json()
            print("✅ 服务统计获取成功")
            print(f"   服务名称: {stats.get('service_name', 'N/A')}")
            print(f"   基金代码: {stats.get('fund_code', 'N/A')}")
            print(f"   是否交易时间: {stats.get('is_trading_time', 'N/A')}")
        else:
            print(f"❌ 服务统计获取失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 服务统计异常: {e}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_mysterious_fund_service() 