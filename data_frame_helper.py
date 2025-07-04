import environment
import logging

import pandas as pd

from date_utils import DateUtils
from trading_time_helper import TradingTimeHelper
from datetime import datetime, time
from environment import special_days


class DataFrameHelper:
    def __init__(self, product_type):
        """
        初始化 DataFrameHelper 类，设置产品类型。

        :param product_type: 产品类型，用于获取交易时间。
        """
        self.product_type = product_type

    def filter_trade_time(self, df):
        """
        过滤数据帧中的交易时间，确保只保留在指定交易时段内的数据。

        :param df: 包含时间索引的数据帧。
        :return: 过滤后的数据帧，仅包含在交易时段内的数据。
        """
        # 确保数据帧的索引是日期时间格式
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)  # 将索引转换为日期时间格式

        # 获取当前产品的交易时段
        trade_hours = TradingTimeHelper(self.product_type).trading_time()

        # 初始化空DataFrame
        filtered_dfs = []

        # 遍历每个交易时段
        for start, end in trade_hours:
            # 处理跨午夜时段（例如00:00-01:00）
            if start > end:
                # 分两段筛选：当日结束时间到午夜 + 午夜到次日结束时间
                evening = df.between_time(start, '00:00:00')
                morning = df.between_time('00:00:01', end)
                filtered = pd.concat([morning, evening])
            else:
                filtered = df.between_time(start, end)

            filtered_dfs.append(filtered)

        # 合并所有时段数据并去重
        all_filtered_dfs = pd.concat(filtered_dfs)

        # 处理因数据采集错误或合并导致的重复时间戳
        filtered_duplicate_dfs = all_filtered_dfs[~all_filtered_dfs.index.duplicated(keep='first')]

        df_ascending_time = filtered_duplicate_dfs.sort_index(ascending=True)  # 按时间升序排列

        # 过滤掉非交易日的数据
        trading_helper = TradingTimeHelper(self.product_type)
        df_filter_no_trading_day = df_ascending_time[df_ascending_time.index.map(lambda timestamp: trading_helper.is_trading_day(timestamp.date()))]
        
        # 检查特殊日期配置
        for special_date_str, config in environment.special_days.items():
            special_date = datetime.strptime(special_date_str, '%Y-%m-%d')
            if special_date.date() in df_filter_no_trading_day.index.date:
                if config.get('no_night_session', False):
                    df_filter_no_trading_day = df_filter_no_trading_day[~((df_filter_no_trading_day.index.date == special_date.date()) &
                                                  (df_filter_no_trading_day.index.time >= time(21, 0)) &
                                                  (df_filter_no_trading_day.index.time <= time(23, 0)))]

        return df_filter_no_trading_day
