import numpy as np
import pandas as pd


class SignalSeriesManager:
    def __init__(self):
        self.close_series = pd.Series(dtype=float)
        self.entries_series = pd.Series(dtype=bool)
        self.exits_series = pd.Series(dtype=bool)
        self.direction_series = pd.Series(dtype=int)
        self.stop_price_series = pd.Series(dtype=float)  # 新增

    def record_entry(self, timestamp, price, direction, stop_price=None):
        self.close_series.loc[timestamp] = price
        self.entries_series.loc[timestamp] = True
        self.exits_series.loc[timestamp] = False
        self.direction_series.loc[timestamp] = direction
        if stop_price is not None:
            self.stop_price_series.loc[timestamp] = stop_price
        else:
            self.stop_price_series.loc[timestamp] = np.nan

    def record_exit(self, timestamp, price):
        self.close_series.loc[timestamp] = price
        self.entries_series.loc[timestamp] = False
        self.exits_series.loc[timestamp] = True
        self.direction_series.loc[timestamp] = 0
        self.stop_price_series.loc[timestamp] = np.nan

    def update_stop(self, timestamp, stop_price):
        self.stop_price_series.loc[timestamp] = stop_price

    def get_stop(self):
        return self.stop_price_series

    def clear(self):
        self.close_series = pd.Series(dtype=float)
        self.entries_series = pd.Series(dtype=bool)
        self.exits_series = pd.Series(dtype=bool)
        self.direction_series = pd.Series(dtype=int)
        self.stop_price_series = pd.Series(dtype=float)

    def get_close(self):
        return self.close_series

    def get_entries(self):
        return self.entries_series

    def get_exits(self):
        return self.exits_series

    def get_directions(self):
        return self.direction_series