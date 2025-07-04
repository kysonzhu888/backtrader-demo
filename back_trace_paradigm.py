import environment
import logging
from datetime import datetime, timedelta

from csv_file_path_manager import CSVFilePathManager
from database_helper import DatabaseHelper
import pandas as pd
import os
import numpy as np
import time

from micro_defs import Minimum_Data_Count
from trading_time_helper import TradingTimeHelper

MAX_HISTORY_DATA_NUM = 500

class DebugTimeManager:
    @staticmethod
    def update_debug_time(current_time: datetime, trading_helper) -> str:
        """
        更新debug时间，如果当前时间不是交易时间，则找到下一个交易时间点。
        如果下个交易时间超过当前真实时间，则判定为无法找到下一个交易时间点，返回None。
        """
        if not trading_helper.is_trading_time(current_time):
            next_trading_time: datetime = DebugTimeManager.find_next_trading_time(current_time, trading_helper)
            if next_trading_time is None:
                logging.info("无法找到下一个交易时间点，结束回测")
                return None
            current_os_time: datetime = datetime.strptime(environment.debug_current_os_time, '%Y-%m-%d %H:%M:%S')
            if next_trading_time > current_os_time:
                logging.info("下一个交易时间超过当前真实时间，结束回测")
                return None
            environment.debug_latest_candle_time = next_trading_time.strftime('%Y-%m-%d %H:%M:%S')
            logging.info(f"当前时间 {current_time} 不是交易时间，已调整到下一个交易时间点: {next_trading_time}")
        else:
            environment.debug_latest_candle_time = (current_time + timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
        return environment.debug_latest_candle_time

    @staticmethod
    def find_next_trading_time(current_time, trading_helper):
        """
        找到下一个交易时间点
        通过每次增加1分钟的方式查找下一个交易时间
        """
        # 最多查找8天（国庆和春节）
        max_attempts = 9 * 24 * 60  # 7天 * 24小时 * 12次/小时
        attempts = 0

        while attempts < max_attempts:
            # 检查当前时间是否为交易时间
            if trading_helper.is_trading_time(current_time):
                return current_time

            # 增加1分钟
            current_time = current_time + timedelta(minutes=1)
            attempts += 1

        # 如果找不到，返回当前时间加15分钟
        return None


class HistoricalDataLoader:
    @staticmethod
    def _get_required_days(interval):
        """根据周期获取需要加载的天数"""
        interval_days_map = {
            '1min': 2,
            '5min': 5,
            '15min': 10,
            '30min': 20,
            '60min': 30,
            '1d': 40
        }
        return interval_days_map.get(interval, 2)

    @staticmethod
    def _limit_data_by_days(data, days, interval):
        """限制数据加载的数量
        
        Args:
            data: 原始数据
            days: 天数（不再使用）
            interval: 时间周期，用于计算需要的数据条数
            
        Returns:
            DataFrame: 限制后的数据
        """
        if data is None or data.empty or len(data) == 0:
            return data

        # 根据周期计算需要的数据条数
        interval_bars_map = {
            '1min': 100,
            '5min': 100 * 5,
            '15min': 100 * 15,
            '30min': 100 * 30,
            '60min': 100 * 60,
            '1d': 100 * 24 * 60
        }

        required_bars = interval_bars_map.get(interval, 100)
        limited_data = data.tail(required_bars)
        logging.info(f"已限制加载最近{required_bars}条数据，共{len(limited_data)}条")
        return limited_data

    @staticmethod
    def _build_kline_dataframe(df, time_col):
        """构建K线数据DataFrame"""
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.dropna(subset=[time_col])
        df = df.sort_values(time_col)
        df = df.set_index(time_col)

        return pd.DataFrame({
            'Open': df['open'],
            'High': df['high'],
            'Low': df['low'],
            'Close': df['close'],
            'Volume': df['volume'] if 'volume' in df.columns else 0
        })

    @staticmethod
    def load_historical_data(product_type, interval, end_time):
        """加载历史数据，包括较大周期数据"""
        try:
            # 检查是否存在CSV文件
            csv_path = CSVFilePathManager.get_split_file_path_by_year(product_type, 2025)
            if os.path.exists(csv_path):
                logging.info(f"发现CSV文件 {csv_path}，从CSV文件加载数据")
                # 获取1分钟数据
                one_min_data = DataProcessor.read_csv_data(csv_path, end_time=end_time,limit=MAX_HISTORY_DATA_NUM )
                if one_min_data is not None and not one_min_data.empty:
                    logging.info(f'已限制加载最近{MAX_HISTORY_DATA_NUM}条数据，共{len(one_min_data)}条')
                    return one_min_data
            else:
                logging.info("没有找到 csv 文件，下面开始读取数据库")

            # 从数据库读取数据
            db_helper = DatabaseHelper()
            df = db_helper.read_kline_data(
                product_type=product_type,
                interval=interval,
                end_time=end_time
            )

            if df is not None and not df.empty:
                # 处理时间列并构建K线数据
                time_col = 'trade_date' if interval == '1d' else 'time'
                data_window = HistoricalDataLoader._build_kline_dataframe(df, time_col)

                # 更新最后时间戳
                if not data_window.empty:
                    last_timestamp = data_window.index[-1]
                    logging.info(f"历史数据加载完成，最新时间戳: {last_timestamp}")
                    if os.getenv('DEBUG_MODE') == '1':
                        logging.info(f"Debug模式：数据已过滤到 {end_time} 之前")
                    return data_window
        except Exception as e:
            logging.error(f"加载历史数据时发生错误: {e}")
        return None


class TimeRangeManager:
    """时间范围管理器，统一管理时间范围计算"""

    @staticmethod
    def calculate_time_range(cur_time, interval, extra_days=0):
        """
        计算时间范围
        
        Args:
            cur_time: 当前时间
            interval: 时间周期（如 '5min', '15min' 等）
            extra_days: 额外增加的天数
            
        Returns:
            tuple: (start_time, end_time) 时间范围的字符串表示
        """
        end_time = cur_time.strftime('%Y-%m-%d %H:%M:%S')

        # 根据周期计算需要的历史数据量
        interval_days_map = {
            '5min': 2,
            '15min': 3,
            '30min': 4,
            '60min': 5,
            '1d': 10
        }

        days = interval_days_map.get(interval, 2) + extra_days
        start_time = (cur_time - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

        return start_time, end_time


class DataProcessor:
    @staticmethod
    def read_csv_data(csv_path, start_time=None, end_time=None, limit=None):
        """读取CSV文件数据
        
        Args:
            csv_path: CSV文件路径
            start_time: 开始时间，用于过滤数据
            end_time: 结束时间，用于过滤数据
            limit: 限制返回的数据条数，如果为None则返回所有数据
            
        Returns:
            DataFrame: 处理后的数据
        """
        try:
            # 读取CSV文件
            df = pd.read_csv(
                csv_path,
                usecols=['date', 'open', 'high', 'low', 'close', 'volume'],
                parse_dates=['date']
            )

            if df is None or df.empty:
                logging.warning(f"CSV文件 {csv_path} 为空或读取失败")
                return None

            # 检查必要的列是否存在
            required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logging.error(f"CSV文件 {csv_path} 缺少必要的列: {missing_columns}")
                return None

            # 如果有开始时间，过滤数据
            if start_time:
                start_time_dt = pd.to_datetime(start_time)
                df = df[df['date'] >= start_time_dt]
                if df.empty:
                    logging.warning(f"过滤后没有数据，start_time: {start_time}")
                    return None

            # 如果有结束时间，过滤数据
            if end_time:
                end_time_dt = pd.to_datetime(end_time)
                df = df[df['date'] <= end_time_dt]
                if df.empty:
                    logging.warning(f"过滤后没有数据，end_time: {end_time}")
                    return None

            # 重命名列以匹配数据库格式
            df = df.rename(columns={
                'date': 'time',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            })

            # 设置时间索引并按时间倒序排序
            df = df.set_index('time')
            df = df.sort_index(ascending=False)

            # 如果指定了限制，只获取指定数量的数据(取最新的)
            if limit:
                df = df.head(limit)
                if df.empty:
                    logging.warning(f"限制后没有数据，limit: {limit}")
                    return None

            # 构建K线数据
            data_window = pd.DataFrame({
                'Open': df['open'],
                'High': df['high'],
                'Low': df['low'],
                'Close': df['close'],
                'Volume': df['volume']
            })

            # 按时间正序排序
            return data_window.sort_index()
        except Exception as e:
            logging.error(f"处理CSV数据时发生错误: {e}")
            return None

    @staticmethod
    def read_latest_data(product_type, interval, start_time=None, end_time=None):
        """读取最新数据，支持从数据库或CSV文件读取"""
        try:
            # 如果 end_time 存在但 start_time 为空，设置默认的 start_time
            if end_time and not start_time:
                end_time_dt = pd.to_datetime(end_time)
                start_time, _ = TimeRangeManager.calculate_time_range(end_time_dt, interval, extra_days=2)

            # 首先尝试从CSV文件读取
            csv_path = CSVFilePathManager.get_split_file_path_by_year(product_type, 2025)
            if os.path.exists(csv_path):
                # 读取CSV数据（始终读取1分钟数据）
                df = DataProcessor.read_csv_data(csv_path, start_time=start_time, end_time=end_time)
                if df is not None and not df.empty:
                    # 如果有开始时间，过滤数据
                    if start_time:
                        start_time_dt = pd.to_datetime(start_time)
                        df = df[df.index >= start_time_dt]
                        if df.empty:
                            logging.warning(f"过滤后没有数据，start_time: {start_time}, end_time: {end_time}")
                            return None

                    # 更新缓存
                    return df
                return None

            # 如果CSV文件不存在，则从数据库读取
            db_helper = DatabaseHelper()
            df = db_helper.read_kline_data(
                product_type=product_type,
                interval=interval,
                end_time=end_time,
                limit=1
            )
            return df
        except Exception as e:
            logging.error(f"读取最新数据时发生错误: {e}")
            return None

    @staticmethod
    def process_new_data(df, interval, last_timestamp):
        """处理新数据，返回处理后的数据"""
        if df is None or df.empty:
            logging.warning(f"无法获取数据")
            return None

        # 处理时间列
        time_col = 'trade_date' if interval == '1d' else 'time'
        if time_col not in df.columns and df.index.name == time_col:
            # 如果时间列已经是索引，则重置索引
            df = df.reset_index()

        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.dropna(subset=[time_col])
        df = df.sort_values(time_col)
        df = df.set_index(time_col)

        logging.debug(f"当前数据最新时间戳: {df.index[-1]}, last_timestamp: {last_timestamp}")

        # 检查是否有新数据
        if last_timestamp is not None and df.index[-1] <= last_timestamp:
            logging.debug("没有新数据")
            return None

        # 更新最后时间戳
        last_timestamp = df.index[-1]
        logging.debug(f"更新 last_timestamp 为: {last_timestamp}")

        # 检查列名是否已经是处理过的格式
        if 'Open' in df.columns and 'High' in df.columns and 'Low' in df.columns and 'Close' in df.columns:
            # 已经是处理过的格式，直接使用
            new_data = pd.Series({
                'Open': df['Open'].iloc[-1],
                'High': df['High'].iloc[-1],
                'Low': df['Low'].iloc[-1],
                'Close': df['Close'].iloc[-1],
                'Volume': df['Volume'].iloc[-1] if 'Volume' in df.columns else 0
            }, name=last_timestamp)
        else:
            # 需要转换列名
            new_data = pd.Series({
                'Open': df['open'].iloc[-1],
                'High': df['high'].iloc[-1],
                'Low': df['low'].iloc[-1],
                'Close': df['close'].iloc[-1],
                'Volume': df['volume'].iloc[-1] if 'volume' in df.columns else 0
            }, name=last_timestamp)

        return new_data.astype(np.float64)
