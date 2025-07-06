import backtrader as bt
import pandas as pd
import numpy as np

import backtrader as bt


class PowerWave(bt.Indicator):
    lines = ('vard', 'vare', 'life', 'level50', 'top80', 'bottom20')
    plotinfo = dict(subplot=True)  # 副图显示

    params = (
        ('period_hl', 34),  # 高低价周期
        ('period_ema1', 13),  # 首层EMA周期
        ('period_ema2', 2),  # 二次EMA周期
        ('life_period', 10),  # 生命线周期
    )

    def __init__(self):
        # 计算中间变量
        vara = (2 * self.data.close + self.data.high + self.data.low) / 4
        varb = bt.indicators.Lowest(self.data.low, period=self.p.period_hl)
        varc = bt.indicators.Highest(self.data.high, period=self.p.period_hl)

        # 核心计算逻辑
        numerator = vara - varb
        denominator = varc - varb
        ratio = (numerator / denominator) * 100
        self.lines.vard = bt.indicators.EMA(ratio, period=self.p.period_ema1)

        ref_vard = self.lines.vard(-1)  # REF(VARD,1)
        vare_input = 0.667 * ref_vard + 0.333 * self.lines.vard
        self.lines.vare = bt.indicators.EMA(vare_input, period=self.p.period_ema2)

        # 辅助线
        self.lines.life = bt.indicators.EMA(self.lines.vare, period=self.p.life_period)
        # self.lines.level50 = 50  # 固定水平线
        # self.lines.top80 = 80
        # self.lines.bottom20 = 20

        # 可视化配置
        self.plotlines = dict(
            vard=dict(color='red', alpha=0.5),
            vare=dict(color='blue', alpha=0.5),
            life=dict(color='gray', linewidth=2),
            level50=dict(color='black', ls='--'),
            top80=dict(color='green', ls='--'),
            bottom20=dict(color='red', ls='--')
        )

    def next(self):
        self.lines.level50[0] = 50
        self.lines.top80[0] = 80
        self.lines.bottom20[0] = 20
