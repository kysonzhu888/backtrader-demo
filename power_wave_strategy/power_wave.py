# import talib


class PowerWave:
    def __init__(self):
        self.close = None
        self.high = None
        self.low = None
        self.vara = None
        self.vard = None
        self.vare = None
        self.bar_height = None
        self.life_line = None

    def update(self, data_window):
        self.close = data_window['Close']
        self.high = data_window['High']
        self.low = data_window['Low']
        self.vara = (2 * self.close + self.high + self.low) / 4
        period_hl = 34
        period_ema1 = 13
        period_ema2 = 2
        varc = self.high.rolling(window=period_hl).max()
        varb = self.low.rolling(window=period_hl).min()
        numerator = self.vara - varb
        denominator = varc - varb
        ratio = (numerator / denominator) * 100
        self.vard = ratio.ewm(span=period_ema1, adjust=False).mean()
        ref_vard = self.vard.shift(1)
        vare_input = 0.667 * ref_vard + 0.333 * self.vard
        self.vare = vare_input.ewm(span=period_ema2, adjust=False).mean()
        # self.life_line = talib.EMA(self.vare, timeperiod=10)
        self.bar_height = abs(self.vard - self.vare)
