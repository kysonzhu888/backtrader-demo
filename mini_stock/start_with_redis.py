#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动带有Redis缓存功能的市场数据服务
"""

import sys
import os
import time
import logging
from datetime import datetime

import environment

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mini_stock.stock_market_service import start_service
from mini_stock.redis_cache_manager import RedisCacheManager

def check_redis_connection():
    """检查Redis连接状态"""
    try:
        cache_manager = RedisCacheManager(host=environment.REDIS_HOST)
        if cache_manager.redis_client:
            cache_manager.redis_client.ping()
            print("✅ Redis连接正常")
            return True
        else:
            print("❌ Redis连接失败")
            return False
    except Exception as e:
        print(f"❌ Redis连接错误: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("股票市场数据服务 - Redis缓存版本")
    print("=" * 60)
    
    # 检查Redis连接
    print("\n1. 检查Redis连接...")
    if not check_redis_connection():
        print("\n请确保Redis服务正在运行：")
        print("  - Linux/macOS: redis-server")
        print("  - Windows: redis-server.exe")
        print("\n或者安装Redis：")
        print("  - Ubuntu/Debian: sudo apt-get install redis-server")
        print("  - macOS: brew install redis")
        return
    
    # 显示配置信息
    print("\n2. 服务配置信息:")
    print(f"   - 服务地址: 0.0.0.0:5000")
    print(f"   - Redis地址: localhost:6379")
    print(f"   - 调仓日期: 2025-06-12")
    print(f"   - 监控日期: 当前日期")
    
    # 启动服务
    print("\n3. 启动市场数据服务...")
    try:
        # 指定调仓日期
        report_date = datetime(2025, 6, 12)
        
        print("🚀 服务启动中，请稍候...")
        print("📊 访问地址: http://localhost:5000")
        print("📈 市场数据: http://localhost:5000/market_data")
        print("📋 股票列表: http://localhost:5000/stock_list")
        print("📊 缓存统计: http://localhost:5000/cache_stats")
        print("🗑️  清空缓存: POST http://localhost:5000/clear_cache")
        print("\n按 Ctrl+C 停止服务")
        
        # 启动服务
        start_service(
            host='0.0.0.0',
            port=5000,
            report_date=report_date
        )
        
    except KeyboardInterrupt:
        print("\n\n🛑 服务已停止")
    except Exception as e:
        print(f"\n❌ 服务启动失败: {e}")

if __name__ == "__main__":
    main() 