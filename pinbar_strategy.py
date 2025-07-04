import environment
import pinbar
from environment import group_chat_name_vip

import threading

from date_utils import DateUtils

import backtrader as bt
import logging

from feature_info import FeatureInfo
from k_line import KLine
from key_level_helper import KeyLevelHelper
from pinbar import Pinbar
from pinbar_helper import PinbarHelper
from trading_time_helper import TradingTimeHelper

from wechat_helper import WeChatHelper
from database_helper import DatabaseHelper


class PinbarStrategy(bt.Strategy):

    def __init__(self, atr_multiplier, product_type, interval):
        # 检查数据量是否足够计算ATR
        logging.debug(f"PinbarStrategy of {product_type} in {interval} initialed ")

        total_length = self.data.buflen()
        if total_length < 14:
            logging.debug("数据量不足以计算ATR，策略可能无法正常运行。")
            self.atr = None
        else:
            self.atr = bt.indicators.AverageTrueRange()

        self.atr_multiplier = atr_multiplier
        self.product_type = product_type
        self.interval = interval

    def next(self):
        total_length = self.data.buflen()
        logging.debug(f"current : {len(self.data)} , total : {total_length}")

        if len(self.data) == 1:
            logging.debug(
                f"product_type:{self.product_type}->interval:{self.interval}->start waiting to latest candle")

        if len(self.data) == total_length - 1:
            logging.debug(
                f"current thread is main tread:  {threading.current_thread() == threading.main_thread()},product_type:{self.product_type}->interval:{self.interval}->now it's latest candle ")

        if len(self.data) == total_length:
            # 为了确保拉取最后一根 k线，这里计算一下最后一根k线的大概位置
            result_pinbar = self.check_pinbar()
            logging.debug(f"========>{result_pinbar}")
            if result_pinbar:
                # 播放音频
                product_name = FeatureInfo.get_product_name(self.product_type)
                # 检查数据库中是否已有记录
                score = len(result_pinbar.score_detail)
                score_detail_str = ",".join(result_pinbar.score_detail)
                current_time = DateUtils.now()

                db_helper = DatabaseHelper()
                db_helper.store_pinbar_data(
                    timestamp=current_time,
                    product_type=self.product_type,
                    interval=self.interval,
                    product_name=product_name,
                    score=score,
                    score_detail=score_detail_str,
                    key_level_strength='strong',
                    open=result_pinbar.get_open(),
                    close=result_pinbar.get_close(),
                    high=result_pinbar.get_high(),
                    low=result_pinbar.get_low()
                )

            else:
                logging.info('check completed, there is no pinbar. ')

    def check_pinbar(self):
        current_candle_time = self.data.datetime.datetime(0)

        formatted_time = current_candle_time.strftime('%Y-%m-%d %H:%M:%S')

        # 检查 ATR 是否已初始化
        if self.atr is None:
            logging.debug("ATR 未初始化，跳过当前计算。")
            return None
        else:
            logging.debug(f"atr:{self.atr}")

        # 获取未完成的K线数据
        current_open = self.data.open[0]
        current_high = self.data.high[0]
        current_low = self.data.low[0]
        current_close = self.data.close[0]

        # 获取当前ATR值
        real_atr = self.atr[0]
        base_atr = real_atr * self.atr_multiplier
        product_name = FeatureInfo.get_product_name(self.product_type)

        logging.info(
            f"{self.product_type} :{product_name}->{self.interval} -> time:{formatted_time}-> (open:{current_open},close {current_close}, high:{current_high}, low :{current_low}) -> start checking...")

        # 判断是否为Pinbar
        pin = PinbarHelper.is_pinbar_or_variant(self.data, base_atr)

        if pin is not None:
            pin.kline.set_interval(self.interval)

            is_at_key_level, key_level_strength = self.evaluate_key_conditions(current_high, current_low, base_atr)
            if not is_at_key_level:
                logging.debug(f"时间: {formatted_time} pinbar 不在关键位，滚粗")
                return None

            is_recent_high_or_low = PinbarHelper.at_recent_high_low(data=self.data, pinbar=pin, lookback=16, atr=self.atr)
            if not is_recent_high_or_low:
                logging.info(
                    f"{self.product_type}( {product_name}) 时间: {formatted_time}  pinbar 不在相对的高位或者低位，滚粗")
                return None

            have_giant_price_gap = PinbarHelper.have_giant_price_gap(data=self.data,pinbar=pin, base_atr=base_atr)
            if have_giant_price_gap is True:
                logging.info(f"{self.product_type}( {product_name}) 时间: {formatted_time} pinbar 有巨幅跳空，滚粗")
                return None

            pb = self.calculate_score(base_atr=base_atr, pinbar=pin)
            return pb
        else:
            logging.debug(f"时间: {formatted_time} 不是 pinbar,滚粗")
            return None

    def evaluate_key_conditions(self, current_high, current_low, base_atr):
        total_length = self.data.buflen()
        is_at_key_level, key_level, lbl = self.at_key_values(22, total_length, current_high, current_low, base_atr)
        if not is_at_key_level:
            is_at_key_level, key_level, lbl = self.at_key_values(64, total_length, current_high, current_low,
                                                                 base_atr * 1.1)
            if not is_at_key_level:
                is_at_key_level, key_level, lbl = self.at_key_values(126, total_length, current_high, current_low,
                                                                     base_atr * 1.2)
            else:
                logging.debug(f"在 60 日线上是关键位")
        else:
            logging.debug(f"在 20 日线上是关键位")

        key_level_strength = "强" if is_at_key_level else ""
        return is_at_key_level, key_level_strength

    def calculate_score(self, base_atr,pinbar):

        is_lager_than_left_eye = PinbarHelper.is_lager_than_left_eye(data=self.data,pinbar=pinbar)
        is_body_in_left_eye = PinbarHelper.is_body_in_left_eye(data=self.data, pinbar=pinbar)

        # pinbar 长度是否大于左眼
        if is_lager_than_left_eye and is_body_in_left_eye:
            pinbar.score_detail.append(Pinbar.Score.score_3)
        elif is_lager_than_left_eye and (is_body_in_left_eye is not True):
            trading_time_helper = TradingTimeHelper(self.product_type)
            if trading_time_helper.is_just_opened(self.interval):
                logging.info("目前是刚开盘时间，有跳空正常")
                pinbar.score_detail.append(Pinbar.Score.score_3)
            else:
                logging.info(f"???is_lager_than_left_eye:{is_lager_than_left_eye},is_body_in_left_eye:{is_body_in_left_eye}")
        else:
            logging.info(f"???is_lager_than_left_eye:{is_lager_than_left_eye},is_body_in_left_eye:{is_body_in_left_eye}")

        if PinbarHelper.is_prominent(self.data,pinbar,atr=base_atr):
            pinbar.score_detail.append(Pinbar.Score.score_1)

        highest, lowest = KeyLevelHelper.identify_highest_lowest(self.data, 36)
        if highest is not None and lowest is not None:
            is_false_breakout = PinbarHelper.is_false_breakout(pinbar=pinbar,
                                                               highest=highest, lowest=lowest)
            if is_false_breakout:
                pinbar.score_detail.append(Pinbar.Score.score_2)

        is_follow_trend = PinbarHelper.is_trend_following(data=self.data,pinbar=pinbar, product_type=self.product_type)
        if is_follow_trend:
            pinbar.score_detail.append(Pinbar.Score.score_4)

        is_risk_reward_ratio_ok = PinbarHelper.risk_reward_ratio_ok(pinbar=pinbar,atr=base_atr)
        if is_risk_reward_ratio_ok:
            pinbar.score_detail.append(Pinbar.Score.score_5)

        is_no_obvious_acceleration = PinbarHelper.no_obvious_acceleration(data=self.data,pinbar=pinbar,atr=base_atr)
        if is_no_obvious_acceleration:
            pinbar.score_detail.append(Pinbar.Score.score_6)

        return pinbar

    def at_key_values(self, lookback_length, data_total_length, current_high, current_low, atr):
        # 判断 k 线长度是否够
        lookback_real_length = lookback_length if data_total_length > lookback_length else data_total_length
        #拉取这段时间的关键位数组
        latest_key_levels = KeyLevelHelper.identify_key_levels_without_noise(self.data, lookback_real_length)
        tolerance = 0.01 * atr * lookback_real_length
        is_at_key_level, key_level = PinbarHelper.is_at_key_level(current_high, current_low, latest_key_levels,
                                                                  tolerance)
        return is_at_key_level, key_level, lookback_length
