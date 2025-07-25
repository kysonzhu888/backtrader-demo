from datetime import datetime
import logging
from xtquant import xtdata

from mini_stock.utils.trading_time_utils import TradingTimeUtils


class MarketDataUtils:
    """市场数据工具类，用于处理市场数据获取相关的逻辑"""

    @staticmethod
    def get_latest_trading_data(code_list, current_date):
        """
        获取最新的交易数据
        如果在交易时间内，返回实时数据（tick级别）
        如果在非交易时间，返回最近的收盘价数据（日线级别）
        
        参数:
            code_list: list, 股票代码列表
            current_date: datetime, 当前日期
        返回:
            dict, 股票数据字典
        """
        try:
            if TradingTimeUtils.is_trading_time():
                # 在交易时间内，获取实时数据（tick级别）
                kline_data = xtdata.get_market_data_ex([], code_list, period='tick', count=1)

                if kline_data:
                    return kline_data

            # 非交易时间或获取实时数据失败，返回最近的收盘价数据（日线级别）
            end_time = current_date.strftime('%Y%m%d')
            daily_data = xtdata.get_market_data_ex([], code_list, period='1d', count=1, end_time=end_time)

            if not daily_data:
                logging.warning("获取日线数据失败")
                return {}

            return daily_data

        except Exception as e:
            logging.error(f"获取行情数据失败: {e}")
            return {}

    @staticmethod
    def get_latest_trading_data_with_period(code_list, current_date, period='1m'):
        """
        获取指定周期的最新交易数据
        
        参数:
            code_list: list, 股票代码列表
            current_date: datetime, 当前日期
            period: str, 数据周期，默认为'1m'（1分钟线）
        返回:
            dict, 股票数据字典
        """
        try:
            if TradingTimeUtils.is_trading_time():
                # 在交易时间内，获取指定周期的数据
                kline_data = xtdata.get_market_data_ex([], code_list, period=period, count=1)

                if kline_data:
                    return kline_data

            # 非交易时间或获取数据失败，返回最近的收盘价数据（日线级别）
            end_time = current_date.strftime('%Y%m%d')
            daily_data = xtdata.get_market_data_ex([], code_list, period='1d', count=1, end_time=end_time)

            if not daily_data:
                logging.warning("获取日线数据失败")
                return {}

            return daily_data

        except Exception as e:
            logging.error(f"获取行情数据失败: {e}")
            return {}

    @staticmethod
    def get_minute_data(code_list, period='1m', count=1, end_time=None):
        """
        获取分钟级别数据
        
        参数:
            code_list: list, 股票代码列表
            period: str, 数据周期，可选值：'1m', '5m', '15m'
            count: int, 获取的数据条数，默认为1
            end_time: str, 结束时间，格式：'YYYYMMDD' 或 'YYYYMMDDHHMMSS'
        返回:
            dict, 分钟级别数据
        """
        try:
            if end_time is None:
                end_time = datetime.now().strftime('%Y%m%d%H%M%S')
            
            minute_data = xtdata.get_market_data_ex(
                [], code_list, period=period, 
                end_time=end_time, count=count
            )
            
            return minute_data if minute_data else {}
        except Exception as e:
            logging.error(f"获取分钟数据失败: {e}")
            return {}

    @staticmethod
    def get_realtime_data(code_list):
        """
        获取实时行情数据
        
        参数:
            code_list: list, 股票代码列表
        返回:
            dict, 实时行情数据
        """
        try:
            kline_data = xtdata.get_market_data_ex([], code_list, period='tick', count=1)
            return kline_data if kline_data else {}
        except Exception as e:
            logging.error(f"获取实时数据失败: {e}")
            return {}

    @staticmethod
    def get_daily_data(code_list, end_date=None, count=1):
        """
        获取日线数据
        
        参数:
            code_list: list, 股票代码列表
            end_date: datetime, 结束日期，默认为当前日期
            count: int, 获取的数据条数，默认为1
        返回:
            dict, 日线数据
        """
        try:
            if end_date is None:
                end_date = datetime.now()
            
            end_time = end_date.strftime('%Y%m%d')
            daily_data = xtdata.get_market_data_ex([], code_list, period='1d', count=count, end_time=end_time)
            
            return daily_data if daily_data else {}
        except Exception as e:
            logging.error(f"获取日线数据失败: {e}")
            return {}

    @staticmethod
    def get_historical_data(code_list, start_date, end_date, period='1d'):
        """
        获取历史数据
        
        参数:
            code_list: list, 股票代码列表
            start_date: datetime, 开始日期
            end_date: datetime, 结束日期
            period: str, 数据周期，默认为'1d'
        返回:
            dict, 历史数据
        """
        try:
            start_time = start_date.strftime('%Y%m%d')
            end_time = end_date.strftime('%Y%m%d')
            
            historical_data = xtdata.get_market_data_ex(
                [], code_list, period=period, 
                start_time=start_time, end_time=end_time
            )
            
            return historical_data if historical_data else {}
        except Exception as e:
            logging.error(f"获取历史数据失败: {e}")
            return {}

    @staticmethod
    def subscribe_minute_data(code_list, period='1m', callback=None):
        """
        订阅分钟级别数据
        
        参数:
            code_list: list, 股票代码列表
            period: str, 数据周期，可选值：'1m', '5m', '15m'
            callback: function, 回调函数
        """
        try:
            for code in code_list:
                xtdata.subscribe_quote(code, period=period, count=-1, callback=callback)
            logging.info(f"已订阅分钟级别数据: {code_list}, 周期: {period}")
        except Exception as e:
            logging.error(f"订阅分钟级别数据失败: {e}")

    @staticmethod
    def download_minute_history_data(code_list, period='1m', start_time='', end_time=''):
        """
        下载分钟级别历史数据
        
        参数:
            code_list: list, 股票代码列表
            period: str, 数据周期，可选值：'1m', '5m', '15m'
            start_time: str, 开始时间，格式：'YYYYMMDD' 或 'YYYYMMDDHHMMSS'
            end_time: str, 结束时间，格式：'YYYYMMDD' 或 'YYYYMMDDHHMMSS'
        """
        try:
            for code in code_list:
                xtdata.download_history_data(code, period=period, start_time=start_time, end_time=end_time)
            logging.info(f"已下载分钟级别历史数据: {code_list}, 周期: {period}")
        except Exception as e:
            logging.error(f"下载分钟级别历史数据失败: {e}") 