import environment  # 确保在其他模块之前导入
import os

import backtrader as bt
import pandas as pd
from datetime import datetime
import logging

from data_frame_helper import DataFrameHelper
from database_helper import DatabaseHelper
from pinbar_strategy import PinbarStrategy
from power_wave_strategy_backup import PowerWaveStrategy
from utils import IntervalUtils


class FeatureProcessCenter:
    """
    通用的期货数据处理中心，支持分钟级别和日线级别 pinbar 检测
    """
    use_backup_strategy = False

    @staticmethod
    def read_feature_data(product_type, interval='1min'):
        db_helper = DatabaseHelper()
        end_time = None
        if os.getenv('DEBUG_MODE') == '1':
            end_time = f'{environment.debug_latest_candle_time}'
        df = db_helper.read_kline_data(product_type, interval=interval, end_time=end_time)
        if df is None or df.empty:
            return None
        # 这里做类型转换、排序、设索引
        time_col = 'trade_date' if interval == '1d' else 'time'
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.dropna(subset=[time_col])
        df = df.sort_values(time_col)
        df = df.set_index(time_col)
        return df

    @staticmethod
    def resample_data_with(product_type, interval='1min'):
        """
        根据 interval 返回重采样后的数据，日线直接返回，无需重采样
        """
        df = FeatureProcessCenter.read_feature_data(product_type, interval=interval)
        if df is None or df.empty:
            return None
        if interval == '1d':
            df['product_type'] = product_type
            df['interval'] = '1d'
            return df
        else:
            # 分钟线重采样逻辑
            interval_num = IntervalUtils.convert_interval_to_minutes(interval)
            if len(df) < interval_num:
                return None
            # 删除重复索引
            df = df[~df.index.duplicated(keep='first')]
            df = df.resample('1min').asfreq().ffill()
            df_resampled = df.resample(interval, closed='right', label='right').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum' if 'volume' in df.columns else 'sum',
                'amount': 'sum' if 'amount' in df.columns else 'sum',
                'oi': 'last' if 'oi' in df.columns else 'last'
            })
            df_resampled.index = df_resampled.index.floor(interval)
            df_resampled = df_resampled.dropna(subset=['open', 'high', 'low', 'close'])
            df_resampled['product_type'] = product_type
            df_resampled['interval'] = interval
            # 使用 DataFrameHelper 类过滤非交易时段
            df_helper = DataFrameHelper(product_type)
            filtered_df_resampled = df_helper.filter_trade_time(df_resampled)
            logging.debug(
                f"resampled data of {interval} have {len(df.columns)} columns, they are :{df.columns} ; {len(filtered_df_resampled)} rows")

            return filtered_df_resampled

    @staticmethod
    def run_pinbar_strategy_with_resampled_data(df):
        if df is None or df.empty:
            logging.error("DataFrame is empty or None")
            return None
        if 'product_type' not in df.columns or df['product_type'].empty:
            return None
        m_product_type = df['product_type'].iloc[0]
        m_interval = df['interval'].iloc[0] if 'interval' in df.columns else '1d'
        interval_num = 1440 if m_interval == '1d' else IntervalUtils.convert_interval_to_minutes(m_interval)
        # 这里加一行，确保数据量大于你用到的最大均线周期，比如20
        min_required = max(20, interval_num)  # 20是你用到的最大均线周期
        if len(df) < min_required:
            logging.warning(f"{m_product_type} {m_interval} 数据量不足（{len(df)} < {min_required}），跳过回测")
            return None
        cerebro = bt.Cerebro()
        data = bt.feeds.PandasData(dataname=df)
        cerebro.adddata(data)
        atr_multiplier = environment.atr_muliter_of(interval_num)
        cerebro.addstrategy(PinbarStrategy, product_type=m_product_type, atr_multiplier=atr_multiplier,
                            interval=m_interval)
        cerebro.run()

    @staticmethod
    def run_power_wave_strategy_with_resampled_data(df):
        if df is None or df.empty:
            logging.error("DataFrame is empty or None")
            return None
        if 'product_type' not in df.columns or df['product_type'].empty:
            return None
        m_product_type = df['product_type'].iloc[0]
        m_interval = df['interval'].iloc[0] if 'interval' in df.columns else '1d'
        interval_num = 1440 if m_interval == '1d' else IntervalUtils.convert_interval_to_minutes(m_interval)
        # 这里加一行，确保数据量大于你用到的最大均线周期，比如20
        min_required = max(34, interval_num)  # 20是你用到的最大均线周期
        if len(df) < min_required:
            logging.warning(f"{m_product_type} {m_interval} 数据量不足（{len(df)} < {min_required}），跳过回测")
            return None
        cerebro = bt.Cerebro()
        data = bt.feeds.PandasData(dataname=df)
        cerebro.adddata(data)
        cerebro.addstrategy(PowerWaveStrategy,interval=m_interval,product_type=m_product_type)

        cerebro.run()