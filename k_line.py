

class KLine:
    high = 0
    low = 0
    open = 0
    close = 0

    period_1min = "1min"
    period_3min = "3min"
    period_5min = "5min"
    period_15min = "15min"
    period_20min = "20min"
    period_30min = "30min"
    period_40min = "40min"
    period_45min = "45min"
    period_60min = "60min"
    period_120min = "120min"

    def __init__(self, high, low, open, close,period="1min"):
        self.high = high
        self.low = low
        self.open = open
        self.close = close
        self.period = period

    def set_interval(self,interval):
        self.period = interval

    def set_period(self,period):
        self.period = period

    def __str__(self):
        return f" kline:(open={self.open},close={self.close},high={self.high},low={self.low}, period={self.period})"

