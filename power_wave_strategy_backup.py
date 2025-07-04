import environment
import logging

from date_utils import DateUtils
from feature_info import shfe_product_types, cffex_product_types, dce_product_types, czce_product_types, \
    ine_product_types, gfex_product_types, FeatureInfo
from power_wave_backup import PowerWave
import backtrader as bt

from text_utils import TextUtils
from trading_time_helper import TradingTimeHelper
from wechat_helper import WeChatHelper
from database_helper import DatabaseHelper
import pandas as pd
from power_wave_helper import PowerWaveHelper

db_helper = DatabaseHelper()


class ColorState:
    def __init__(self, power):
        self.power = power
        self.current_diff = self.power.vard[0] - self.power.vare[0]
        self.prev_diff = self.power.vard[-1] - self.power.vare[-1]
        self.current_color = '绿' if self.current_diff < 0 else '红'
        self.pre_color = '绿' if self.prev_diff < 0 else '红'

    def is_color_changed(self):
        return self.current_color != self.pre_color

    def __str__(self):
        direction = "（看空）" if self.current_color == "绿" and self.pre_color == "红" else "（看多）" if self.current_color == "红" and self.pre_color == "绿" else ""
        return f"当前颜色：{self.current_color}，上一根：{self.pre_color}{direction}。"


class PowerStatus:
    def __init__(self, strategy):
        self.strategy = strategy
        self.color_state = ColorState(strategy.power)
        self.percentile = self._calculate_percentile()
        self.macd_status = PowerWaveHelper.get_macd_cross(strategy.macd)
        self.macd_msg = "不满足" if TextUtils.is_empty(self.macd_status) else self.macd_status
        self.direction = '多' if self.color_state.current_color == '红' else '空'
        self.boll_status = PowerWaveHelper.check_boll_condition(strategy.data.close, self.direction)
        self.boll_ok = bool(self.boll_status)
        self.macd_ok = (self.direction == '多' and self.macd_status == '金叉') or (
                self.direction == '空' and self.macd_status == '死叉')
        self.valid_percentile = (self.direction == '空' and self.percentile > 80) or (self.direction == '多' and self.percentile < 20)

    def _calculate_percentile(self):
        return self.strategy.power.vare[0] if self.color_state.current_color == "红" else self.strategy.power.vard[0]

    def is_valid_signal(self):
        return self.color_state.is_color_changed() and self.valid_percentile

    #当前的柱子是否满足
    def is_valid_kline(self):
        return (self.direction == '空' and self.percentile > 80) or (self.direction == '多' and self.percentile < 20)

    def is_all_conditions_met(self):
        return self.macd_ok and self.boll_ok and self.valid_percentile

    def format_status_msg(self, extra_msg=""):
        msg = (
            f"{self.color_state}"
            f"百分位：{self.percentile:.2f}，"
            f"MACD：{'满足' if self.macd_ok else '未满足'}，布林带：{'满足' if self.boll_ok else '未满足'}"
        )
        if extra_msg:
            msg += f"，{extra_msg}"
        return msg


class PowerWaveStrategy(bt.Strategy):
    params = (
        ('exit_threshold', 70),  # 超买平仓阈值
    )

    def __init__(self, interval, product_type):
        self.power = PowerWave(self.data)
        self.macd = bt.indicators.MACD(self.data.close)

        # 柱状图颜色计算（需在next中处理）
        self.histogram = self.data.close - self.data.close  # 初始化空线
        self.histogram_color = []
        self.interval = interval
        self.product_type = product_type

    def next(self):
        # 计算柱状图颜色
        current_vard = self.power.vard[0]
        current_vare = self.power.vare[0]
        current_diff = current_vard - current_vare
        current_wave_height = abs(current_diff)
        prev_diff = self.power.vard[-1] - self.power.vare[-1]
        pre_wave_height = abs(prev_diff)

        current_color = '绿' if current_diff < 0 else '红'
        current_candle_time = self.data.datetime.datetime(0)
        formatted_time = current_candle_time.strftime('%Y-%m-%d %H:%M:%S')

        total_length = self.data.buflen()

        if len(self.data) > total_length - 6:
            logging.info(
                f"[power wave] time:{formatted_time},current : {len(self.data)} , total : {total_length},color:{current_color}")

        if len(self.data) == total_length:
            current_power_status = PowerStatus(self)

            logging.info(
                f"[power wave] time:{formatted_time},current : {len(self.data)} , total : {total_length},vard:{current_vard},vare:{current_vare},current_height : {current_wave_height},pre_height : {pre_wave_height}")

            latest_triggered_signal = db_helper.get_latest_triggered_power_wave_signal(self.product_type,
                                                                                       self.interval)
            if latest_triggered_signal is not None:
                self.handle_un_closed(latest_triggered_signal, current_power_status)
            else:
                untriggered_signals = db_helper.get_untriggered_power_wave_signals(self.product_type, self.interval)
                if len(untriggered_signals) > 0:
                    sig = untriggered_signals[-1]
                    self.handle_un_triggered(sig, current_power_status)
                else:
                    self._handle_current_kline(formatted_time)

    def handle_un_triggered(self, signal, status):
        if status.macd_ok and getattr(signal, 'macd_triggered', 0) == 0:
            db_helper.update_power_wave_signal_macd(signal.id)

        if status.boll_ok and getattr(signal, 'boll_triggered', 0) == 0:
            db_helper.update_power_wave_signal_boll(signal.id)

        wx_helper = WeChatHelper()
        if status.is_all_conditions_met():
            msg = self.format_broadcast_msg(
                sig=signal,
                extra_msg=f"\n可以下单！开单价: {self.data.close[0]}"
            )
            wx_helper.send_message(msg, "动力波策略群")
            db_helper.update_power_wave_signal_broadcast(signal.id)
            db_helper.update_power_wave_signal_open_price(signal.id, self.data.close[0])
        else:
            msg = self.format_broadcast_msg(
                sig=signal,
                extra_msg="\n小助理将持续为您播报..."
            )
            wx_helper.send_message(msg, "动力波策略群")

    def handle_un_closed(self, position, power_status):
        current_candle_time = self.data.datetime.datetime(0)
        formatted_time = current_candle_time.strftime('%Y-%m-%d %H:%M:%S')
        if position:
            if position.closed != 1:
                # 当前刚刚发生改变
                if power_status.color_state.is_color_changed():

                    open_price = position.open_price
                    close_price = self.data.close[0]
                    earn = (close_price - open_price) if position.direction == '多' else (open_price - close_price)
                    # 发送平仓播报
                    wx_helper = WeChatHelper()
                    msg = self.format_broadcast_msg(None,
                                                    f"\n颜色发生变化，请平仓！平仓价: {close_price:.2f},开仓价{open_price:.2f},本次盈利{earn:.2f}")
                    wx_helper.send_message(
                        msg,
                        "动力波策略群")
                    # 更新数据库中的平仓信息
                    db_helper.update_power_wave_signal_exit(position.id, close_price,
                                                            formatted_time)

                    self._handle_current_kline(formatted_time)
                else:
                    # 异常退出过，但是颜色已经发生变化，可以平仓了
                    if position.direction != power_status.direction:
                        open_price = position.open_price
                        close_price = self.data.close[0]
                        earn = (close_price - open_price) if position.direction == '多' else (open_price - close_price)

                        wx_helper = WeChatHelper()
                        msg = self.format_broadcast_msg(position,
                                                        f"\n系统可能异常退出，未及时播报颜色变化，请平仓！盈利：{earn:.2f}")
                        wx_helper.send_message(
                            msg,
                            "动力波策略群")
                        # 更新数据库中的平仓信息
                        db_helper.update_power_wave_signal_exit(position.id, close_price,
                                                                formatted_time)

                        self._handle_current_kline(formatted_time)
                    else:
                        logging.info(f"[power wave] 品种: {self.product_type}, interval: {self.interval},当前百分位:{power_status.percentile:.2f}，颜色未变化，请继续持仓")
            else:
                logging.info("[power wave] 已经平仓，等待新机会吧")
                self._handle_current_kline(formatted_time)

        else:
            self._handle_current_kline(formatted_time)

    def format_signal_base_msg(self, sig):
        """
        格式化信号的基本信息
        """
        product_name = FeatureInfo.get_product_name(sig.product_type)
        return (
            f"请注意，当前：【{product_name}({sig.product_type}){sig.interval} "
            f"方向：{sig.direction}，"
            f"时间：{sig.signal_time}"
            f"的信号】"
        )

    def format_broadcast_msg(self, sig, extra_msg=""):
        """
        组合信号基本信息和当前状态信息
        """
        status = PowerStatus(self)
        if sig is not None:
            base_msg = self.format_signal_base_msg(sig)
        else:
            product_name = FeatureInfo.get_product_name(self.product_type)
            base_msg = f"请注意，{self.product_type}({product_name}) {self.interval}"
        status_msg = status.format_status_msg(extra_msg)
        return base_msg + "\n" + status_msg

    def _handle_current_kline(self, formatted_time):
        """
        处理新动力波信号产生时的逻辑：判断条件，入库，首次播报。
        """
        status = PowerStatus(self)
        close_price = self.data.close[0]

        def judge_open(status):
            # 检查是否存在相同条件的未平仓信号
            existing_signal = db_helper.get_latest_unclosed_signal(
                product_type=self.product_type,
                interval=self.interval,
                direction=status.direction
            )

            if existing_signal is not None:
                logging.info(f"已存在相同条件的未平仓信号，跳过新信号生成。现有信号ID: {existing_signal.id}")
                return

            # 较大级别周期方向暂置空
            higher_period_direction = ''

            db_helper.store_power_wave_signal(
                product_type=self.product_type,
                interval=self.interval,
                direction=status.direction,
                percentile=status.percentile,
                macd_triggered=status.macd_ok,
                boll_triggered=status.boll_ok,
                higher_period_direction=higher_period_direction,
                signal_time=formatted_time,
                is_triggered= status.is_all_conditions_met(),
                open_price= close_price if status.is_all_conditions_met() is True else 0,
            )
        #刚刚发生改变
        if status.is_valid_signal():
            judge_open(status)
            msg = self.format_broadcast_msg(
                sig=None,
                extra_msg="\n我将持续跟踪布林带和macd的共振情况，请等待我后续播报" if not status.is_all_conditions_met() else ""
            )
            wx_helper = WeChatHelper()
            wx_helper.send_message(msg, "动力波策略群")
        else:
            if status.is_valid_kline():
                judge_open(status)
                extra_msg_not_met = "\n程序之前可能异常，没有捕捉到变色\n我将持续跟踪布林带和 MACD 的共振情况，请等待我后续播报"
                extra_msg_met = f"\n程序之前可能异常，没有捕捉到变色\n目前情况仍然可以开单，请开单！目前价格{close_price}"

                msg = self.format_broadcast_msg(
                    sig=None,
                    extra_msg=extra_msg_not_met if not status.is_all_conditions_met() else extra_msg_met
                )
                wx_helper = WeChatHelper()
                wx_helper.send_message(msg, "动力波策略群")
            else:
                logging.info(f"[power wave]不满足条件。。。等待吧")
