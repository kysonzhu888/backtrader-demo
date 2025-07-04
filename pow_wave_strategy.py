import environment
from color_change_close_confirmer import ColorChangeCloseConfirmer
from color_change_pending_manager import ColorChangePendingManager
from pow_data_stream_generator import PowDataStreamGenerator
from power_status import PowerStatus, IntradayStatus
from power_wave import PowerWave
import pandas as pd
import vectorbt as vbt
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import time
from logger_utils import Logger
import matplotlib
import os
import numpy as np

from micro_defs import BarColor
import logging

from signal_series_manager import SignalSeriesManager
from wechat_helper import WeChatHelper
from threading import Timer
from date_utils import DateUtils
from trading_time_helper import TradingTimeHelper
from power_wave_backtrace import PowerWaveBacktrace, AU_CONTRACT_MULTIPLIER
from back_trace_paradigm import DebugTimeManager

matplotlib.use('Agg')  # 使用 Agg 后端
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 设置中文字体
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

INITIAL_STOP_LOSS = 0.75

# 保本止损相关参数
BREAKEVEN_INITIAL_STOP = 666  # 初始止损金额
BREAKEVEN_THRESHOLDS = [3000, 2000, 1200, 666]  # 浮盈阈值，降序排列
BREAKEVEN_PROFITS = [1800, 1000, 500, 0]  # 对应的保本金额（与阈值一一对应，最后一个为0表示0.25点）
BREAKEVEN_POINT_OFFSET = 0.25  # 最低保本点数


# ======================
# 2. 实时策略类（动力波策略）
# ======================
class StreamingStrategy:
    def __init__(self, warmup_period=34, product_type=None, interval='1min'):
        """
        动力波策略
        参数:
            warmup_period: 预热期（需要至少34根K线计算指标）
            product_type: 品种类型（用于判断收盘时间）
            interval: 当前周期（如1min、5min等）
        """
        self.data_window = pd.DataFrame()
        self.position = 0  # 0:空仓, 1:多仓
        self.warmup = warmup_period
        self.product_type = product_type
        self.interval = interval
        self.trading_helper = TradingTimeHelper(product_type) if product_type else None
        self.power_wave = PowerWave()
        self.intraday_status = IntradayStatus()
        self.macd = None  # MACD指标
        self.last_loss_time = None  # 记录上一次亏损平仓的时间
        self.cur_stop_price = None  # 当前止损价
        self.total_portfolio = None  # 只在需要时生成
        self.color_change_manager = ColorChangePendingManager()
        self.signal_manager = SignalSeriesManager()

    def minutes_to_session_close(self, cur_time):
        """
        返回当前K线距离本交易时段收盘的分钟数。
        """
        trading_time_helper = TradingTimeHelper(product_type=self.product_type)
        end_dt = trading_time_helper.get_current_session_end_time(cur_time)
        if end_dt is None:
            return None
        return (end_dt - cur_time).total_seconds() / 60

    def can_open_position(self, cur_time, min_minutes=15):
        """
        判断当前是否允许开仓（距离收盘min_minutes分钟内不允许开仓，开盘后min_minutes分钟内不允许开仓）。
        """
        if self.position != 0 or self.trading_helper is None:
            return True
        # 检查距离收盘时间
        minutes_left = self.minutes_to_session_close(cur_time)
        if minutes_left is not None and minutes_left <= min_minutes:
            msg = f"[power wave] 时间：{cur_time}，距离收盘{minutes_left:.1f}分钟，不允许开新仓"
            logging.debug(msg)
            return False
        # 检查开盘后时间
        session_start = self.trading_helper.get_current_session_start_time(cur_time)
        if session_start is not None:
            minutes_after_open = (cur_time - session_start).total_seconds() / 60
            if 0 < minutes_after_open <= min_minutes:
                msg = f"[power wave] 时间：{cur_time}，开盘后{minutes_after_open:.1f}分钟，不允许开新仓"
                logging.debug(msg)
                return False
        return True

    def format_broadcast_msg(self, cur_status, new_data):
        msg_head = f"【动力波信号播报】\n品种：{self.product_type}  周期：{self.interval}  时间：{new_data.name}\n"
        if cur_status is not None:
            return msg_head + cur_status
        else:
            return msg_head

    def on_new_bar(self, new_data):
        """主流程优化：早返回+子函数拆分，减少嵌套"""
        if new_data is None:
            return None
        status = self._calc_status()
        self._append_data(new_data, status)

        if not self._is_warmup_ok():
            return None
        cur_time = new_data.name
        status = self._calc_status()
        logging.info(f"{cur_time} ->status.intraday_ok:{status.intraday_ok},intraday_price:{status.intraday_price}")

        minutes_left = self.minutes_to_session_close(cur_time)

        # 1. 收盘前强平
        if self._should_force_close(minutes_left):
            self._handle_force_close(status, new_data, minutes_left)
            return

        # 2. 收盘前播报
        if self._should_broadcast(minutes_left):
            self._broadcast_performance()
            self._clear_orders_if_needed()
            # 不return，继续处理信号

        # 3. 空仓时的开仓逻辑
        if self.position == 0:
            if not self.can_open_position(cur_time):
                return 0.0
            if self._should_open(status, cur_time):
                self._handle_open(status, new_data)
            else:
                self._handle_no_open(status, new_data)
            return

        # 4. 持仓时的风控和平仓逻辑
        if self._check_breakeven(new_data):
            self._handle_breakeven_close(new_data)
            return
        if self._should_color_change_close(status):
            self._handle_color_change_close(status, new_data)
            return

        # 5. 其它情况
        self._handle_hold(status, new_data)

    # ===== 以下为子函数实现 =====
    def _append_data(self, new_data, status=None):
        row = new_data.to_frame().T
        if status is not None:
            row['color'] = status.color_state.current_color
            row['bar_height'] = status.bar_height
        self.data_window = pd.concat([self.data_window, row]).iloc[-50000:]

    def _is_warmup_ok(self):
        return len(self.data_window) >= self.warmup

    def _calc_status(self):
        self.power_wave.update(self.data_window)
        self.macd = vbt.MACD.run(self.power_wave.close, fast_window=12, slow_window=26, signal_window=9)
        self.intraday_status.update(self.data_window)
        return PowerStatus(self.power_wave, self.macd, self.intraday_status)

    def _should_force_close(self, minutes_left):
        return self.position != 0 and minutes_left is not None and 1 < minutes_left <= 2

    def _handle_force_close(self, status, new_data, minutes_left):
        signal, profit, msg = self.close_position(status, f"收盘前{minutes_left}分钟", new_data)
        wx_helper = WeChatHelper()
        wx_helper.send_message_to_multiple_recipients(msg,
                                                      [environment.group_chat_name_dlb, environment.group_chat_name_vip])

    def _should_broadcast(self, minutes_left):
        return minutes_left is not None and 0 < minutes_left <= 1

    def _broadcast_performance(self):
        self.build_total_portfolio()

        if len(self.signal_manager.exits_series) > 0:
            msg = PowerWaveBacktrace.broadcast_daily_performance(self)
            wx_helper = WeChatHelper()
            wx_helper.send_message_to_multiple_recipients(msg,
                                                      [environment.group_chat_name_dlb, environment.group_chat_name_vip])

    def _clear_orders_if_needed(self):
        if os.getenv('DEBUG_MODE') == '0':
            self.signal_manager.clear()
            self.total_portfolio = None

    def _should_open(self, status, cur_time):
        if status.is_all_conditions_met():
            if self.last_loss_time is not None:
                if (cur_time - self.last_loss_time).total_seconds() < 30 * 60:
                    sts_msg = f"上一单亏损，半小时内不允许开仓，剩余{(30 * 60 - (cur_time - self.last_loss_time).total_seconds()) / 60:.1f}分钟"
                    loss_msg = self.format_broadcast_msg(cur_status=sts_msg, new_data=self.data_window.iloc[-1])
                    wx_helper = WeChatHelper()
                    wx_helper.send_message_to_multiple_recipients(loss_msg, [environment.group_chat_name_dlb,
                                                                             environment.group_chat_name_vip])
                    return False
            return True
        return False

    def _handle_open(self, status, new_data):
        is_red = status.color_state.current_color == BarColor.RED.value
        signal = 1.0 if is_red else -1.0
        msg = self.format_broadcast_msg(
            f"上一根颜色：{status.color_state.prev_color}，当前颜色：{status.color_state.current_color}\n当前百分位 {status.percentile:.2f}，MACD:{'满足' if status.macd_ok else '未满足'}，布林:{'满足' if status.boll_ok else '未满足'}，日均线：{'满足' if status.intraday_ok else '未满足'}。",
            new_data)
        msg += "\n满足开仓条件，开仓方向：" + status.direction + "\n开仓价格：" + str(new_data.Close)
        wx_helper = WeChatHelper()
        wx_helper.send_message_to_multiple_recipients(msg,
                                                      [environment.group_chat_name_dlb, environment.group_chat_name_vip])
        self._do_trade(signal, new_data)

    def _handle_no_open(self, status, new_data):
        if status.valid_percentile and status.color_state.current_color != status.color_state.prev_color:
            msg = self.format_broadcast_msg(
                f"上一根颜色：{status.color_state.prev_color}，当前颜色：{status.color_state.current_color}\n当前百分位 {status.percentile:.2f}，MACD:{'满足' if status.macd_ok else '未满足'}，布林:{'满足' if status.boll_ok else '未满足'}，日均线：{'满足' if status.intraday_ok else '未满足'}。",
                new_data)
            msg += "颜色发生变化了，可以关注起来了。(注意：不意味着可以开单！)"
            wx_helper = WeChatHelper()
            wx_helper.send_message(msg, "动力波策略群")
        else:
            logging.debug(f"[power wave] 时间：{new_data.name} 不满足开仓条件，保持空仓")

    def _check_breakeven(self, new_data):
        stop_triggered, _ = self.check_and_move_stop_to_breakeven(new_data)
        return stop_triggered

    def _handle_breakeven_close(self, new_data):
        if self.position == 0:
            logging.error("报错了，没单怎么平仓")
        self._do_trade(-1.0 if self.position > 0 else 1.0, new_data, force_stop_price=True)

    def _should_color_change_close(self, status):
        if self.position == 0:
            self.color_change_manager.reset()
            return False
        cur_color = status.color_state.current_color
        position_color = BarColor.GREEN.value if self.position < 0 else BarColor.RED.value
        return self.color_change_manager.update(cur_color, position_color, status.bar_height)

    def _handle_color_change_close(self, status, new_data):
        signal, _, msg = self.close_position(status=status, cur_status_msg=None, new_data=new_data)
        wx_helper = WeChatHelper()
        wx_helper.send_message_to_multiple_recipients(msg,
                                                      [environment.group_chat_name_dlb, environment.group_chat_name_vip])

    def _handle_hold(self, status, new_data):
        # 可根据需要添加持仓时的其它处理逻辑
        pass

    def _do_trade(self, signal, new_data, force_stop_price=False):
        pre_postion = self.position
        if signal != 0:
            if signal > 0 and self.position == 0:  # 开多仓
                stop_price = new_data.Close - BREAKEVEN_INITIAL_STOP / AU_CONTRACT_MULTIPLIER
                self.signal_manager.record_entry(new_data.name, new_data.Close, direction=1, stop_price=stop_price)
                self.position = 1
                self.cur_stop_price = stop_price

            elif signal < 0 and self.position == 0:  # 开空仓
                stop_price = new_data.Close + BREAKEVEN_INITIAL_STOP / AU_CONTRACT_MULTIPLIER
                self.signal_manager.record_entry(new_data.name, new_data.Close, direction=-1, stop_price=stop_price)
                self.position = -1
                self.cur_stop_price = stop_price

            elif signal < 0 and self.position > 0:  # 平多仓
                exit_price = self.cur_stop_price if force_stop_price else new_data.Close
                entry_price = self.signal_manager.get_close().iloc[-1]
                self.signal_manager.record_exit(new_data.name, exit_price)
                if exit_price < entry_price:
                    self.last_loss_time = new_data.name
                self.position = 0
                self.cur_stop_price = None

            elif signal > 0 and self.position < 0:  # 平空仓
                exit_price = self.cur_stop_price if force_stop_price else new_data.Close
                entry_price = self.signal_manager.get_close().iloc[-1]
                self.signal_manager.record_exit(new_data.name, exit_price)
                if exit_price > entry_price:
                    self.last_loss_time = new_data.name
                self.position = 0
                self.cur_stop_price = None

            aft_postion = self.position
            return pre_postion, aft_postion

    def build_total_portfolio(self):
        """根据当前信号序列生成/刷新 portfolio"""
        if len(self.signal_manager.get_close()) == 0:
            self.total_portfolio = None
            return
        self.total_portfolio = vbt.Portfolio.from_signals(
            close=self.signal_manager.get_close(),
            entries=self.signal_manager.get_entries(),
            exits=self.signal_manager.get_exits(),
            init_cash=100000,
            fees=0,
            size=1,  # 每次只做一手，盈亏后处理时统一乘以合约乘数
            freq='1min'
        )

    def close_position(self, status, cur_status_msg, new_data):
        signal = 1.0 if status.color_state.current_color == BarColor.RED.value else -1.0
        pre_position, _ = self._do_trade(signal=signal, new_data=new_data)

        msg = self.format_broadcast_msg(cur_status_msg, new_data) + "满足平仓条件，执行平仓"
        profit = 0  # 默认值
        # 盈亏计算
        if len(self.signal_manager.get_close()) > 0:
            entry_price = self.signal_manager.get_close().iloc[-2]
            long_profit = (new_data.Close - entry_price) * AU_CONTRACT_MULTIPLIER
            short_profit = (entry_price - new_data.Close) * AU_CONTRACT_MULTIPLIER
            profit = long_profit if pre_position > 0 else short_profit
            msg += f"\n开仓价格：{entry_price:.2f} 元，平仓价格：{new_data.Close:.2f} 元"
            msg += f"\n本单盈利：{profit:.2f} 元"

        return signal, profit, msg

    def check_and_move_stop_to_breakeven(self, new_data):
        """
        推保本逻辑：浮盈超过666元时止损上移到开仓价，若价格回落到止损价则自动平仓
        新增：浮盈超过1200/2000/3000时，止损价分别推到500/1000/1800元
        返回：是否触发保本止损（True/False），以及是否刚刚推保本（True/False）
        """
        if self.position == 0 or len(self.signal_manager.get_close()) == 0:
            return False, False

        entry_price = self.signal_manager.get_close().iloc[-1]
        cur_high = new_data.High
        cur_low = new_data.Low
        floating_profit = (cur_high - entry_price) * AU_CONTRACT_MULTIPLIER if self.position > 0 else (
                                                                                                              entry_price - cur_low) * AU_CONTRACT_MULTIPLIER

        # 亏损超过初始止损，止损
        stop_triggered = False
        if (self.position > 0 and cur_low <= self.cur_stop_price) or (
                self.position < 0 and cur_high >= self.cur_stop_price):
            stop_triggered = True

        if stop_triggered:
            long_profit = (self.cur_stop_price - entry_price) * AU_CONTRACT_MULTIPLIER
            short_profit = (entry_price - self.cur_stop_price) * AU_CONTRACT_MULTIPLIER
            profit = long_profit if self.position > 0 else short_profit

            msg = self.format_broadcast_msg("价格触及止损价，自动平仓", new_data)
            gain_or_loss = "盈利" if profit > 0 else "亏损"
            msg += f"\n开仓价：{entry_price:.2f}，止损价：{self.cur_stop_price:.2f}，本单{gain_or_loss} {profit:.2f}元"
            logging.info(msg)
            wx_helper = WeChatHelper()
            wx_helper.send_message_to_multiple_recipients(msg, [environment.group_chat_name_dlb,
                                                                environment.group_chat_name_vip])
            return True, False

        # 推保本逻辑
        new_stop = self.cur_stop_price
        just_moved = False
        for threshold, profit in zip(BREAKEVEN_THRESHOLDS, BREAKEVEN_PROFITS):
            if floating_profit >= threshold:
                if profit == 0:
                    candidate = entry_price + BREAKEVEN_POINT_OFFSET if self.position > 0 else entry_price - BREAKEVEN_POINT_OFFSET
                else:
                    candidate = entry_price + profit / AU_CONTRACT_MULTIPLIER if self.position > 0 else entry_price - profit / AU_CONTRACT_MULTIPLIER
                if (self.position > 0 and candidate > self.cur_stop_price) or (
                        self.position < 0 and candidate < self.cur_stop_price):
                    new_stop = candidate
                    just_moved = True
                break  # 只推到最高档位

        if just_moved and new_stop != self.cur_stop_price:
            self.cur_stop_price = new_stop
            self.signal_manager.update_stop(new_data.name, new_stop)

            long_profit = (self.cur_stop_price - entry_price) * AU_CONTRACT_MULTIPLIER
            short_profit = (entry_price - self.cur_stop_price) * AU_CONTRACT_MULTIPLIER
            profit = long_profit if self.position > 0 else short_profit
            gain_or_loss = "盈利" if profit > 0 else "亏损"

            msg = self.format_broadcast_msg(f"止损价移到 {new_stop:.2f}，目前{gain_or_loss} {profit} 元", new_data)
            wx_helper = WeChatHelper()
            wx_helper.send_message_to_multiple_recipients(msg, [environment.group_chat_name_dlb,
                                                                environment.group_chat_name_vip])

        return False, just_moved


def run_debug_tasks(data_gen, strategy):
    """
    Debug模式下的定时任务
    """
    # 更新debug时间
    current_time = datetime.strptime(environment.debug_latest_candle_time, '%Y-%m-%d %H:%M:%S')
    trading_helper = TradingTimeHelper(data_gen.product_type)
    updated_time = DebugTimeManager.update_debug_time(current_time, trading_helper)
    if updated_time is None:
        strategy.build_total_portfolio()
        PowerWaveBacktrace.report_performance(strategy)
        return

    # 获取新数据
    new_data = data_gen.next()
    if new_data is not None:
        # 处理数据
        Logger.debug(f"加载新的数据成功->时间戳：{new_data.name}", save_to_file=False)
        strategy.on_new_bar(new_data)

    # 设置下一次执行时间（0.5秒后）
    Timer(0.01, run_debug_tasks, args=[data_gen, strategy]).start()


def run_prod_tasks(data_gen, strategy):
    """
    生产环境下的定时任务，在每分钟的40-50秒之间执行
    """
    now = DateUtils.now()
    current_second = now.second

    if current_second in range(20, 25):  # 在5-10秒之间执行
        # 获取新数据
        new_data = data_gen.next()
        if new_data is not None:
            # 处理数据
            strategy.on_new_bar(new_data)

        # 设置下一次执行时间
        delay = 20 - now.second
        if delay <= 0:
            delay += 60
        Timer(delay, run_prod_tasks, args=[data_gen, strategy]).start()
    else:
        # 如果不在目标时间范围内，等待到下一个5秒
        delay = 20 - current_second
        if delay <= 0:
            delay += 60
        Timer(delay, run_prod_tasks, args=[data_gen, strategy]).start()


if __name__ == "__main__":
    # 初始化
    product_type = "AU"  # 设置要交易的品种
    interval = "1min"  # 设置时间周期
    data_gen = PowDataStreamGenerator(product_type, interval)
    strategy = StreamingStrategy(product_type=product_type)
    strategy.data_window = data_gen.data_window

    # 根据环境启动对应的定时任务
    if os.getenv('DEBUG_MODE') == '1':
        msg = f"[power wave] 开始监控 DEBUG环境 {product_type} {interval} 实时交易..."
        run_debug_tasks(data_gen, strategy)
    else:
        msg = f"[power wave] 开始监控 真实环境 {product_type} {interval} 实时交易..."

        run_prod_tasks(data_gen, strategy)

    wx_helper = WeChatHelper()
    wx_helper.send_message_to_multiple_recipients(msg, [environment.group_chat_name_monitor])
