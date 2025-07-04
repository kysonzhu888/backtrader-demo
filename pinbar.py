from k_line import KLine
from key_level_helper import KeyLevelHelper


class PinbarType:
    type_bearish = "type_bearish"
    type_none = "type_none"
    type_bullish = "type_bullish"


class Pinbar:

    class Score:
        score_1 = "visually prominent"  # pinbar明显
        score_2 = "false breakout"  # pinbar有假突破
        score_3 = "body fall within the high-low range of the preceding K-line,and amplitude larger than the preceding K-line"  # 实体有没有包含在之前的K线(左眼)的最高价和最低价之内，并且信号的幅度要大于左眼？
        score_4 = "aligned with the higher timeframe trend"  # 顺着较大级别趋势
        score_5 = "risk-reward ratio for the breakout entry exceed 1.5:1"  # 突破入场的盈亏比是否大于1.5︰1
        score_6 = "no obvious acceleration in the current trend compared to earlier phases, OR is there a buffer trend preceding the signal"  # 信号所处波段的趋势对比前期走势是否没有出现明显的加速？或者信号前面是否有缓冲趋势？

    def __init__(self, kline):
        self.score_detail = []
        self.type = PinbarType.type_none
        self.kline = kline
        self.key_level_period = KeyLevelHelper.period_none
        self.key_level_strength = KeyLevelHelper.strength_none
        self.is_excellent = False

    def get_open(self):
        return self.kline.open

    def get_close(self):
        return self.kline.close

    def get_high(self):
        return self.kline.high

    def get_low(self):
        return self.kline.low

    def get_length(self):
        len = abs(self.kline.high - self.kline.low)
        return len

    def get_interval(self):
        return self.kline.interval

    def __str__(self):
        return f"pinbar:({self.kline}, type={self.type},score={len(self.score_detail)},score_detail={self.score_detail})"
