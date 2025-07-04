#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redis缓存API客户端示例
演示如何使用Redis缓存相关的API接口
"""

import requests
import json
import time
from datetime import datetime

class RedisCacheClient:
    """Redis缓存API客户端"""
    
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
    
    def get_market_data(self):
        """获取市场数据"""
        try:
            response = requests.get(f"{self.base_url}/market_data")
            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取市场数据失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"请求失败: {e}")
            return None
    
    def get_stock_list(self):
        """获取股票列表"""
        try:
            response = requests.get(f"{self.base_url}/stock_list")
            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取股票列表失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"请求失败: {e}")
            return None
    
    def get_stock_data_today(self, stock_code, limit=None):
        """获取某只股票当天的所有数据"""
        try:
            url = f"{self.base_url}/stock_data_today/{stock_code}"
            if limit:
                url += f"?limit={limit}"
            
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取股票当天数据失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"请求失败: {e}")
            return None
    
    def get_cache_stats(self):
        """获取缓存统计信息"""
        try:
            response = requests.get(f"{self.base_url}/cache_stats")
            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取缓存统计失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"请求失败: {e}")
            return None
    
    def clear_cache(self):
        """清空缓存"""
        try:
            response = requests.post(f"{self.base_url}/clear_cache")
            if response.status_code == 200:
                return response.json()
            else:
                print(f"清空缓存失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"请求失败: {e}")
            return None
    
    def get_filtered_stocks(self, **kwargs):
        """获取筛选后的股票列表"""
        try:
            response = requests.get(f"{self.base_url}/filtered_stocks", params=kwargs)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取筛选股票失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"请求失败: {e}")
            return None

def demo_basic_usage():
    """演示基本用法"""
    print("=" * 60)
    print("Redis缓存API客户端示例")
    print("=" * 60)
    
    client = RedisCacheClient()
    
    # 1. 获取缓存统计信息
    print("\n1. 获取缓存统计信息:")
    stats = client.get_cache_stats()
    if stats:
        print(f"   当天股票数: {stats.get('today_stocks', 0)}")
        print(f"   最新数据数: {stats.get('latest_stocks', 0)}")
        print(f"   筛选缓存数: {stats.get('filter_caches', 0)}")
        print(f"   总记录数: {stats.get('total_records', 0)}")
        print(f"   日期: {stats.get('date', 'N/A')}")
    
    # 2. 获取股票列表
    print("\n2. 获取股票列表:")
    stock_list = client.get_stock_list()
    if stock_list:
        print(f"   共{len(stock_list)}只股票")
        if len(stock_list) > 0:
            print(f"   示例股票: {stock_list[:3]}")
    
    # 3. 获取市场数据
    print("\n3. 获取市场数据:")
    market_data = client.get_market_data()
    if market_data:
        print(f"   共{len(market_data)}只股票的最新数据")
        if len(market_data) > 0:
            # 显示第一只股票的数据
            first_stock = list(market_data.keys())[0]
            first_data = market_data[first_stock]
            print(f"   示例: {first_stock} = {first_data}")
    
    # 4. 获取某只股票的当天数据
    if stock_list and len(stock_list) > 0:
        test_stock = stock_list[0]
        print(f"\n4. 获取股票 {test_stock} 的当天数据:")
        today_data = client.get_stock_data_today(test_stock, limit=5)
        if today_data:
            print(f"   共{len(today_data)}条记录")
            for i, record in enumerate(today_data[:3]):
                timestamp = record.get('timestamp', 'N/A')
                price = record.get('price', 'N/A')
                print(f"   记录{i+1}: 价格={price}, 时间={timestamp}")
    
    # 5. 获取筛选股票
    print("\n5. 获取筛选后的股票:")
    filtered_stocks = client.get_filtered_stocks(
        min_listed_days=90,
        exclude_st=True,
        exclude_delisted=True,
        exclude_limit_up=True,
        exclude_suspended=True
    )
    if filtered_stocks:
        print(f"   筛选结果: {len(filtered_stocks)}只股票")
        if len(filtered_stocks) > 0:
            for stock in filtered_stocks[:3]:
                print(f"   {stock['股票代码']} - {stock['股票名称']} - 市值{stock['市值(亿)']}亿")

def demo_advanced_usage():
    """演示高级用法"""
    print("\n" + "=" * 60)
    print("高级用法演示")
    print("=" * 60)
    
    client = RedisCacheClient()
    
    # 1. 监控缓存状态
    print("\n1. 监控缓存状态变化:")
    for i in range(3):
        stats = client.get_cache_stats()
        if stats:
            print(f"   第{i+1}次检查: {stats.get('total_records', 0)}条记录")
        time.sleep(2)
    
    # 2. 批量获取多只股票数据
    print("\n2. 批量获取多只股票数据:")
    stock_list = client.get_stock_list()
    if stock_list and len(stock_list) >= 3:
        test_stocks = stock_list[:3]
        for stock_code in test_stocks:
            data = client.get_stock_data_today(stock_code, limit=1)
            if data and len(data) > 0:
                latest = data[0]
                price = latest.get('price', 'N/A')
                timestamp = latest.get('timestamp', 'N/A')
                print(f"   {stock_code}: 价格={price}, 时间={timestamp}")
    
    # 3. 清空缓存（谨慎使用）
    print("\n3. 清空缓存演示:")
    print("   注意: 这会清空所有当天的缓存数据")
    # 取消注释下面的代码来实际执行清空操作
    # result = client.clear_cache()
    # if result:
    #     print("   缓存清空成功")
    # else:
    #     print("   缓存清空失败")

def main():
    """主函数"""
    try:
        # 基本用法演示
        demo_basic_usage()
        
        # 高级用法演示
        demo_advanced_usage()
        
        print("\n" + "=" * 60)
        print("演示完成！")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n演示被用户中断")
    except Exception as e:
        print(f"\n演示过程中出现错误: {e}")

if __name__ == "__main__":
    main() 