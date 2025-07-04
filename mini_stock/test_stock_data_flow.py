"""
测试股票数据流程
验证从数据获取到缓存再到异常检测的完整流程
"""

import logging
import time
from datetime import datetime
from stock_data_model import StockTickData, StockDataFactory
from redis_cache_manager import RedisCacheManager
from cache_config import create_essential_config
from alert_detector import AlertDetector, get_alert_detector


def test_stock_data_creation():
    """测试股票数据创建"""
    print("=== 测试股票数据创建 ===")
    
    # 创建测试数据
    test_data = {
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
    
    # 使用工厂创建StockTickData
    stock_data = StockDataFactory.create_from_xtquant_data(test_data, "000001.SZ")
    print(f"创建的StockTickData: {stock_data}")
    print(f"价格变动: {stock_data.price_change:.2f}")
    print(f"涨跌幅: {stock_data.price_change_pct:.2%}")
    
    return stock_data


def test_redis_cache():
    """测试Redis缓存"""
    print("\n=== 测试Redis缓存 ===")
    
    try:
        # 创建缓存管理器
        cache_manager = RedisCacheManager(
            host='localhost',
            port=6379,
            db=0,
            cache_mode='essential'
        )
        
        if not cache_manager.redis_client:
            print("Redis连接失败，跳过缓存测试")
            return None
        
        # 创建测试数据
        stock_data = test_stock_data_creation()
        
        # 缓存数据
        success = cache_manager.cache_stock_data("000001.SZ", stock_data)
        print(f"缓存单只股票: {'成功' if success else '失败'}")
        
        # 创建更多测试数据
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
        
        # 测试获取数据（返回dict）
        today_data_dict = cache_manager.get_stock_data_today("000001.SZ", limit=5, return_stock_data=False)
        print(f"获取dict格式数据: {len(today_data_dict)}条记录")
        if today_data_dict:
            print(f"第一条记录类型: {type(today_data_dict[0])}")
            print(f"第一条记录字段: {list(today_data_dict[0].keys())}")
        
        # 测试获取数据（返回StockTickData）
        today_data_stock = cache_manager.get_stock_data_today("000001.SZ", limit=5, return_stock_data=True)
        print(f"获取StockTickData格式数据: {len(today_data_stock)}条记录")
        if today_data_stock:
            print(f"第一条记录类型: {type(today_data_stock[0])}")
            if isinstance(today_data_stock[0], StockTickData):
                print(f"第一条记录价格: {today_data_stock[0].lastPrice}")
                print(f"第一条记录涨跌幅: {today_data_stock[0].price_change_pct:.2%}")
        
        return cache_manager
        
    except Exception as e:
        print(f"Redis缓存测试出错: {e}")
        return None


def test_alert_detection():
    """测试异常检测"""
    print("\n=== 测试异常检测 ===")
    
    try:
        # 获取异常检测器
        detector = get_alert_detector()
        
        # 获取缓存管理器
        cache_manager = detector.cache_manager
        
        if not cache_manager:
            print("缓存管理器不可用，跳过异常检测测试")
            return
        
        # 获取StockTickData格式的数据
        today_data = cache_manager.get_stock_data_today("000001.SZ", return_stock_data=True)
        print(f"获取数据用于异常检测: {len(today_data)}条记录")
        
        if today_data:
            print(f"数据类型: {type(today_data[0])}")
            if isinstance(today_data[0], StockTickData):
                print(f"数据字段: {today_data[0].lastPrice}, {today_data[0].volume}")
        
        # 模拟前收盘价
        cache_manager.cache_preclose_data({"000001.SZ": 10.55})
        
        # 手动触发异常检测
        latest_record = {"timestamp": datetime.now().isoformat()}
        detector._detect_stock_alerts("000001.SZ", latest_record)
        
        # 获取异常提示
        alerts = detector.get_recent_alerts(minutes=5)
        print(f"获取到的异常提示: {len(alerts)}条")
        for alert in alerts:
            print(f"  {alert.message}")
        
    except Exception as e:
        print(f"异常检测测试出错: {e}")


def test_data_flow():
    """测试完整数据流程"""
    print("=== 测试完整数据流程 ===")
    
    # 1. 创建股票数据
    stock_data = test_stock_data_creation()
    
    # 2. 测试Redis缓存
    cache_manager = test_redis_cache()
    
    # 3. 测试异常检测
    test_alert_detection()
    
    print("\n=== 数据流程测试完成 ===")


def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    
    print("股票数据流程测试")
    print("=" * 50)
    
    try:
        test_data_flow()
    except Exception as e:
        print(f"测试执行出错: {e}")
        logging.exception("详细错误信息")


if __name__ == "__main__":
    main() 