import pandas as pd

import environment
from micro_defs import Direction
import matplotlib.pyplot as plt
import logging

from wechat_helper import WeChatHelper

AU_CONTRACT_MULTIPLIER = 1000  # 黄金等合约乘数

class PowerWaveBacktrace:
    """
    用于计算和打印动力波策略绩效的工具类，重构为直接使用 vectorbt Portfolio。
    """

    @staticmethod
    def report_performance(strategy, output_type='print'):
        """
        打印最终绩效并保存图表（PNG和交互式HTML）
        """
        if strategy.total_portfolio is None or strategy.total_portfolio.trades.count() == 0:
            print("没有产生任何交易信号")
            return

        # 用信号序列重建明细
        entries_series = strategy.signal_manager.get_entries()
        exits_series = strategy.signal_manager.get_exits()
        close_series = strategy.signal_manager.get_close()
        direction_series = strategy.signal_manager.get_directions()

        trades = []
        entry_time = None
        entry_price = None
        entry_direction = None

        for time in entries_series.index:
            is_entry = entries_series[time]
            is_exit = exits_series[time]
            price = close_series[time]
            direction = direction_series[time] if time in direction_series else None

            if is_entry:
                entry_time = time
                entry_price = price
                entry_direction = direction
            elif is_exit and entry_time is not None:
                if entry_direction == 1:
                    profit = (price - entry_price) * AU_CONTRACT_MULTIPLIER
                    dir_str = '多头'
                elif entry_direction == -1:
                    profit = (entry_price - price) * AU_CONTRACT_MULTIPLIER
                    dir_str = '空头'
                else:
                    profit = 0
                    dir_str = '未知'
                trades.append({
                    "开仓时间": entry_time,
                    "平仓时间": time,
                    "方向": dir_str,
                    "开仓价": round(entry_price, 4),
                    "平仓价": round(price, 4),
                    "收益金额": round(profit, 2),
                    "收益率(%)": None  # 可后续补充
                })
                entry_time = None
                entry_price = None
                entry_direction = None

        report_df = pd.DataFrame(trades)

        if output_type == 'df':
            return report_df

        if output_type == 'print':
            total_trades = len(report_df)
            winning_trades = len(report_df[report_df['收益金额'] > 0])
            win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0

            if winning_trades > 0 and (total_trades - winning_trades) > 0:
                avg_win = report_df[report_df['收益金额'] > 0]['收益金额'].mean()
                avg_loss = abs(report_df[report_df['收益金额'] < 0]['收益金额'].mean())
                profit_ratio = avg_win / avg_loss
            else:
                profit_ratio = float('nan')

            print("=" * 60)
            print(f"{'交易战报':^60}")
            print("=" * 60)
            print(f"总交易次数: {total_trades} | 胜率: {win_rate:.2f}%")
            print("-" * 60)
            print(report_df.to_string(index=False))

            total_profit = report_df['收益金额'].sum()
            avg_profit = total_profit / total_trades if total_trades > 0 else 0
            sharpe_ratio = strategy.total_portfolio.sharpe_ratio()

            print("\n" + "=" * 60)
            print(f"{'业绩总结':^60}")
            print("=" * 60)
            print(f"总利润: {total_profit:.2f} | 平均每笔盈利: {avg_profit:.2f}")
            print(f"最大单笔盈利: {report_df['收益金额'].max():.2f}")
            print(f"最大单笔亏损: {report_df['收益金额'].min():.2f}")
            print(f"盈亏比: {profit_ratio:.2f}:1")
            print(f"夏普比率: {sharpe_ratio:.2f}")

    @staticmethod
    def broadcast_daily_performance(strategy):
        """播报当日交易绩效"""
        if strategy.total_portfolio is None or len(strategy.total_portfolio.trades.records) == 0:
            return

        # 使用实际记录的交易数据
        entries_series = strategy.signal_manager.get_entries()
        exits_series = strategy.signal_manager.get_exits()
        close_series = strategy.signal_manager.get_close()
        direction_series = strategy.signal_manager.get_directions()

        trades = []
        entry_time = None
        entry_price = None
        entry_direction = None

        for time in entries_series.index:
            is_entry = entries_series[time]
            is_exit = exits_series[time]
            price = close_series[time]
            direction = direction_series[time] if time in direction_series else None

            if is_entry:
                entry_time = time
                entry_price = price
                entry_direction = direction
            elif is_exit and entry_time is not None:
                # 计算盈亏
                if entry_direction == 1:
                    profit = (price - entry_price) * AU_CONTRACT_MULTIPLIER
                    dir_str = '多'
                elif entry_direction == -1:
                    profit = (entry_price - price) * AU_CONTRACT_MULTIPLIER
                    dir_str = '空'
                else:
                    profit = 0
                    dir_str = '未知'
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': time,
                    'entry_price': entry_price,
                    'exit_price': price,
                    'direction': dir_str,
                    'profit': profit
                })
                entry_time = None
                entry_price = None
                entry_direction = None

        if not trades:
            return

        # 计算统计数据
        total_trades = len(trades)
        win_count = sum(1 for t in trades if t['profit'] > 0)
        win_rate = win_count / total_trades * 100 if total_trades > 0 else 0
        total_profit = sum(t['profit'] for t in trades)

        # 生成播报消息
        msg = f"【交易播报】\n"
        msg += f"总交易次数：{total_trades}\n"
        msg += f"盈利次数：{win_count}\n"
        msg += f"胜率：{win_rate:.1f}%\n"
        msg += f"总盈亏：{total_profit:.2f}元\n\n"

        # 添加每笔交易明细
        msg += "交易明细：\n"
        for t in trades:
            msg += f"开仓时间：{t['entry_time'].strftime('%H:%M:%S')} | "
            msg += f"平仓时间：{t['exit_time'].strftime('%H:%M:%S')} | "
            msg += f"方向：{t['direction']} | "
            msg += f"开仓价：{t['entry_price']:.2f} | "
            msg += f"平仓价：{t['exit_price']:.2f} | "
            msg += f"盈亏：{t['profit']:.2f}元\n"

        # 发送消息
        wx_helper = WeChatHelper()
        wx_helper.send_message_to_multiple_recipients(msg, [environment.group_chat_name_dlb,
                                                          environment.group_chat_name])
