#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
神秘资金监控演示启动脚本
"""

import time
import threading
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def start_market_service():
    """启动市场数据服务"""
    print("启动市场数据服务...")
    import subprocess
    import sys
    
    try:
        # 启动main.py
        process = subprocess.Popen([sys.executable, 'main.py'])
        print(f"市场数据服务已启动，PID: {process.pid}")
        return process
    except Exception as e:
        print(f"启动市场数据服务失败: {e}")
        return None

def start_dashboard():
    """启动交易监控仪表板"""
    print("启动交易监控仪表板...")
    import subprocess
    import sys
    
    try:
        # 等待市场数据服务启动
        time.sleep(3)
        
        # 启动trading_dashboard.py
        process = subprocess.Popen([sys.executable, 'trading_dashboard.py'])
        print(f"交易监控仪表板已启动，PID: {process.pid}")
        return process
    except Exception as e:
        print(f"启动交易监控仪表板失败: {e}")
        return None

def test_mysterious_fund_api():
    """测试神秘资金API"""
    print("测试神秘资金API...")
    import requests
    import time
    
    # 等待服务启动
    time.sleep(5)
    
    base_url = "http://localhost:5000"
    
    try:
        # 测试健康检查
        response = requests.get(f"{base_url}/mysterious_fund/health", timeout=5)
        if response.status_code == 200:
            print("✅ 神秘资金服务健康检查通过")
        else:
            print(f"❌ 神秘资金服务健康检查失败: {response.status_code}")
            
        # 测试市场数据
        response = requests.get(f"{base_url}/mysterious_fund/market_data", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 神秘资金市场数据获取成功: {data.get('name', 'N/A')} - {data.get('price', 'N/A')}")
        else:
            print(f"❌ 神秘资金市场数据获取失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ API测试失败: {e}")

def main():
    """主函数"""
    print("=== 神秘资金监控演示 ===")
    print(f"启动时间: {datetime.now()}")
    
    # 启动市场数据服务
    market_service_process = start_market_service()
    if not market_service_process:
        print("❌ 市场数据服务启动失败，退出")
        return
    
    # 启动交易监控仪表板
    dashboard_process = start_dashboard()
    if not dashboard_process:
        print("❌ 交易监控仪表板启动失败，退出")
        market_service_process.terminate()
        return
    
    # 测试API
    test_mysterious_fund_api()
    
    print("\n=== 服务启动完成 ===")
    print("市场数据服务: http://localhost:5000")
    print("交易监控仪表板: http://localhost:8051")
    print("神秘资金监控页面: http://localhost:8051 (点击'💰 神秘资金'标签)")
    print("\n按 Ctrl+C 停止服务")
    
    try:
        # 保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        
        # 停止进程
        if dashboard_process:
            dashboard_process.terminate()
            print("交易监控仪表板已停止")
            
        if market_service_process:
            market_service_process.terminate()
            print("市场数据服务已停止")
            
        print("所有服务已停止")

if __name__ == "__main__":
    main() 