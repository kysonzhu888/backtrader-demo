import environment
import backtrader as bt
import logging
from datetime import datetime
from pinbar import Pinbar

import numpy as np
import pandas as pd

from k_line import KLine
from pinbar import PinbarType
from trading_time_helper import TradingTimeHelper


class PinbarHelper:

    @staticmethod
    def is_bullish_pinbar(open_price, high, low, close):
        # 计算实体长度
        length = abs(high - low)

        # 计算上下影线长度
        lower_shadow = min(open_price, close) - low

        # 判断是否为Pinbar
        # 下影线是实体的2/3以上，且上影线较短
        is_bullish_pinbar = (lower_shadow > (2 / 3.001 * length))

        return is_bullish_pinbar

    @staticmethod
    def is_bearish_pinbar(open_price, high, low, close):
        # 计算实体长度
        length = abs(high - low)

        # 计算上下影线长度
        upper_shadow = high - max(open_price, close)

        # 判断是否为Pinbar
        # 上影线是实体的2/3以上，且下影线较短
        is_bearish_pinbar = (upper_shadow > (2 / 3.001 * length))

        return is_bearish_pinbar

    @staticmethod
    def is_excellent_pinbar(open_price, high, low, close):
        # 创建 KLine 和 Pinbar 对象
        k_line = KLine(open=open_price, high=high, low=low, close=close)
        p = Pinbar(k_line)

        # 计算实体长度
        length = abs(high - low)

        # 计算影线长度
        lower_shadow = min(open_price, close) - low
        upper_shadow = high - max(open_price, close)

        # 判断影线是否大于总长度的75%
        if lower_shadow > 0.75 * length:
            p.is_excellent = True
            p.type = PinbarType.type_bullish
            return p
        elif upper_shadow > 0.75 * length:
            p.is_excellent = True
            p.type = PinbarType.type_bearish
            return p

        return None

    @staticmethod
    def is_single_pinbar(open_price, high, low, close, minest):
        k_line = KLine(open=open_price, high=high, low=low, close=close)
        p = Pinbar(k_line)

        # 计算实体长度
        length = abs(high - low)
        if length < minest:
            ep = PinbarHelper.is_excellent_pinbar(open_price, high, low, close)
            if ep is not None and length > minest * 0.75:
                return ep
            else:
                return None

        # 判断是否为Pinbar
        # 上影线是实体的2/3以上，且下影线较短
        is_bearish_pinbar = PinbarHelper.is_bearish_pinbar(open_price, high, low, close)

        if is_bearish_pinbar:
            p.type = PinbarType.type_bearish
            return p

        # 下影线是实体的2/3以上，且上影线较短
        is_bullish_pinbar = PinbarHelper.is_bullish_pinbar(open_price, high, low, close)
        if is_bullish_pinbar:
            p.type = PinbarType.type_bullish
            return p

        return None

    ## Evening Star	/Morning Star	/Bullish Engulfing Pattern	/Bearish Engulfing Pattern
    def combined_candle_with_previous(data, count):
        # 确保 count 不超过 3
        count = min(count, 3)

        # 使用 Backtrader 的 API 获取需要合并的K线数据
        combined_open = data.open.get(size=count)[-count]  # 最早K线的开盘价
        combined_close = data.close.get(size=count)[-1]  # 最晚K线的收盘价
        combined_high = max(data.high.get(size=count))  # 所有K线中的最高价
        combined_low = min(data.low.get(size=count))  # 所有K线中的最低价

        return combined_open, combined_high, combined_low, combined_close

    @staticmethod
    def is_lager_than_left_eye(data, pinbar):
        # 计算当前 pinbar 的长度
        current_high = pinbar.get_high()
        current_low = pinbar.get_low()
        pinbar_length = abs(current_high - current_low)

        # 计算左眼的长度
        # warning 这里要改针对组合pinbar 的情况
        prev_high = data.high[-1]
        prev_low = data.low[-1]
        left_eye_length = abs(prev_high - prev_low)
        # 判断当前 pinbar 是否有效
        return pinbar_length >= left_eye_length

    # 判断当前pinbar的实体部分是否在左眼最高价和最低价之内
    @staticmethod
    def is_body_in_left_eye(data, pinbar):
        # 计算当前 pinbar 的长度
        current_open = pinbar.get_open()
        current_close = pinbar.get_close()

        # 计算左眼的长度
        # warning 这里要改针对组合pinbar 的情况
        prev_high = data.high[-1]
        prev_low = data.low[-1]

        # 判断当前pinbar的实体部分是否在左眼最高价和最低价之内
        return prev_low <= min(current_open, current_close) and prev_high >= max(current_open, current_close)

    # 判断当前pinbar是否存在巨幅跳空
    @staticmethod
    def have_giant_price_gap(data, pinbar, base_atr):
        # 计算跳空大小
        current_open = pinbar.get_open()
        #warning 这里待修复（复合pinbar ）
        prev_close = data.close[-1]

        price_gap = abs(current_open - prev_close)
        # 判断跳空是否大于 2 个 ATR
        return price_gap > 2 * base_atr

    @staticmethod
    def at_recent_high_low(data, pinbar, lookback, atr):
        '''
        是否在相对的高位或者低位，通过两个维度来判断
        1.中周期上，看 10 日均线是否梯度增加或减少（分别取 lookback 的 1.5 倍和 1/2.4 倍）
        2.小周期上，看最近的 lookback 根 K 线是否梯度上涨或者下跌
        '''
        # 最近的高低点
        recent_highs = data.high.get(size=lookback)
        recent_lows = data.low.get(size=lookback)
        # 判断是上插针还是下插针
        is_bullish = pinbar.type == PinbarType.type_bullish
        is_bearish = pinbar.type == PinbarType.type_bearish

        current_high = pinbar.kline.high
        current_low = pinbar.kline.low

        # 计算满足条件的数量
        valid_count = 0
        window = 5
        # 将 LineBuffer 转换为 Pandas Series
        size = lookback * 1.2 + window + 1
        close_series = pd.Series(data.close.get(size=round(size)))
        # 计算局部 MA20
        ma5_subset = close_series.rolling(window=window).mean()

        # 定位关键点
        idx = -round(lookback * 1.1)
        if len(ma5_subset) > abs(idx):
            prev_far = ma5_subset.iloc[idx]
        else:
            # 长度不够，直接返回False或None，或者跳过本次判断
            return False  # 或者 return None，视你的业务逻辑而定
        prev_mid = ma5_subset.iloc[-round(lookback / 2)]
        current = ma5_subset.iloc[-1]

        ma_condition_met = False

        if is_bullish:
            if any(current_low >= low for low in recent_lows[:-1]):
                return False
            for i in range(len(recent_highs)):  # 确保索引不超出范围
                # 计算前 i 根的中点
                prev_midpoint = (recent_highs[i] + recent_lows[i]) / 2
                logging.debug(f"===>计算前 i 根的中点 recent_highs[{i}]:{recent_highs[i]}, recent_lows[{i}]:{recent_lows[i]}")

                # 检查前一根的中点是否高于当前
                if i > 0:
                    prev_prev_midpoint = (recent_highs[i - 1] + recent_lows[i - 1]) / 2
                    logging.debug(
                        f"===>计算前 i 根的中点 recent_highs[{i}]:{recent_highs[i]}, recent_lows[{i}]:{recent_lows[i]}")
                    if prev_prev_midpoint >= prev_midpoint:
                        valid_count += 1

            # 检查20日平均线是否递增
            ma_condition_met = prev_far > prev_mid > current

        elif is_bearish:
            # 确保 pinbar 的最高值高于 recent_highs 中的每一个元素
            logging.debug(f"===>recent_highs[:-1]: {recent_highs[:-1]}")
            if any(current_high <= high for high in recent_highs[:-1]):
                return False
            for i in range(len(recent_highs)):  # 确保索引不超出范围
                # 计算前 i 根的中点
                logging.debug(f"===>计算前 i 根的中点 recent_highs[{i}]:{recent_highs[i]}, recent_lows[{i}]:{recent_lows[i]}")
                prev_midpoint = (recent_highs[i] + recent_lows[i]) / 2
                # 检查前一根的中点是否低于当前
                if i > 0:
                    logging.debug(
                        f"===>检查前一根的中点是否低于当前 recent_highs[{i - 1}]:{recent_highs[i - 1]}, recent_lows[{i - 1}]:{recent_lows[i - 1]}")
                    prev_prev_midpoint = (recent_highs[i - 1] + recent_lows[i - 1]) / 2
                    if prev_prev_midpoint <= prev_midpoint:
                        valid_count += 1

            # 检查20日平均线是否递减
            ma_condition_met = prev_far < prev_mid < current

        else:
            logging.error("===>不是 pinbar，怎么走到这里来了")

        # 至少有一半的 lookback 满足条件
        target_count = round(lookback / 2.4)
        logging.info(f"valid_count:{valid_count}, ma_condition_met:{ma_condition_met}")
        return valid_count >= target_count and ma_condition_met

    @staticmethod
    def is_at_key_level(current_high, current_low, key_levels, tolerance):
        """
        判断 pinbar 是否位于关键位（支撑或阻力位）

        :param current_high: 当前 K 线的最高价
        :param current_low: 当前 K 线的最低价
        :param key_levels: 关键位列表（支撑或阻力位）
        :param tolerance: 容忍度，用于判断价格是否接近关键位
        :return: 如果 pinbar 位于关键位，返回 True；否则返回 False
        """
        closest_level = None
        min_distance = float('inf')

        # 遍历所有关键位
        for level in key_levels:
            # 计算当前 K 线的高低价与关键位的距离
            high_distance = abs(current_high - level)
            low_distance = abs(current_low - level)

            # 检查是否接近关键位
            is_high_near = high_distance > (tolerance * -1)
            is_low_near = low_distance > (tolerance * -1)

            if is_high_near or is_low_near:
                # 选择更接近的关键位
                closer_distance = min(high_distance, low_distance)
                if closer_distance < min_distance:
                    min_distance = closer_distance
                    closest_level = level

        # 返回最接近的关键位
        if closest_level is not None:
            return True, closest_level

        return False, None  # 如果没有接近任何关键位，返回 False

    @staticmethod
    def is_false_breakout(pinbar, highest, lowest):
        """
        判断 pinbar 是否为假突破

        :param current_high: 当前 K 线的最高价
        :param current_low: 当前 K 线的最低价
        :param key_levels: 关键位列表（支撑或阻力位）
        :param tolerance: 容忍度，用于判断价格是否接近关键位
        :return: 如果 pinbar 为假突破，返回 True；否则返回 False
        """
        # 判断逻辑优化
        is_bullish = pinbar.type == PinbarType.type_bullish
        current_low = pinbar.get_low()
        if is_bullish and current_low < lowest:
            return True

        is_bearish = pinbar.type == PinbarType.type_bearish
        current_high = pinbar.get_high()
        if is_bearish and current_high > highest:
            return True

        return False

    @staticmethod
    def is_trend_following(data, pinbar, product_type):

        trading_time_helper = TradingTimeHelper(product_type)
        trading_time_lenght = trading_time_helper.calculate_daily_trading_hours()
        # 根据 trading_time_lenght 决定 lookback 周期数
        lookback = int(trading_time_lenght * 12)

        total_length = data.buflen()  # 数据源总长度
        if total_length < lookback:
            return False

        # 获取最近 lookback 周期内的最高价和最低价
        highs = [data.high[-i - 1] for i in range(lookback)]
        lows = [data.low[-i - 1] for i in range(lookback)]

        highest_high = max(highs)
        lowest_low = min(lows)

        # 计算 61.8% 的位置
        fib_618 = lowest_low + 0.618 * (highest_high - lowest_low)

        # 判断逻辑优化
        is_bullish = pinbar.type == PinbarType.type_bullish
        is_bearish = pinbar.type == PinbarType.type_bearish

        # 方法 A: 使用斐波那契回撤判断趋势
        is_trend_following_a = True
        if pinbar.get_close() < fib_618 and is_bullish:
            is_trend_following_a = False  # 逆势
        elif pinbar.get_close() > fib_618 and is_bearish:
            is_trend_following_a = False  # 逆势

        # 方法 B: 使用 MA50 判断趋势
        ma50_recent = np.mean([data.close[-i - 1] for i in range(50)])
        ma50_past = np.mean([data.close[-i - 1 - lookback] for i in range(50)])
        is_trend_following_b = (ma50_recent > ma50_past and is_bullish) or (ma50_recent < ma50_past and is_bearish)

        # 返回两种方法的结果

        if is_trend_following_a == is_trend_following_b:
            return is_trend_following_b
        else:
            logging.warning(f"Method A: {is_trend_following_a}, Method B: {is_trend_following_b} 不一致，看看什么情况")
            return is_trend_following_b

    @staticmethod
    def is_engulfing(prev_open, prev_close, curr_open, curr_close):
        """吞没形态判断"""
        prev_body = prev_close - prev_open
        curr_body = curr_close - curr_open
        # 方向相反且当前K线完全吞没前一根
        return (prev_body * curr_body < 0) and \
            (abs(curr_body) > abs(prev_body)) and \
            (min(curr_open, curr_close) < min(prev_open, prev_close)) and \
            (max(curr_open, curr_close) > max(prev_open, prev_close))

    @staticmethod
    def is_morning_star(opens, closes, lows):
        """启明星形态（三日看涨）"""
        if len(opens) < 3 or len(closes) < 3:
            return False

        # 第一根长阴线
        cond1 = closes[-2] < opens[-2] and (opens[-2] - closes[-2]) / (opens[-2] + 1e-5) > 0.01

        # 第二根小实体（可能跳空）
        cond2 = abs(closes[-1] - opens[-1]) / (opens[-1] + 1e-5) < 0.005

        # 第三根长阳线且收盘超过第一根 三分之二
        cond3 = closes[0] > opens[0] and closes[0] > (opens[-2] + closes[-2]) / 3 * 2

        return cond1 and cond2 and cond3

    @staticmethod
    def is_evening_star(opens, closes, highs):
        """黄昏之星形态（三日看跌）"""
        if len(opens) < 3 or len(closes) < 3:
            return False

        # 第一根长阳线
        cond1 = closes[-2] > opens[-2] and (closes[-2] - opens[-2]) / (opens[-2] + 1e-5) > 0.01

        # 第二根小实体（可能跳空）
        cond2 = abs(closes[-1] - opens[-1]) / (opens[-1] + 1e-5) < 0.005

        # 第三根长阴线且收盘低于第一根中点
        cond3 = closes[0] < opens[0] and closes[0] < (opens[-2] + closes[-2]) / 3 * 2

        return cond1 and cond2 and cond3

    @staticmethod
    def is_pinbar_or_variant(data, minest, valid_length=3):

        """综合判断形态变体"""
        if len(data) < valid_length:
            return None

        current_open = data.open[0]
        current_high = data.high[0]
        current_low = data.low[0]
        current_close = data.close[0]

        # 单根Pinbar判断
        pin = PinbarHelper.is_single_pinbar(current_open, current_high, current_low, current_close, minest)
        if pin is not None:
            logging.info(f"====单根 pinbar")
            return pin

        candle_length = abs(current_high - current_low)
        if candle_length < minest:
            return None

        pre_time = data.datetime.datetime(-1)
        pre_open = data.open[-1]
        pre_close = data.close[-1]
        pre_high = data.high[-1]
        pre_low = data.low[-1]

        logging.info(
            f"即将判断是否其他组合 pinbar::pre time:{pre_time},pre_open->{pre_open},pre_close->{pre_close},pre_high->{pre_high},pre_low->{pre_low}")

        if candle_length < minest * 1.4:
            return None

        # 两日吞没形态
        if PinbarHelper.is_engulfing(pre_open, pre_close, current_open, current_close):
            combined_open, combined_high, combined_low, combined_close = PinbarHelper.combined_candle_with_previous(
                data, 2)
            logging.info(
                f"====是吞没，下面判断 是否 pinbar open:{combined_open},high:{combined_high},low:{combined_low},close:{combined_close}")

            combine_pinbar = PinbarHelper.is_single_pinbar(combined_open, combined_high, combined_low,
                                                           combined_close, minest)
            return combine_pinbar

        # 获取最近3根K线数据（包含当前最新K线，索引0为最新）
        opens = [data.open[i] for i in range(-valid_length + 1, 1)]
        closes = [data.close[i] for i in range(-valid_length + 1, 1)]
        highs = [data.high[i] for i in range(-valid_length + 1, 1)]
        lows = [data.low[i] for i in range(-valid_length + 1, 1)]

        # 三日形态判断
        is_pin = PinbarHelper.is_morning_star(opens, closes, lows) or \
                 PinbarHelper.is_evening_star(opens, closes, highs)
        if is_pin:
            combined_open, combined_high, combined_low, combined_close = PinbarHelper.combined_candle_with_previous(
                data, 3)
            logging.info(
                f"====是黄昏星或者启明星，下面判断 是否 pinbar open:{combined_open},high:{combined_high},low:{combined_low},close:{combined_close}")
            com_pinbar = PinbarHelper.is_single_pinbar(combined_open, combined_high, combined_low,
                                                       combined_close, minest)

            return com_pinbar

        return None
    @staticmethod
    def is_prominent(data, pinbar, atr):
        """判断pinbar是否突出"""
        # 计算 pinbar 的长度
        pinbar_length = abs(pinbar.get_high() - pinbar.get_low())

        # 判断 pinbar 长度是否大于 2 倍 ATR
        if pinbar_length > 2 * atr:
            return True

        # 判断是否为下插针
        is_bullish = pinbar.type == PinbarType.type_bullish
        is_bearish = pinbar.type == PinbarType.type_bearish

        if is_bullish:
            # 获取左边6根的最低价
            left_lows = [data.low[-i - 1] for i in range(6)]
            # 判断左边6根最低价和当前pinbar的最低价差是否大于1.5倍ATR
            if min(left_lows) - pinbar.get_low() > 1.5 * atr:
                return True

        elif is_bearish:
            # 获取左边6根的最高价
            left_highs = [data.high[-i - 1] for i in range(6)]
            # 判断左边6根最高价和当前pinbar的最高价差是否大于1.5倍ATR
            if pinbar.get_high() - max(left_highs) > 1.5 * atr:
                return True

        return False

    @staticmethod
    def no_obvious_acceleration(data, pinbar, atr):
        """判断是否存在明显的加速"""
        # 判断是否为下插针
        is_bullish = pinbar.type == PinbarType.type_bullish
        is_bearish = pinbar.type == PinbarType.type_bearish

        if is_bullish:
            # 获取前面15根的最高价
            prev_highs = [data.high[-i - 1] for i in range(15)]
            # 判断前面15根的最高价减去pinbar的收盘价是否大于10倍的ATR
            if max(prev_highs) - pinbar.get_close() > 10 * atr:
                return False

        elif is_bearish:
            # 获取前面15根的最低价
            prev_lows = [data.low[-i - 1] for i in range(15)]
            # 判断pinbar的收盘价减去前面15根的最低价是否大于10倍的ATR
            if pinbar.get_close() - min(prev_lows) > 10 * atr:
                return False

        return True
    
    def risk_reward_ratio_ok(pinbar,atr):
        """判断pinbar的盈亏比是否合理"""
        return True
