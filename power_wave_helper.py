import pandas as pd

from micro_defs import MACDCross


class PowerWaveHelper:
    @classmethod
    def get_macd_cross(cls, macd_indicator):
        """
        判断当前K线是否发生MACD金叉或死叉。
        :param macd_indicator: Backtrader的MACD指标对象
        :return: '金叉'、'死叉'或''
        """
        if len(macd_indicator.macd) > 1:
            prev_dif = macd_indicator.macd[-1]
            prev_dea = macd_indicator.signal[-1]
            curr_dif = macd_indicator.macd[0]
            curr_dea = macd_indicator.signal[0]
            # if prev_dif < prev_dea and curr_dif > curr_dea:
            #     return '金叉'
            # elif prev_dif > prev_dea and curr_dif < curr_dea:
            #     return '死叉'

            if curr_dif > curr_dea:
                return MACDCross.GOLDEN.value
            else:
                return MACDCross.DEAD.value

    @staticmethod
    def check_boll_condition(data_close, direction):
        """
        检查布林带条件
        :param data_close: 收盘价序列
        :param direction: 方向（多/空）
        :return: 是否满足条件
        """
        window = 20
        if len(data_close) < window:
            return None

        # 使用 iloc 按位置访问数据
        close_list = [data_close.iloc[-i-1] for i in range(window)]
        close_series = pd.Series(close_list)
        
        # 计算布林带
        ma = close_series.mean()
        std = close_series.std()
        # upper = ma + 2 * std
        # lower = ma - 2 * std
        
        # 判断条件
        if direction == '多':
            return data_close.iloc[-1] >= ma
        elif direction == '空':
            return data_close.iloc[-1] < ma
        return None
