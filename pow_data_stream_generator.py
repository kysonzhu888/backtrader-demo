import logging
import os

import pandas as pd

import environment
from back_trace_paradigm import HistoricalDataLoader, DataProcessor
from database_helper import DatabaseHelper


# ======================
# 1. 实时数据流生成器
# ======================
class PowDataStreamGenerator:
    def __init__(self, product_type, interval='1min'):
        """从数据库读取实时数据"""
        self.db_helper = DatabaseHelper()
        self.product_type = product_type
        self.interval = interval
        self.last_timestamp = None
        self.data_window = pd.DataFrame()

        # 加载历史数据
        end_time = environment.debug_latest_candle_time if os.getenv('DEBUG_MODE') == '1' else None
        self.data_window = HistoricalDataLoader.load_historical_data(product_type=self.product_type,
                                                                     interval=self.interval, end_time=end_time)
        if self.data_window is not None and not self.data_window.empty:
            self.last_timestamp = self.data_window.index[-1]
            logging.info(
                f"初始化完成，已加载 {len(self.data_window)} 条历史数据,最后一条数据的时间是{self.last_timestamp}")
        else:
            logging.info("初始化完成，未加载历史数据（使用CSV文件作为数据源）")

    def next(self):
        """获取下一根K线数据"""
        try:
            # 读取最新数据
            end_time = environment.debug_latest_candle_time if os.getenv('DEBUG_MODE') == '1' else None
            df = DataProcessor.read_latest_data(self.product_type, self.interval, end_time=end_time)

            new_data = DataProcessor.process_new_data(df, self.interval, self.last_timestamp)
            if new_data is not None:
                self.last_timestamp = new_data.name
            return new_data

        except Exception as e:
            logging.error(f"获取数据时发生错误: {e}")
            return None
