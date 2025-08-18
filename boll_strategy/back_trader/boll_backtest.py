#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
布林线策略回测程序 v2.0
使用backtrader框架实现

主要功能：
- 支持分钟级别和日线级别回测
- 自动根据时间周期调整策略参数
- 完整的风险管理和统计分析

策略说明：
- 使用布林线突破策略（以收线为准）
- 当K线收盘价突破上轨时做多，收盘价回撤到中轨时平仓
- 当K线收盘价突破下轨时做空，收盘价回升到中轨时平仓
- 止损采用盘中即时触发，其他信号需收线确认
- 使用ATR进行动态止损止盈管理

使用方法：
1. 修改 BacktestConfig 中的 TIMEFRAME：
   - 'MINUTE': 分钟级别回测（默认）
   - 'DAILY': 日线级别回测
   
2. 直接运行: python boll_backtest.py
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, time
import backtrader as bt
import backtrader.analyzers as btanalyzers
import matplotlib.pyplot as plt

# 添加上级目录到路径，以便导入配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 注释掉导入，因为只是用于IDE提示，实际不需要
# from boll_strategy import BollStrategyConfig


# ==================== 回测配置 ====================
class BacktestConfig:
    """回测配置类 - 在这里修改回测参数"""
    
    # 数据周期配置
    TIMEFRAME = 'MINUTE'       # 数据周期：'MINUTE'（分钟线）或 'DAILY'（日线）
    
    # 时间范围配置
    START_DATE = '2024-01-01'  # 回测开始日期
    END_DATE = '2025-03-01'    # 回测结束日期
    
    # 资金配置
    INITIAL_CASH = 100000      # 初始资金
    COMMISSION = 3             # 手续费：每手3元（固定费用）
    MARGIN_RATE = 0.09         # 保证金比例：9%
    # 注：实际保证金 = 合约价值 * MARGIN_RATE
    # 例如：8000元/吨 * 10吨 * 9% = 7200元/手
    
    # 策略参数配置（根据时间周期自动调整）
    # 分钟级别参数
    MINUTE_PARAMS = {
        'boll_period': 26,     # 布林线周期
        'boll_std': 2.0,       # 标准差倍数
        'atr_period': 14,      # ATR周期
        'atr_multiplier': 2.0, # ATR倍数
        'hard_stop_loss': 380, # 硬止损金额
    }
    
    # 日线级别参数（通常需要更长的周期）
    DAILY_PARAMS = {
        'boll_period': 20,     # 布林线周期（日线常用20）
        'boll_std': 2.0,       # 标准差倍数
        'atr_period': 14,      # ATR周期
        'atr_multiplier': 1.5, # ATR倍数（日线用更小的倍数）
        'hard_stop_loss': 3000,# 硬止损金额（日线波动更大，需要更大的止损空间）
        'use_atr_stop': True,  # 日线建议使用ATR止损而非固定止损
    }
    
    # 根据时间周期选择参数
    @classmethod
    def get_strategy_params(cls):
        if cls.TIMEFRAME == 'DAILY':
            return cls.DAILY_PARAMS
        else:
            return cls.MINUTE_PARAMS
    
    CONTRACT_MULTIPLIER = 10   # 合约乘数
    
    # 显示配置
    PRINT_LOG = False         # 是否打印交易日志（关闭以提高速度）
    PLOT_CHART = False        # 是否显示图表（关闭以提高速度）
    
    # 数据文件配置
    DATA_FILE = 'OI9999.XZCE.csv'  # 数据文件名


class BollStrategy(bt.Strategy):
    """布林线回测策略"""
    
    # 获取策略参数
    strategy_params = BacktestConfig.get_strategy_params()
    
    params = (
        ('boll_period', strategy_params['boll_period']),           # 布林线周期
        ('boll_std', strategy_params['boll_std']),                 # 标准差倍数
        ('atr_period', strategy_params['atr_period']),             # ATR周期
        ('atr_multiplier', strategy_params['atr_multiplier']),     # ATR倍数用于止盈
        ('hard_stop_loss', strategy_params['hard_stop_loss']),     # 硬止损金额
        ('contract_multiplier', BacktestConfig.CONTRACT_MULTIPLIER),   # 合约乘数
        ('printlog', BacktestConfig.PRINT_LOG),                # 是否打印日志
        ('margin_rate', BacktestConfig.MARGIN_RATE),           # 保证金比例
        # 交易保护参数
        ('opening_protection_minutes', 15),  # 开盘后保护时间（分钟）
        ('closing_protection_minutes', 2),   # 收盘前强制平仓时间（分钟）
    )
    
    def __init__(self):
        """初始化指标"""
        # 基础数据
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        
        # 布林线指标
        self.boll = bt.indicators.BollingerBands(
            self.datas[0],
            period=self.params.boll_period,
            devfactor=self.params.boll_std
        )
        
        # ATR指标
        self.atr = bt.indicators.ATR(
            self.datas[0],
            period=self.params.atr_period
        )
        
        # 记录交易信息
        self.order = None
        self.buyprice = None  # 开仓价格（买入或卖出）
        self.buycomm = None
        self.bar_executed = 0
        self.position_before_order = 0  # 记录下单前的仓位
        
        # 交易信号记录
        self.signal_triggered = False
        self.signal_type = None  # 'long' or 'short'
        self.signal_price = 0
        
        # 止损止盈线
        self.stop_loss_price = 0
        self.take_profit_price = 0
        self.trailing_stop = 0
        
        # 统计信息
        self.trade_count = 0
        self.win_count = 0
        self.loss_count = 0
        self.total_profit = 0
        self.max_profit = 0
        self.max_loss = 0
        
        # 超额亏损记录（超过硬止损的交易）
        self.excess_loss_trades = []
        
    def log(self, txt, dt=None, doprint=False):
        """日志输出"""
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} {txt}')
    
    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f'买入执行, 价格: {order.executed.price:.2f}, '
                    f'成本: {order.executed.value:.2f}, '
                    f'手续费: {order.executed.comm:.2f}'
                )
            else:
                self.log(
                    f'卖出执行, 价格: {order.executed.price:.2f}, '
                    f'成本: {order.executed.value:.2f}, '
                    f'手续费: {order.executed.comm:.2f}'
                )
            
            # 记录开仓价格（基于下单前的仓位判断）
            if self.position_before_order == 0:  # 之前没有仓位，这是开仓
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:  # 之前有仓位，这是平仓
                self.buyprice = None  # 清空开仓价格
            
            self.bar_executed = len(self)
            
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/拒绝')
        
        self.order = None
    
    def notify_trade(self, trade):
        """交易通知"""
        if not trade.isclosed:
            return
        
        # 更新统计
        self.trade_count += 1
        profit = trade.pnl
        self.total_profit += profit
        
        if profit > 0:
            self.win_count += 1
            self.max_profit = max(self.max_profit, profit)
        else:
            self.loss_count += 1
            self.max_loss = min(self.max_loss, profit)
            
            # 检查是否超过硬止损（分钟级别）
            if BacktestConfig.TIMEFRAME == 'MINUTE' and abs(profit) > self.params.hard_stop_loss:
                # 记录超额亏损交易详情
                # 计算平仓价格
                if trade.long:
                    # 多头平仓价 = 开仓价 - 亏损点数
                    close_price = trade.price + profit / self.params.contract_multiplier
                else:
                    # 空头平仓价 = 开仓价 + 亏损点数
                    close_price = trade.price - profit / self.params.contract_multiplier
                    
                trade_info = {
                    '交易编号': self.trade_count,
                    '日期时间': self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                    '交易方向': '多头' if trade.long else '空头',
                    '开仓价': trade.price,
                    '平仓价': close_price,
                    '价格变动点数': abs(close_price - trade.price),
                    '实际亏损': profit,
                    '超出金额': abs(profit) - self.params.hard_stop_loss,
                    '超出百分比': (abs(profit) - self.params.hard_stop_loss) / self.params.hard_stop_loss * 100,
                    '可能原因': '跳空导致止损失效' if abs(close_price - trade.price) > self.params.hard_stop_loss / self.params.contract_multiplier else '其他'
                }
                self.excess_loss_trades.append(trade_info)
        
        # 详细的交易信息（只在打印日志开启时显示）
        if self.params.printlog:
            self.log(f'交易关闭:')
            self.log(f'  交易方向: {"多头" if trade.long else "空头"}')
            self.log(f'  开仓价: {trade.price:.2f}')
            self.log(f'  交易量: {abs(trade.size):.0f}手')
            self.log(f'  价格变动: {abs(self.dataclose[0] - trade.price):.2f}点')
            self.log(f'  毛利润: ￥{trade.pnl:.2f}')
            self.log(f'  净利润: ￥{trade.pnlcomm:.2f}')
            self.log(f'  手续费: ￥{abs(trade.commission):.2f}')
    
    def check_boll_signal(self):
        """检查布林线交易信号 - 以收线为准"""
        if len(self) < self.params.boll_period + 2:
            return
        
        # 使用上一根已完成K线的收盘价进行判断（收线确认）
        # [0] 是当前正在形成的K线，[-1] 是上一根已完成的K线
        last_close = self.dataclose[-1]  # 上一根K线收盘价
        prev_close = self.dataclose[-2]  # 前一根K线收盘价
        
        # 上轨
        upper = self.boll.lines.top[-1]  # 上一根K线的上轨
        prev_upper = self.boll.lines.top[-2]  # 前一根K线的上轨
        
        # 中轨
        middle = self.boll.lines.mid[-1]  # 上一根K线的中轨
        
        # 下轨
        lower = self.boll.lines.bot[-1]  # 上一根K线的下轨
        prev_lower = self.boll.lines.bot[-2]  # 前一根K线的下轨
        
        # 做多信号：上一根K线收盘价突破上轨（收线确认）
        if prev_close <= prev_upper and last_close > upper:
            self.signal_triggered = True
            self.signal_type = 'long'
            self.signal_price = last_close
            self.log(f'做多信号确认: 上根K线收盘价{last_close:.2f}突破上轨{upper:.2f}')
        
        # 做空信号：上一根K线收盘价突破下轨（收线确认）
        elif prev_close >= prev_lower and last_close < lower:
            self.signal_triggered = True
            self.signal_type = 'short'
            self.signal_price = last_close
            self.log(f'做空信号确认: 上根K线收盘价{last_close:.2f}突破下轨{lower:.2f}')
    
    def check_entry_conditions(self):
        """检查开仓条件"""
        if not self.signal_triggered:
            return False
        
        # 检查交易时间保护
        if not self.is_trade_allowed():
            return False
        
        # 突破后立即开仓，不需要等待其他条件
        return True
    
    def is_trade_allowed(self):
        """检查当前时间是否允许交易"""
        # 获取当前时间
        current_dt = self.datas[0].datetime.datetime(0)
        current_time = current_dt.time()
        
        # 分钟级别才需要时间保护
        if BacktestConfig.TIMEFRAME != 'MINUTE':
            return True
        
        # 检查开盘后保护时间（09:00-09:15, 21:00-21:15）
        # 早盘开盘保护
        if current_time >= time(9, 0) and current_time < time(9, 15):
            self.log(f'早盘开盘保护期，不允许开仓 {current_dt.strftime("%H:%M:%S")}')
            return False
        
        # 夜盘开盘保护
        if current_time >= time(21, 0) and current_time < time(21, 15):
            self.log(f'夜盘开盘保护期，不允许开仓 {current_dt.strftime("%H:%M:%S")}')
            return False
        
        return True
    
    def check_force_close(self):
        """检查是否需要强制平仓（收盘前）"""
        if not self.position:
            return False
        
        # 分钟级别才需要强制平仓
        if BacktestConfig.TIMEFRAME != 'MINUTE':
            return False
        
        # 获取当前时间
        current_dt = self.datas[0].datetime.datetime(0)
        current_time = current_dt.time()
        
        # 白天收盘前强制平仓（14:58）
        if current_time >= time(14, 58) and current_time < time(15, 0):
            self.log(f'白天收盘前强制平仓 {current_dt.strftime("%H:%M:%S")}')
            return True
        
        # 夜盘收盘前强制平仓（22:58）
        if current_time >= time(22, 58) and current_time < time(23, 0):
            self.log(f'夜盘收盘前强制平仓 {current_dt.strftime("%H:%M:%S")}')
            return True
        
        return False
    
    def calculate_position_size(self):
        """计算仓位大小"""
        # 计算当前可用资金
        available_cash = self.broker.getcash()
        current_price = self.dataclose[0]
        
        # 计算每手所需保证金
        contract_value = current_price * self.params.contract_multiplier
        margin_per_lot = contract_value * self.params.margin_rate
        
        # 计算最大可开手数（考虑手续费）
        # 需要预留手续费：开仓3元 + 平仓3元 = 6元
        max_lots = int((available_cash - 6) / margin_per_lot)
        
        # 为了风险控制，每次只开1手
        # 但如果资金不足，返回0
        if max_lots >= 1:
            if self.params.printlog:
                self.log(f'可用资金: {available_cash:.2f}, 单手保证金: {margin_per_lot:.2f}, 最大可开: {max_lots}手')
            return 1
        else:
            if self.params.printlog:
                self.log(f'资金不足: 可用{available_cash:.2f}, 需要{margin_per_lot:.2f}')
            return 0
    
    def set_stop_levels(self, is_long):
        """设置止损止盈水平"""
        current_price = self.dataclose[0]
        atr_value = self.atr[0]
        
        # 判断是否使用ATR止损（日线级别推荐）
        use_atr_stop = BacktestConfig.TIMEFRAME == 'DAILY'
        
        if is_long:
            # 多头止损止盈
            if use_atr_stop:
                # 使用ATR止损（更适合日线）
                stop_distance = atr_value * 1.5  # ATR的1.5倍作为止损距离
                self.stop_loss_price = current_price - stop_distance
            else:
                # 使用固定金额止损（适合分钟线）
                self.stop_loss_price = current_price - self.params.hard_stop_loss / self.params.contract_multiplier
            
            self.take_profit_price = current_price + atr_value * self.params.atr_multiplier
            self.trailing_stop = self.stop_loss_price
        else:
            # 空头止损止盈
            if use_atr_stop:
                # 使用ATR止损（更适合日线）
                stop_distance = atr_value * 1.5  # ATR的1.5倍作为止损距离
                self.stop_loss_price = current_price + stop_distance
            else:
                # 使用固定金额止损（适合分钟线）
                self.stop_loss_price = current_price + self.params.hard_stop_loss / self.params.contract_multiplier
            
            self.take_profit_price = current_price - atr_value * self.params.atr_multiplier
            self.trailing_stop = self.stop_loss_price
    
    def update_trailing_stop(self):
        """更新移动止损"""
        if not self.position or self.buyprice is None:
            return
        
        current_price = self.dataclose[0]
        atr_value = self.atr[0]
        
        if self.position.size > 0:  # 多头
            # 盈利超过2个ATR后开始移动止损
            profit = current_price - self.buyprice
            if profit > atr_value * 2:
                new_stop = current_price - atr_value
                self.trailing_stop = max(self.trailing_stop, new_stop)
        
        elif self.position.size < 0:  # 空头
            # 盈利超过2个ATR后开始移动止损
            profit = self.buyprice - current_price
            if profit > atr_value * 2:
                new_stop = current_price + atr_value
                self.trailing_stop = min(self.trailing_stop, new_stop)
    
    def check_exit_conditions(self):
        """检查平仓条件 - 以收线为准"""
        if not self.position:
            return False
        
        # 需要至少2根K线才能判断
        if len(self) < 2:
            return False
            
        # 使用上一根已完成K线的收盘价进行判断（收线确认）
        last_close = self.dataclose[-1]  # 上一根K线收盘价
        current_price = self.dataclose[0]  # 当前价格（用于止损判断）
        middle = self.boll.lines.mid[-1]  # 上一根K线的中轨
        
        if self.position.size > 0:  # 多头
            # 1. 止损条件（盘中即可触发）
            if current_price <= self.trailing_stop:
                self.log(f'多头止损触发: 当前价格{current_price:.2f} <= 止损线{self.trailing_stop:.2f}')
                return True
            # 2. 收线回撤到中轨平仓
            if last_close <= middle:
                self.log(f'多头获利平仓: 上根K线收盘{last_close:.2f}回撤到中轨{middle:.2f}')
                return True
        
        elif self.position.size < 0:  # 空头
            # 1. 止损条件（盘中即可触发）
            if current_price >= self.trailing_stop:
                self.log(f'空头止损触发: 当前价格{current_price:.2f} >= 止损线{self.trailing_stop:.2f}')
                return True
            # 2. 收线回升到中轨平仓
            if last_close >= middle:
                self.log(f'空头获利平仓: 上根K线收盘{last_close:.2f}回升到中轨{middle:.2f}')
                return True
        
        return False
    
    def next(self):
        """策略主逻辑"""
        # 检查是否有未完成的订单
        if self.order:
            return
        
        # 首先检查是否需要强制平仓
        if self.check_force_close():
            # 记录下单前的仓位
            self.position_before_order = self.position.size
            
            if self.position.size > 0:
                self.order = self.sell()
                self.log('收盘前强制平仓多单')
            elif self.position.size < 0:
                self.order = self.buy()
                self.log('收盘前强制平仓空单')
            self.signal_triggered = False
            return
        
        # 检查布林线信号
        if not self.position:
            self.check_boll_signal()
        
        # 更新移动止损
        self.update_trailing_stop()
        
        # 检查平仓条件
        if self.check_exit_conditions():
            # 记录下单前的仓位
            self.position_before_order = self.position.size
            
            if self.position.size > 0:
                self.order = self.sell()
            elif self.position.size < 0:
                self.order = self.buy()
            self.signal_triggered = False
            return
        
        # 检查开仓条件
        if not self.position and self.check_entry_conditions():
            size = self.calculate_position_size()
            
            # 记录下单前的仓位（此时应该为0）
            self.position_before_order = 0
            
            if self.signal_type == 'long':
                self.log(f'做多开仓: 价格{self.dataclose[0]:.2f}')
                self.order = self.buy(size=size)
                self.set_stop_levels(is_long=True)
                # 日线级别显示止损信息
                if BacktestConfig.TIMEFRAME == 'DAILY' and self.params.printlog:
                    self.log(f'  止损价: {self.stop_loss_price:.2f} (ATR止损)')
                    self.log(f'  止盈价: {self.take_profit_price:.2f}')
                    self.log(f'  ATR值: {self.atr[0]:.2f}')
            
            elif self.signal_type == 'short':
                self.log(f'做空开仓: 价格{self.dataclose[0]:.2f}')
                self.order = self.sell(size=size)
                self.set_stop_levels(is_long=False)
                # 日线级别显示止损信息
                if BacktestConfig.TIMEFRAME == 'DAILY' and self.params.printlog:
                    self.log(f'  止损价: {self.stop_loss_price:.2f} (ATR止损)')
                    self.log(f'  止盈价: {self.take_profit_price:.2f}')
                    self.log(f'  ATR值: {self.atr[0]:.2f}')
            
            self.signal_triggered = False
    
    def stop(self):
        """策略结束时的统计输出"""
        # 保存超额亏损交易到文件
        if self.excess_loss_trades:
            import json
            import os
            from datetime import datetime
            
            # 创建输出文件名
            output_dir = os.path.dirname(__file__)
            output_file = os.path.join(output_dir, f'excess_loss_trades_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
            
            # 保存到JSON文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    '回测配置': {
                        '时间周期': BacktestConfig.TIMEFRAME,
                        '回测时间': f'{BacktestConfig.START_DATE} 至 {BacktestConfig.END_DATE}',
                        '硬止损金额': self.params.hard_stop_loss,
                        '初始资金': BacktestConfig.INITIAL_CASH
                    },
                    '超额亏损交易总数': len(self.excess_loss_trades),
                    '超额亏损交易详情': self.excess_loss_trades,
                    '分析摘要': {
                        '总超额亏损金额': sum(abs(t['实际亏损']) - self.params.hard_stop_loss for t in self.excess_loss_trades),
                        '平均超额亏损': sum(t['超出金额'] for t in self.excess_loss_trades) / len(self.excess_loss_trades) if self.excess_loss_trades else 0,
                        '最大超额亏损': max((t['超出金额'] for t in self.excess_loss_trades), default=0),
                        '最大超额亏损百分比': max((t['超出百分比'] for t in self.excess_loss_trades), default=0)
                    }
                }, f, ensure_ascii=False, indent=2)
            
            print(f'\n警告: 发现 {len(self.excess_loss_trades)} 笔超额亏损交易！')
            print(f'详细信息已保存到: {output_file}')
            
            # 打印摘要信息
            print(f'\n【超额亏损交易摘要】')
            print(f'  超额亏损交易数: {len(self.excess_loss_trades)} 笔')
            print(f'  占总亏损交易比例: {len(self.excess_loss_trades) / self.loss_count * 100:.2f}%' if self.loss_count > 0 else '0%')
            print(f'  最大单笔超额亏损: ￥{max((t["超出金额"] for t in self.excess_loss_trades), default=0):.2f}')
            print(f'  平均超额亏损: ￥{sum(t["超出金额"] for t in self.excess_loss_trades) / len(self.excess_loss_trades):.2f}')
            
            # 打印前5笔最严重的超额亏损
            print(f'\n【最严重的超额亏损（前5笔）】')
            sorted_losses = sorted(self.excess_loss_trades, key=lambda x: x['超出金额'], reverse=True)[:5]
            for i, trade in enumerate(sorted_losses, 1):
                print(f'  {i}. 时间: {trade["日期时间"]}')
                print(f'     方向: {trade["交易方向"]}, 开仓: {trade["开仓价"]:.2f}, 平仓: {trade["平仓价"]:.2f}')
                print(f'     实际亏损: ￥{trade["实际亏损"]:.2f}, 超出: ￥{trade["超出金额"]:.2f} ({trade["超出百分比"]:.1f}%)')
        
        # 始终显示策略统计信息
        print('\n' + '=' * 60)
        print('【策略执行统计】')
        print(f'  总交易次数: {self.trade_count} 笔')
        
        if self.trade_count > 0:
            print(f'  盈利次数: {self.win_count} 笔')
            print(f'  亏损次数: {self.loss_count} 笔')
            win_rate = self.win_count / self.trade_count * 100
            print(f'  胜率: {win_rate:.2f}%')
            print(f'  总盈亏: ￥{self.total_profit:.2f}')
            print(f'  最大单笔盈利: ￥{self.max_profit:.2f}')
            print(f'  最大单笔亏损: ￥{self.max_loss:.2f}')
            
            # 计算平均盈亏
            if self.win_count > 0:
                avg_win = (self.total_profit + abs(self.max_loss * self.loss_count)) / self.win_count
                print(f'  平均盈利: ￥{avg_win:.2f}')
            if self.loss_count > 0:
                avg_loss = self.max_loss * self.loss_count / self.loss_count
                print(f'  平均亏损: ￥{avg_loss:.2f}')
        else:
            print('  没有执行任何交易')
        print('=' * 60)


def run_backtest():
    """运行回测 - 使用配置类中的参数"""
    # 创建Cerebro引擎
    cerebro = bt.Cerebro()
    
    # 添加策略
    cerebro.addstrategy(BollStrategy)
    
    # 读取数据
    datapath = os.path.join(os.path.dirname(__file__), BacktestConfig.DATA_FILE)
    print(f'=' * 60)
    print(f'布林线策略回测程序')
    print(f'=' * 60)
    print(f'配置信息:')
    print(f'  数据周期: {BacktestConfig.TIMEFRAME}')
    print(f'  回测时间: {BacktestConfig.START_DATE} 至 {BacktestConfig.END_DATE}')
    print(f'  初始资金: {BacktestConfig.INITIAL_CASH:,}')
    print(f'  手续费: 每手{BacktestConfig.COMMISSION}元')
    print(f'  数据文件: {datapath}')
    
    # 日线级别特别提示
    if BacktestConfig.TIMEFRAME == 'DAILY':
        print(f'-' * 60)
        print(f'注意: 日线级别回测注意事项:')
        print(f'  1. 使用ATR动态止损（1.5倍ATR）')
        print(f'  2. 日线波动大，单笔亏损可能超过预期')
        print(f'  3. 建议使用更长的回测周期（1年以上）')
        print(f'  4. 止损可能因跳空而无法精确执行')
    
    print(f'-' * 60)
    
    # 读取CSV数据
    df = pd.read_csv(datapath)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    
    # 过滤时间范围
    df = df[df.index >= BacktestConfig.START_DATE]
    df = df[df.index <= BacktestConfig.END_DATE]
    
    # 如果是日线级别，需要将分钟数据转换为日线
    if BacktestConfig.TIMEFRAME == 'DAILY':
        print(f'转换数据到日线级别...')
        # 重采样到日线
        df_daily = df.resample('D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'money': 'sum',
            'open_interest': 'last'
        })
        # 去除空值（非交易日）
        df = df_daily.dropna()
        print(f'日线数据记录数: {len(df):,}')
    else:
        print(f'分钟数据记录数: {len(df):,}')
    
    print(f'实际日期范围: {df.index[0]} 到 {df.index[-1]}')
    print(f'=' * 60)
    
    # 创建数据源
    data = bt.feeds.PandasData(
        dataname=df,
        datetime=None,
        open='open',
        high='high',
        low='low',
        close='close',
        volume='volume',
        openinterest='open_interest'
    )
    
    # 添加数据到Cerebro
    cerebro.adddata(data)
    
    # 设置初始资金
    cerebro.broker.setcash(BacktestConfig.INITIAL_CASH)
    
    # *** 重要：设置期货合约的参数 ***
    # 设置期货合约规格（菜籽油）
    # 使用自定义的CommissionInfo来正确设置期货合约
    from backtrader.comminfo import CommInfoBase
    
    class RapeseedOilCommInfo(CommInfoBase):
        params = (
            ('stocklike', False),  # 期货
            ('commtype', CommInfoBase.COMM_FIXED),  # 固定手续费
            ('percabs', False),  # 不是百分比
            ('interest', 0),  # 无利息
        )
        
        def _getcommission(self, size, price, pseudoexec):
            '''每手固定3元手续费'''
            return abs(size) * BacktestConfig.COMMISSION
            
        def get_margin(self, price):
            '''保证金 = 合约价值 * 9%'''
            return price * BacktestConfig.CONTRACT_MULTIPLIER * BacktestConfig.MARGIN_RATE
    
    # 设置合约乘数和佣金信息
    comminfo = RapeseedOilCommInfo(
        mult=BacktestConfig.CONTRACT_MULTIPLIER,  # 合约乘数
    )
    cerebro.broker.addcommissioninfo(comminfo)
    
    # 添加分析器
    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(btanalyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(btanalyzers.Returns, _name='returns')
    cerebro.addanalyzer(btanalyzers.TradeAnalyzer, _name='trades')
    
    # 打印初始资金
    print(f'\n开始回测...')
    print(f'初始资金: {cerebro.broker.getvalue():,.2f}')
    print(f'保证金比例: {BacktestConfig.MARGIN_RATE:.1%}')
    print(f'手续费: 每手{BacktestConfig.COMMISSION}元（开平各收）')
    
    # 运行回测
    results = cerebro.run()
    strat = results[0]
    
    # 打印最终资金
    final_value = cerebro.broker.getvalue()
    initial_cash = BacktestConfig.INITIAL_CASH
    profit = final_value - initial_cash
    profit_rate = profit / initial_cash * 100
    
    print(f'\n回测完成!')
    print(f'=' * 60)
    print(f'【资金统计】')
    print(f'  初始资金: ￥{initial_cash:,.2f}')
    print(f'  最终资金: ￥{final_value:,.2f}')
    print(f'  总收益: ￥{profit:,.2f}')
    print(f'  收益率: {profit_rate:.2f}%')
    
    # 打印分析结果
    print(f'\n{"="*60}')
    print(f'【风险指标】')
    
    # 最大回撤
    drawdown = strat.analyzers.drawdown.get_analysis()
    print(f'  最大回撤率: {drawdown["max"]["drawdown"]:.2f}%')
    print(f'  最大回撤金额: ￥{drawdown["max"]["moneydown"]:.2f}')
    
    # Sharpe Ratio
    sharpe = strat.analyzers.sharpe.get_analysis()
    if sharpe.get('sharperatio'):
        print(f'  夏普比率: {sharpe["sharperatio"]:.3f}')
    
    # 交易统计
    trades = strat.analyzers.trades.get_analysis()
    if trades.get('total'):
        total_trades = trades['total']['total']
        if total_trades > 0:
            print(f'\n{"="*60}')
            print(f'【交易统计】')
            print(f'  总交易次数: {total_trades} 笔')
            
            # 盈亏统计
            won_trades = trades.get("won", {}).get("total", 0)
            lost_trades = trades.get("lost", {}).get("total", 0)
            win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0
            
            print(f'  盈利交易: {won_trades} 笔')
            print(f'  亏损交易: {lost_trades} 笔')
            print(f'  胜率: {win_rate:.1f}%')
            
            # 盈利交易详情
            if trades.get('won', {}).get('total', 0) > 0:
                avg_win = trades["won"]["pnl"]["average"]
                max_win = trades["won"]["pnl"]["max"]
                total_win = trades["won"]["pnl"]["total"]
                
                print(f'\n  【盈利交易分析】')
                print(f'    平均盈利: ￥{avg_win:.2f}/笔')
                print(f'    最大盈利: ￥{max_win:.2f} (单笔)')
                print(f'    总盈利额: ￥{total_win:.2f}')
            
            # 亏损交易详情
            if trades.get('lost', {}).get('total', 0) > 0:
                avg_loss = trades["lost"]["pnl"]["average"]
                max_loss = trades["lost"]["pnl"]["max"]
                total_loss = trades["lost"]["pnl"]["total"]
                
                print(f'\n  【亏损交易分析】')
                print(f'    平均亏损: ￥{avg_loss:.2f}/笔')
                print(f'    最大亏损: ￥{max_loss:.2f} (单笔)')
                print(f'    总亏损额: ￥{total_loss:.2f}')
            
            # 盈亏比
            if won_trades > 0 and lost_trades > 0:
                avg_win = trades["won"]["pnl"]["average"]
                avg_loss = abs(trades["lost"]["pnl"]["average"])
                profit_factor = avg_win / avg_loss if avg_loss != 0 else 0
                
                print(f'\n  【盈亏比分析】')
                print(f'    盈亏比: {profit_factor:.2f} (平均盈利/平均亏损)')
                print(f'    期望值: ￥{(won_trades * avg_win + lost_trades * trades["lost"]["pnl"]["average"]) / total_trades:.2f}/笔')
    
    # 添加术语说明和风险提示
    print(f'\n{"="*60}')
    print(f'【术语说明】')
    print(f'  * 所有金额单位均为人民币（元）')
    print(f'  * 点位指价格变动的最小单位')
    print(f'  * 1手菜籽油 = {BacktestConfig.CONTRACT_MULTIPLIER}吨')
    print(f'  * 盈亏计算 = (卖出价-买入价) × 合约乘数 × 手数')
    print(f'  * 例如: 价格涨10个点，1手盈利 = 10 × {BacktestConfig.CONTRACT_MULTIPLIER} = {10 * BacktestConfig.CONTRACT_MULTIPLIER}元')
    
    # 根据数据周期显示不同的风险提示
    if BacktestConfig.TIMEFRAME == 'DAILY':
        print(f'\n【日线级别风险说明】')
        print(f'  * 日线止损使用ATR动态止损（1.5倍ATR）')
        print(f'  * 实际亏损可能因跳空超过预设止损')
        print(f'  * 最大亏损 = 开盘跳空幅度 × 合约乘数')
        strategy_params = BacktestConfig.get_strategy_params()
        print(f'  * 预设止损参考值: {strategy_params["hard_stop_loss"]}元（仅供参考）')
    else:
        print(f'\n【分钟级别风险说明】')
        strategy_params = BacktestConfig.get_strategy_params()
        print(f'  * 分钟止损使用固定金额: {strategy_params["hard_stop_loss"]}元')
        print(f'  * 止损执行相对及时精确')
    
    print(f'{"="*60}')
    
    # 绘制图表（根据配置决定是否显示）
    if BacktestConfig.PLOT_CHART:
        print('\n正在生成图表...')
        cerebro.plot(style='candlestick', volume=False)


def main():
    """主函数 - 直接运行回测，使用配置文件中的参数"""
    print(f'\n{"="*60}')
    print(f'布林线策略回测程序 v2.0')
    print(f'{"="*60}')
    print(f'\n提示: 修改 BacktestConfig 类中的参数来调整回测配置')
    
    # 获取当前策略参数
    strategy_params = BacktestConfig.get_strategy_params()
    
    print(f'当前配置:')
    print(f'  - 数据周期: {BacktestConfig.TIMEFRAME}')
    print(f'  - 回测时间: {BacktestConfig.START_DATE} 至 {BacktestConfig.END_DATE}')
    print(f'  - 初始资金: {BacktestConfig.INITIAL_CASH:,}')
    print(f'\n策略参数({BacktestConfig.TIMEFRAME}级别):')
    print(f'  - 布林线周期: {strategy_params["boll_period"]}')
    print(f'  - 标准差倍数: {strategy_params["boll_std"]}')
    print(f'  - ATR周期: {strategy_params["atr_period"]}')
    print(f'  - 硬止损: {strategy_params["hard_stop_loss"]}元')
    print(f'{"="*60}\n')
    
    # 运行回测
    run_backtest()


if __name__ == '__main__':
    main()