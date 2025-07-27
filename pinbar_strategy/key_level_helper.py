import logging
import os


class KeyLevelHelper:
    period_none = "0"
    strength_none = "strength_none"

    period_0_20 = "0-20"
    period_0_60 = "0-60"
    period_0_120 = "0-120"

    period_20_60 = "20-60"
    period_60_120 = "60-120"
    period_20_120 = "20-120"

    period_40_80 = "40-80"

    strength_strong = "strength_strong"
    strength_weak = "strength_weak"

    @staticmethod
    def identify_key_levels_without_noise(data, lookback=72):
        """
        使用价格行为识别关键位
        :param data: 包含价格数据的对象，通常是 backtrader 的数据 feed
        :param lookback: 回溯的周期数，用于识别高点和低点
        :return: 关键位列表
        """

        # 确保数据长度足够
        if lookback < 1:
            logging.debug(f"数据长度不足以识别关键位")
            return []
        
        # 收集过去 lookback 周期内的最高价、最低价和收盘价，不包括最新一根 K 线
        highs = [data.high[-i-1] for i in range(lookback-2)]  # 获取每个周期的最高价
        lows = [data.low[-i-1] for i in range(lookback-2)]  # 获取每个周期的最低价
        
        # 去除噪音（剔除最高最低）
        highest_high = max(highs)
        lowest_low = min(lows)
        highs.remove(highest_high)
        lows.remove(lowest_low)

        # 根据 lookback 的数量来剔除噪音数据
        if lookback < 23:
            # 只剔除最高价和最低价
            highest_high = max(highs)
            lowest_low = min(lows)

            key_levels = [highest_high, lowest_low]
        elif 23 <= lookback < 65:
            # 剔除最高和次高，最低和次低
            latest_highest = max(highs)
            highs.remove(latest_highest)

            latest_lowest = min(lows)
            lows.remove(latest_lowest)

            highest_high = max(highs)
            lowest_low = min(lows)

            key_levels = [highest_high, lowest_low]
        else:
            # 剔除最高、次高和次次高，最低、次低和次次低
            # 剔除最高和次高，最低和次低
            latest_highest = max(highs)
            highs.remove(latest_highest)
            latest_lowest = min(lows)
            lows.remove(latest_lowest)

            # 剔除最高和次高，最低和次低
            latest_highest = max(highs)
            highs.remove(latest_highest)
            latest_lowest = min(lows)
            lows.remove(latest_lowest)

            highest_high = max(highs)
            lowest_low = min(lows)

            key_levels = [highest_high, lowest_low]


        # 进一步分析可以添加更多的关键位
        # 例如，寻找局部高点和低点

        return key_levels

    def identify_highest_lowest(data, lookback=72):
        """
        使用价格行为识别关键位
        :param data: 包含价格数据的对象，通常是 backtrader 的数据 feed
        :param lookback: 回溯的周期数，用于识别高点和低点
        :return: 关键位列表
        """
        total_length = data.buflen()  # 数据源总长度
        # 确保数据长度足够
        if total_length < lookback:
            logging.debug(f"数据长度不够")
            return None,None

        # 收集过去 lookback 周期内的最高价、最低价和收盘价，不包括最新一根 K 线
        highs = [data.high[-i - 1] for i in range(lookback - 2)]  # 获取每个周期的最高价
        lows = [data.low[-i - 1] for i in range(lookback - 2)]  # 获取每个周期的最低价

        # 去除噪音（剔除最高最低）
        highest_high = max(highs)
        lowest_low = min(lows)

        return highest_high,lowest_low

    @staticmethod
    def evaluate_key_level_strength(data, key_level, lookback=20):
        """
        评估关键位的强弱
        :param data: 包含价格数据的对象，通常是 backtrader 的数据 feed
        :param key_level: 要评估的关键位
        :param lookback: 回溯的周期数，用于评估关键位的强弱
        :return: 关键位的强弱（强、中、弱）
        """
        # 条件 1: 距离越近关键位越强
        recent_prices = []
        for i in range(1, lookback + 1):
            # 收集最近的收盘价
            recent_prices.append(data.close[-i])

        distance_condition = False
        for price in recent_prices:
            # 检查价格是否接近关键位
            if abs(price - key_level) / key_level < 0.01:
                distance_condition = True
                break

        # 条件 2: 通过拐点越多关键位越强
        turning_points = 0
        for i in range(1, lookback):
            high = data.high[-i]
            low = data.low[-i]
            # 检查拐点是否通过关键位
            if high > key_level > low:
                turning_points += 1
        turning_points_condition = turning_points > (lookback / 4)  # 假设 25% 的拐点通过关键位

        # 条件 3: 级别越大关键位越强
        # 这里假设级别是通过某种方式计算的，例如 ATR 或其他指标
        level_condition = data.high[-1] - data.low[-1] > 0.02 * key_level  # 假设级别大于 2%

        # 评估强弱
        conditions_met = sum([distance_condition, turning_points_condition, level_condition])

        if conditions_met == 3:
            return "强"
        elif conditions_met == 2:
            return "中"
        else:
            return "弱"
