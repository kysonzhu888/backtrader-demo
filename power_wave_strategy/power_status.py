from micro_defs import MACDCross, BarColor, Direction
from power_wave import PowerWave
from power_wave_helper import PowerWaveHelper
import pandas as pd

# 在PowerStatus类定义前添加常量
PERCENTILE_UPPER_LIMIT = 75
PERCENTILE_LOWER_LIMIT = 25


class IntradayStatus:

    def __init__(self):
        self.is_bull = None
        self.intraday_price = None

    def update(self, data_window):
        long_status, intraday_price, _ = IntradayStatus.is_close_above_intraday_ma(data_window)
        self.is_bull = long_status
        self.intraday_price = intraday_price

    @staticmethod
    def is_close_above_intraday_ma(data, ma_type='mean'):
        """
        判断当前K线收盘价是否在分时均线之上。
        均线为"最近交易日15:00收盘价"+当日21:00至当前的所有分钟K线收盘价的均值。
        返回：(True/False, cur_close, mean_price)
        """
        if data is None or data.empty:
            return None, None, None
        cur_time = data.index[-1]
        # 1. 找到最近交易日15:00的收盘价
        if cur_time.hour >= 21:
            # 夜盘，最近交易日为当天
            last_trade_day = cur_time.date()
        else:
            # 日盘，往前找最近交易日
            last_trade_day = (cur_time - pd.Timedelta(days=1)).date()
            # 如果当天是周一，last_trade_day是周日，需再往前找
            while last_trade_day.weekday() >= 5:  # 5=周六，6=周日
                last_trade_day -= pd.Timedelta(days=1)
        # 取最近交易日15:00的收盘价
        last_close_time = pd.Timestamp(last_trade_day).replace(hour=15, minute=0, second=0, microsecond=0)
        if last_close_time in data.index:
            last_close = data.loc[last_close_time, 'Close']
        else:
            # 若数据缺失，取最接近15:00的前一根
            last_day_data = data[(data.index.date == last_trade_day) & (data.index.hour == 15)]
            if not last_day_data.empty:
                last_close = last_day_data['Close'].iloc[-1]
            else:
                last_close = None
        # 2. 拼接最近收盘价+当日分时
        if cur_time.hour >= 21:
            day_start = cur_time.replace(hour=21, minute=0, second=0, microsecond=0)
        else:
            day_start = (cur_time - pd.Timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)
        intraday_data = data[(data.index >= day_start) & (data.index <= cur_time)]
        # 拼接
        if last_close is not None:
            # 构造一个虚拟的"最近收盘"点
            last_row = pd.DataFrame({'Close': [last_close]}, index=[last_close_time])
            all_data = pd.concat([last_row, intraday_data[['Close']]])
            all_data = all_data[~all_data.index.duplicated(keep='last')]  # 去重，防止index重复
        else:
            all_data = intraday_data[['Close']]
        if all_data.empty:
            return None, None, None
        if ma_type == 'mean':
            close_series = pd.to_numeric(all_data['Close'], errors='coerce')
            mean_price = close_series.mean()
        else:
            mean_price = all_data['Close'].rolling(window=ma_type).mean().iloc[-1]
        cur_close = all_data['Close'].iloc[-1]
        return cur_close > mean_price, cur_close, mean_price


class ColorState:
    def __init__(self, vard, vare):
        self.current_diff = vard.iloc[-1] - vare.iloc[-1]
        self.prev_diff = vard.iloc[-2] - vare.iloc[-2]
        self.current_color = BarColor.GREEN.value if self.current_diff < 0 else BarColor.RED.value
        self.prev_color = BarColor.GREEN.value if self.prev_diff < 0 else BarColor.RED.value

    def is_color_changed(self):
        return self.current_color != self.prev_color


class PowerStatus:
    def __init__(self, power_wave: PowerWave, macd, intraday_status: IntradayStatus = None):
        self.color_state = ColorState(power_wave.vard, power_wave.vare)
        self.percentile = self._calculate_percentile(power_wave)
        self.macd_status = self._get_macd_cross_from(macd)
        self.bar_height = self._calculate_bar_height(power_wave)
        self.direction = Direction.LONG.value if self.color_state.current_color == BarColor.RED.value else Direction.SHORT.value
        self.boll_status = PowerWaveHelper.check_boll_condition(power_wave.close, self.direction)
        self.boll_ok = bool(self.boll_status)
        self.macd_ok = (self.direction == Direction.LONG.value and self.macd_status == MACDCross.GOLDEN.value) or (
                self.direction == Direction.SHORT.value and self.macd_status == MACDCross.DEAD.value)
        self.valid_percentile = (
                                        self.direction == Direction.SHORT.value and self.percentile > PERCENTILE_UPPER_LIMIT) or (
                                        self.direction == Direction.LONG.value and self.percentile < PERCENTILE_LOWER_LIMIT)

        self.intraday_price = intraday_status.intraday_price
        #日均线是否 ok
        intraday_long_ok = intraday_status.is_bull and self.direction == Direction.LONG.value
        intraday_short_ok = (intraday_status.is_bull == False) and (self.direction == Direction.SHORT.value)
        self.intraday_ok = intraday_long_ok or intraday_short_ok

    def _calculate_percentile(self, power_wave):
        return power_wave.vare.iloc[-1] if self.color_state.current_color == BarColor.RED.value else \
            power_wave.vard.iloc[-1]

    def _calculate_bar_height(self, power_wave):
        return power_wave.bar_height.iloc[-1]

    def _get_macd_cross_from(self, macd):
        macd_line = macd.macd
        signal_line = macd.signal
        if len(macd_line) < 2:
            return None
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        prev_macd = macd_line.iloc[-2]
        prev_signal = signal_line.iloc[-2]
        if current_macd > current_signal:
            return MACDCross.GOLDEN.value
        else:
            return MACDCross.DEAD.value

    def is_all_conditions_met(self):
        return self.macd_ok and self.boll_ok and self.valid_percentile

    def is_valid_signal(self):
        return self.color_state.is_color_changed() and self.valid_percentile
