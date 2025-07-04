"""
缓存使用示例
展示如何使用新的StockTickData模型和Redis缓存系统
"""

import logging
from datetime import datetime
from stock_data_model import StockTickData, StockDataFactory
from cache_config import CacheConfig, CacheMode, create_essential_config, create_full_config
from redis_cache_manager import RedisCacheManager


def example_1_basic_usage():
    """示例1：基本使用"""
    print("=== 示例1：基本使用 ===")
    
    # 创建股票数据实例
    stock_data = StockTickData(
        time="20250630132600",
        lastPrice=10.65,
        open=10.65,
        high=10.70,
        low=10.53,
        lastClose=10.55,
        amount=30247577.0,
        volume=28448,
        pvolume=2844800,
        tickvol=2844800,
        stockStatus=4,
        openInt=3,
        lastSettlementPrice=13.0,
        askPrice=[10.65, 10.66, 10.67, 10.68, 10.69],
        bidPrice=[10.64, 10.63, 10.62, 10.61, 10.60],
        askVol=[46, 36, 11, 135, 117],
        bidVol=[55, 32, 54, 114, 62],
        settlementPrice=0.0,
        transactionNum=5354,
        pe=0.0
    )
    
    print(f"股票数据: {stock_data}")
    print(f"价格变动: {stock_data.price_change:.2f}")
    print(f"涨跌幅: {stock_data.price_change_pct:.2%}")
    print(f"振幅: {stock_data.amplitude:.2%}")
    
    # 获取核心字段
    essential_fields = stock_data.get_essential_fields()
    print(f"核心字段: {essential_fields}")
    
    # 获取完整字段
    full_fields = stock_data.get_full_fields()
    print(f"完整字段数量: {len(full_fields)}")


def example_2_data_factory():
    """示例2：使用数据工厂"""
    print("\n=== 示例2：使用数据工厂 ===")
    
    # 模拟迅投API返回的原始数据
    raw_data = {
        'time': '20250630132600',
        'lastPrice': 10.65,
        'open': 10.65,
        'high': 10.70,
        'low': 10.53,
        'lastClose': 10.55,
        'amount': 30247577.0,
        'volume': 28448,
        'pvolume': 2844800,
        'tickvol': 2844800,
        'stockStatus': 4,
        'openInt': 3,
        'lastSettlementPrice': 13.0,
        'askPrice': [10.65, 10.66, 10.67, 10.68, 10.69],
        'bidPrice': [10.64, 10.63, 10.62, 10.61, 10.60],
        'askVol': [46, 36, 11, 135, 117],
        'bidVol': [55, 32, 54, 114, 62],
        'settlementPrice': 0.0,
        'transactionNum': 5354,
        'pe': 0.0
    }
    
    # 使用工厂创建StockTickData实例
    stock_data = StockDataFactory.create_from_xtquant_data(raw_data, "000001.SZ")
    print(f"通过工厂创建的股票数据: {stock_data}")
    
    # 批量创建
    batch_data = {
        "000001.SZ": raw_data,
        "000002.SZ": {**raw_data, 'lastPrice': 15.20, 'time': '20250630132601'}
    }
    
    stock_data_dict = StockDataFactory.create_batch_from_xtquant_data(batch_data)
    print(f"批量创建的股票数据数量: {len(stock_data_dict)}")
    for code, data in stock_data_dict.items():
        print(f"  {code}: 价格={data.lastPrice}, 时间={data.time}")


def example_3_cache_config():
    """示例3：缓存配置"""
    print("\n=== 示例3：缓存配置 ===")
    
    # 使用默认配置
    default_config = CacheConfig()
    print(f"默认缓存模式: {default_config.cache_mode}")
    print(f"核心字段: {default_config.essential_fields}")
    print(f"完整字段数量: {len(default_config.full_fields)}")
    
    # 创建核心字段模式配置
    essential_config = create_essential_config()
    print(f"核心字段模式: {essential_config.cache_mode}")
    
    # 创建完整字段模式配置
    full_config = create_full_config()
    print(f"完整字段模式: {full_config.cache_mode}")
    
    # 创建自定义配置
    custom_config = CacheConfig({
        'cache_mode': 'essential',
        'essential_fields': ['time', 'lastPrice', 'volume', 'timestamp'],
        'cache_expire_seconds': {
            'latest_data': 600,  # 10分钟
            'daily_data': 172800,  # 48小时
        }
    })
    print(f"自定义配置: {custom_config.essential_fields}")
    print(f"自定义过期时间: {custom_config.get_expire_seconds('latest_data')}秒")


def example_4_redis_cache():
    """示例4：Redis缓存使用"""
    print("\n=== 示例4：Redis缓存使用 ===")
    
    try:
        # 创建缓存管理器（核心字段模式）
        cache_manager = RedisCacheManager(
            host='localhost',
            port=6379,
            db=0,
            cache_mode='essential'
        )
        
        if not cache_manager.redis_client:
            print("Redis连接失败，跳过缓存示例")
            return
        
        # 创建测试数据
        stock_data = StockTickData(
            time="20250630132600",
            lastPrice=10.65,
            open=10.65,
            high=10.70,
            low=10.53,
            lastClose=10.55,
            amount=30247577.0,
            volume=28448,
            pvolume=2844800,
            tickvol=2844800,
            stockStatus=4,
            openInt=3,
            lastSettlementPrice=13.0,
            askPrice=[10.65, 10.66, 10.67, 10.68, 10.69],
            bidPrice=[10.64, 10.63, 10.62, 10.61, 10.60],
            askVol=[46, 36, 11, 135, 117],
            bidVol=[55, 32, 54, 114, 62],
            settlementPrice=0.0,
            transactionNum=5354,
            pe=0.0
        )
        
        # 缓存单只股票数据
        success = cache_manager.cache_stock_data("000001.SZ", stock_data)
        print(f"缓存单只股票: {'成功' if success else '失败'}")
        
        # 批量缓存
        batch_data = {
            "000001.SZ": stock_data,
            "000002.SZ": StockTickData(
                time="20250630132601",
                lastPrice=15.20,
                open=15.20,
                high=15.25,
                low=15.15,
                lastClose=15.18,
                amount=15000000.0,
                volume=10000,
                pvolume=1000000,
                tickvol=1000000,
                stockStatus=4,
                openInt=0,
                lastSettlementPrice=0.0,
                askPrice=[15.20, 15.21, 15.22, 15.23, 15.24],
                bidPrice=[15.19, 15.18, 15.17, 15.16, 15.15],
                askVol=[100, 80, 60, 40, 20],
                bidVol=[90, 70, 50, 30, 10],
                settlementPrice=0.0,
                transactionNum=2000,
                pe=0.0
            )
        }
        
        success = cache_manager.cache_stocks_batch(batch_data)
        print(f"批量缓存: {'成功' if success else '失败'}")
        
        # 获取缓存的数据
        today_data = cache_manager.get_stock_data_today("000001.SZ", limit=5)
        print(f"获取当天数据: {len(today_data)}条记录")
        
        latest_data = cache_manager.get_latest_stock_data("000001.SZ")
        if latest_data:
            print(f"最新数据: 价格={latest_data.get('lastPrice')}, 时间={latest_data.get('time')}")
        
        # 获取缓存统计
        stats = cache_manager.get_cache_stats()
        print(f"缓存统计: {stats}")
        
    except Exception as e:
        print(f"Redis缓存示例出错: {e}")


def example_5_data_conversion():
    """示例5：数据转换"""
    print("\n=== 示例5：数据转换 ===")
    
    # 创建StockTickData实例
    stock_data = StockTickData(
        time="20250630132600",
        lastPrice=10.65,
        open=10.65,
        high=10.70,
        low=10.53,
        lastClose=10.55,
        amount=30247577.0,
        volume=28448,
        pvolume=2844800,
        tickvol=2844800,
        stockStatus=4,
        openInt=3,
        lastSettlementPrice=13.0,
        askPrice=[10.65, 10.66, 10.67, 10.68, 10.69],
        bidPrice=[10.64, 10.63, 10.62, 10.61, 10.60],
        askVol=[46, 36, 11, 135, 117],
        bidVol=[55, 32, 54, 114, 62],
        settlementPrice=0.0,
        transactionNum=5354,
        pe=0.0
    )
    
    # 转换为字典
    data_dict = stock_data.to_dict()
    print(f"转换为字典: {len(data_dict)}个字段")
    
    # 转换为JSON
    json_str = stock_data.to_json()
    print(f"转换为JSON: {len(json_str)}字符")
    
    # 从字典重新创建
    new_stock_data = StockTickData.from_dict(data_dict)
    print(f"从字典重新创建: {new_stock_data}")
    
    # 从JSON重新创建
    another_stock_data = StockTickData.from_json(json_str)
    print(f"从JSON重新创建: {another_stock_data}")


def main():
    """主函数"""
    print("股票数据模型和缓存系统使用示例")
    print("=" * 50)
    
    # 设置日志级别
    logging.basicConfig(level=logging.INFO)
    
    try:
        example_1_basic_usage()
        example_2_data_factory()
        example_3_cache_config()
        example_4_redis_cache()
        example_5_data_conversion()
        
        print("\n" + "=" * 50)
        print("所有示例执行完成！")
        
    except Exception as e:
        print(f"示例执行出错: {e}")
        logging.exception("详细错误信息")


if __name__ == "__main__":
    main() 