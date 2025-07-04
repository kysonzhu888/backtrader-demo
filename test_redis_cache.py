#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redis缓存功能测试脚本
"""

import sys
import os
import time
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mini_stock.redis_cache_manager import RedisCacheManager

def test_redis_cache():
    """测试Redis缓存功能"""
    print("开始测试Redis缓存功能...")
    
    # 初始化缓存管理器
    cache_manager = RedisCacheManager(host='localhost', port=6379, db=0)
    
    if not cache_manager.redis_client:
        print("❌ Redis连接失败，请确保Redis服务正在运行")
        return False
    
    print("✅ Redis连接成功")
    
    # 测试数据
    test_stock_code = "000001.SZ"
    test_data = {
        "code": test_stock_code,
        "price": 12.34,
        "volume": 1000000,
        "change": 0.56,
        "change_pct": 4.76,
        "open": 11.80,
        "high": 12.50,
        "low": 11.75,
        "close": 12.34
    }
    
    # 测试1: 缓存单只股票数据
    print("\n1. 测试缓存单只股票数据...")
    success = cache_manager.cache_stock_data(test_stock_code, test_data)
    if success:
        print("✅ 单只股票数据缓存成功")
    else:
        print("❌ 单只股票数据缓存失败")
        return False
    
    # 测试2: 获取最新数据
    print("\n2. 测试获取最新数据...")
    latest_data = cache_manager.get_latest_stock_data(test_stock_code)
    if latest_data:
        print(f"✅ 获取最新数据成功: {latest_data['price']}")
    else:
        print("❌ 获取最新数据失败")
        return False
    
    # 测试3: 获取当天所有数据
    print("\n3. 测试获取当天所有数据...")
    today_data = cache_manager.get_stock_data_today(test_stock_code)
    if today_data:
        print(f"✅ 获取当天数据成功，共{len(today_data)}条记录")
        for i, data in enumerate(today_data[:3]):  # 只显示前3条
            print(f"   记录{i+1}: 价格={data['price']}, 时间={data['timestamp']}")
    else:
        print("❌ 获取当天数据失败")
        return False
    
    # 测试4: 批量缓存多只股票
    print("\n4. 测试批量缓存多只股票...")
    batch_data = {
        "000002.SZ": {"code": "000002.SZ", "price": 15.67, "volume": 2000000},
        "000858.SZ": {"code": "000858.SZ", "price": 89.12, "volume": 1500000},
        "600036.SH": {"code": "600036.SH", "price": 45.23, "volume": 3000000}
    }
    success = cache_manager.cache_stocks_batch(batch_data)
    if success:
        print("✅ 批量缓存成功")
    else:
        print("❌ 批量缓存失败")
        return False
    
    # 测试5: 批量获取最新数据
    print("\n5. 测试批量获取最新数据...")
    codes = ["000001.SZ", "000002.SZ", "000858.SZ", "600036.SH"]
    latest_batch = cache_manager.get_multiple_latest_data(codes)
    if latest_batch:
        print(f"✅ 批量获取成功，共{len(latest_batch)}只股票")
        for code, data in latest_batch.items():
            print(f"   {code}: 价格={data['price']}")
    else:
        print("❌ 批量获取失败")
        return False
    
    # 测试6: 缓存统计信息
    print("\n6. 测试获取缓存统计信息...")
    stats = cache_manager.get_cache_stats()
    if stats:
        print("✅ 获取统计信息成功:")
        for key, value in stats.items():
            print(f"   {key}: {value}")
    else:
        print("❌ 获取统计信息失败")
        return False
    
    # 测试7: 筛选结果缓存
    print("\n7. 测试筛选结果缓存...")
    conditions = {
        "min_listed_days": 90,
        "exclude_st": True,
        "exclude_delisted": True
    }
    filter_result = [
        {"股票代码": "000001.SZ", "股票名称": "平安银行", "市值(亿)": 1500.5},
        {"股票代码": "000002.SZ", "股票名称": "万科A", "市值(亿)": 1200.3}
    ]
    
    # 缓存筛选结果
    success = cache_manager.cache_filter_result(conditions, filter_result, 300)
    if success:
        print("✅ 筛选结果缓存成功")
    else:
        print("❌ 筛选结果缓存失败")
        return False
    
    # 获取缓存的筛选结果
    cached_result = cache_manager.get_cached_filter_result(conditions)
    if cached_result:
        print(f"✅ 获取缓存筛选结果成功，共{len(cached_result)}条")
    else:
        print("❌ 获取缓存筛选结果失败")
        return False
    
    print("\n🎉 所有测试通过！Redis缓存功能正常工作")
    return True

def test_cache_cleanup():
    """测试缓存清理功能"""
    print("\n测试缓存清理功能...")
    
    cache_manager = RedisCacheManager(host='localhost', port=6379, db=0)
    
    if not cache_manager.redis_client:
        print("❌ Redis连接失败")
        return False
    
    # 清空当天数据
    success = cache_manager.clear_today_data()
    if success:
        print("✅ 当天数据清理成功")
    else:
        print("❌ 当天数据清理失败")
        return False
    
    # 检查清理后的统计信息
    stats = cache_manager.get_cache_stats()
    if stats.get('total_records', 0) == 0:
        print("✅ 数据清理验证成功")
    else:
        print(f"❌ 数据清理验证失败，仍有{stats.get('total_records', 0)}条记录")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("Redis缓存功能测试")
    print("=" * 50)
    
    # 运行基本功能测试
    if test_redis_cache():
        print("\n" + "=" * 50)
        # 运行清理功能测试
        test_cache_cleanup()
    else:
        print("\n❌ 基本功能测试失败，跳过清理测试")
    
    print("\n测试完成！") 