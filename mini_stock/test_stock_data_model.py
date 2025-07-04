"""
测试StockTickData模型
验证修复后的代码是否能正确处理不完整的数据
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from stock_data_model import StockTickData, StockDataFactory


def test_from_dict_with_incomplete_data():
    """测试使用不完整数据创建StockTickData实例"""
    print("=== 测试使用不完整数据创建StockTickData实例 ===")
    
    # 测试1：只有核心字段的数据
    essential_data = {
        'time': '20250701105100',
        'lastPrice': 8.48,
        'open': 8.31,
        'high': 8.68,
        'low': 8.23,
        'lastClose': 8.24,
        'amount': 23538925.0,
        'volume': 27810
    }
    
    try:
        stock_data = StockTickData.from_dict(essential_data)
        print(f"✓ 成功创建StockTickData实例: {stock_data}")
        print(f"  缺失字段已自动补充为默认值")
        print(f"  pvolume: {stock_data.pvolume}")
        print(f"  tickvol: {stock_data.tickvol}")
        print(f"  stockStatus: {stock_data.stockStatus}")
        print(f"  askPrice: {stock_data.askPrice}")
    except Exception as e:
        print(f"✗ 创建失败: {e}")
        return False
    
    # 测试2：使用StockDataFactory创建
    print("\n=== 测试使用StockDataFactory创建 ===")
    try:
        stock_data2 = StockDataFactory.create_from_xtquant_data(essential_data, "002188.SZ")
        print(f"✓ 成功使用StockDataFactory创建: {stock_data2}")
    except Exception as e:
        print(f"✗ StockDataFactory创建失败: {e}")
        return False
    
    return True


def test_from_essential_fields():
    """测试从核心字段创建实例"""
    print("\n=== 测试从核心字段创建实例 ===")
    
    # 创建一个完整的StockTickData实例
    complete_data = StockTickData(
        time="20250701105100",
        lastPrice=8.48,
        open=8.31,
        high=8.68,
        low=8.23,
        lastClose=8.24,
        amount=23538925.0,
        volume=27810,
        pvolume=2781033,
        tickvol=2781033,
        stockStatus=4,
        openInt=3,
        lastSettlementPrice=13.0,
        askPrice=[8.48, 8.51, 8.52, 8.53, 8.59],
        bidPrice=[8.47, 8.45, 8.44, 8.43, 8.42],
        askVol=[1, 8, 46, 25, 28],
        bidVol=[14, 76, 76, 129, 160],
        settlementPrice=0.0,
        transactionNum=2368,
        pe=0.0
    )
    
    # 获取核心字段
    essential_fields = complete_data.get_essential_fields()
    print(f"核心字段: {essential_fields}")
    
    # 尝试从核心字段重新创建实例
    try:
        recreated_data = StockTickData.from_dict(essential_fields)
        print(f"✓ 成功从核心字段重新创建实例: {recreated_data}")
        print(f"  所有必需字段都已自动补充")
    except Exception as e:
        print(f"✗ 从核心字段创建失败: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("开始测试StockTickData模型...")
    
    success1 = test_from_dict_with_incomplete_data()
    success2 = test_from_essential_fields()
    
    if success1 and success2:
        print("\n🎉 所有测试通过！StockTickData模型修复成功。")
    else:
        print("\n❌ 部分测试失败，需要进一步检查。") 