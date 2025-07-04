import numpy as np
import pandas as pd
import vectorbt as vbt
from datetime import datetime

# 沪金期货参数配置
CONFIG = {
    "initial_cash": 120000,  # 初始资金12万
    "contract_multiplier": 1000,  # 合约乘数（1个点=1000元）
    "entry_fee": 20,  # 开仓手续费20元
    "exit_fee": 20,  # 平仓手续费20元
    "margin_rate": 0.10,  # 保证金比例10%
    "leverage": 10,  # 10倍杠杆
    "point_value": 1000,  # 每点价值1000元
    "min_lot": 1  # 最小交易手数
}


# 自定义回调函数处理期货特性
def custom_order_func(c, price, size, fees, slippage):
    """专业期货订单处理器"""
    # 计算保证金占用
    margin_required = price * CONFIG['contract_multiplier'] * CONFIG['margin_rate'] * size

    # 确保有足够保证金
    if c.cash < margin_required:
        size = min(size, c.cash // margin_required)

    # 计算实际合约价值（含合约乘数）
    contract_value = price * CONFIG['contract_multiplier']

    # 计算实际手续费
    contract_fees = (CONFIG['entry_fee'] + CONFIG['exit_fee']) if size > 0 else 0

    # 考虑滑点影响（此处假设1%的滑点）
    slippage_effect = contract_value * slippage

    # 返回处理结果
    return (
        contract_value,  # 合约实际价值
        contract_fees,  # 总手续费
        slippage_effect,  # 滑点成本
        margin_required,  # 保证金占用
        size  # 实际成交手数
    )


# 创建适配期货的Portfolio类
class FutureAUPortfolio(vbt.Portfolio):
    @classmethod
    def from_signals_futures(cls,
                             close,
                             entries,
                             exits,
                             **kwargs):
        """期货专用策略执行器"""
        # 生成信号价格序列
        signal_price = close.vbt.tile(entries.shape[1])

        # 执行交易
        return cls.from_signals(
            close=signal_price,
            entries=entries,
            exits=exits,
            init_cash=CONFIG['initial_cash'],
            fees=0,  # 手续费自定义处理
            slippage=0,  # 滑点自定义处理
            size=CONFIG['min_lot'],  # 最小交易手数
            size_type='shares',  # 按数量交易
            order_func=custom_order_func,  # 核心处理函数
            **kwargs
        )


# 使用示例
if __name__ == "__main__":
    # 模拟沪金期货数据 (单位: 元/克)
    dates = pd.date_range('2023-01-01', periods=100)
    price = pd.Series(
        np.linspace(400, 450, 100) + np.random.randn(100) * 5,
        index=dates,
        name='沪金主力'
    )

    # 生成简单信号 (双均线策略)
    fast_ma = vbt.MA.run(price, 10)
    slow_ma = vbt.MA.run(price, 30)
    entries = fast_ma.ma_crossed_above(slow_ma)
    exits = fast_ma.ma_crossed_below(slow_ma)

    # 执行期货策略
    pf = FutureAUPortfolio.from_signals_futures(
        price,
        entries,
        exits,
        slippage=0.01  # 1%滑点
    )

    # 生成专业交易报告
    print(f"初始资金: {CONFIG['initial_cash']}元")
    print(f"最终权益: {pf.total_value():.2f}元")
    print(f"总盈利: {pf.total_profit():.2f}元")
    print(f"收益率: {pf.total_return() * 100:.2f}%")

    # 分析保证金使用
    margin_usage = pf.orders.records['margin_required'].mean()
    print(f"平均保证金占用: {margin_usage:.2f}元")