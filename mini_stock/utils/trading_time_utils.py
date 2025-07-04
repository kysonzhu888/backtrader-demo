from datetime import datetime, time, timedelta
import logging
from xtquant import xtdata

from date_utils import DateUtils
from mini_stock.utils.time_utils import TimeUtils


class TradingTimeUtils:
    """交易时间工具类，用于处理交易时间相关的逻辑"""

    # 定义交易时段
    MORNING_START = time(9, 30)
    MORNING_END = time(11, 30)
    AFTERNOON_START = time(13, 0)
    AFTERNOON_END = time(15, 0)

    @staticmethod
    def is_trading_day(date=None):
        """
        判断指定日期是否为交易日
        
        参数:
            date: datetime, 可选，默认为当前日期
        返回:
            bool
        """
        try:
            if date is None:
                date = DateUtils.now()

            date_str = date.strftime('%Y%m%d')
            pre_date = datetime.strptime(date_str, '%Y%m%d') - timedelta(days=10)
            pre_date_str = pre_date.strftime('%Y%m%d')
            trading_dates_ts = xtdata.get_trading_dates(market='SH',start_time=pre_date_str)
            trading_dates_str = [TimeUtils.ts_to_datestr(x) for x in trading_dates_ts]


            return date_str in trading_dates_str

        except Exception as e:
            logging.error(f"判断交易日失败: {e}")
            return False

    @staticmethod
    def is_trading_time():
        """
        判断当前是否为交易时间
        返回: bool
        """
        try:
            # 首先判断是否为交易日
            if not TradingTimeUtils.is_trading_day():
                return False

            code = '688701.SH'
            trading_time = xtdata.get_trading_time(stockcode=code)
            return bool(trading_time)
        except Exception as e:
            logging.debug(f"获取交易时间失败: {e} 尝试硬编码实现")
            # 如果API调用失败，使用本地时间判断
            current_time = datetime.now().time()

            # 判断是否在早盘
            in_morning = TradingTimeUtils.MORNING_START <= current_time <= TradingTimeUtils.MORNING_END
            # 判断是否在午盘
            in_afternoon = TradingTimeUtils.AFTERNOON_START <= current_time <= TradingTimeUtils.AFTERNOON_END

            return in_morning or in_afternoon

    @staticmethod
    def get_latest_trading_data(code_list, current_date):
        """
        获取最新的交易数据
        如果在交易时间内，返回实时数据
        如果在非交易时间，返回最近的收盘价数据
        
        参数:
            code_list: list, 股票代码列表
            current_date: datetime, 当前日期
        返回:
            dict, 股票数据字典
        """
        try:
            if TradingTimeUtils.is_trading_time():
                # 在交易时间内，获取实时数据
                kline_data = xtdata.get_market_data_ex([], code_list, period='tick', count=1)

                if kline_data:
                    return kline_data

            # 非交易时间或获取实时数据失败，返回最近的收盘价数据
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
    def get_next_trading_day(date=None):
        """
        获取下一个交易日
        
        参数:
            date: datetime, 可选，默认为当前日期
        返回:
            str, 下一个交易日（格式：YYYYMMDD）
        """
        try:
            if date is None:
                date = datetime.now()

            date_str = date.strftime('%Y%m%d')
            trading_dates = xtdata.get_trading_dates()

            # 找到大于当前日期的第一个交易日
            for trading_date in trading_dates:
                if trading_date > date_str:
                    return trading_date

            return None

        except Exception as e:
            logging.error(f"获取下一个交易日失败: {e}")
            return None
