# coding:utf-8
import logging
import os
import sys
from datetime import datetime, timedelta
from date_utils import DateUtils
from xtquant import xtdata
from typing import Optional, Dict, Any, List

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from mini_stock.utils.time_utils import TimeUtils
from mini_stock.utils.trading_time_utils import TradingTimeUtils


class StockPriceUtils:
    @staticmethod
    def get_prev_trade_date(date_str: str) -> str:
        """
        用xtdata获取A股前一个交易日
        Args:
            date_str: 当前日期，格式YYYYMMDD
        Returns:
            str: 前一个交易日，格式YYYYMMDD
        """
        # 自动计算date_str往前推10天的start_time
        dt = datetime.strptime(date_str, '%Y%m%d')
        start_time = (dt - timedelta(days=10)).strftime('%Y%m%d')
        trade_days = xtdata.get_trading_dates('SH', start_time=start_time, end_time=date_str)
        trade_days_str = [TimeUtils.ts_to_datestr(ts) for ts in trade_days]
        trade_days_str = [d for d in trade_days_str if d]  # 只保留合法日期字符串
        prev_days = [d for d in trade_days_str if d < date_str]
        if prev_days:
            return prev_days[-1]
        return date_str  # fallback

    @staticmethod
    def get_stock_price_change(stock: str, target_date: Optional[str] = None) -> Optional[float]:
        """
        获取股票涨跌幅
        
        Args:
            stock: 股票代码
            target_date: 目标日期，格式为YYYYMMDD，默认为当前日期
            
        Returns:
            Optional[float]: 涨跌幅，如果获取失败则返回None
        """
        try:
            # 获取目标日期
            target_datetime = None
            if target_date:
                try:
                    target_datetime = datetime.strptime(target_date, '%Y%m%d')
                except ValueError as e:
                    logging.error(f"目标日期格式错误: {target_date}")
                    return None
            else:
                target_datetime = DateUtils.now()

            target_date_str = target_datetime.strftime('%Y%m%d')
            prev_date_str = StockPriceUtils.get_prev_trade_date(target_date_str)

            # 增量下载行情数据
            xtdata.download_history_data(stock, period='1d', incrementally=True)

            # 获取历史数据
            result = xtdata.get_market_data_ex(field_list=['close'],
                                               stock_list=[stock],
                                               period='1d',
                                               start_time=prev_date_str,
                                               end_time=prev_date_str,
                                               count=1)

            if result is None or stock not in result:
                return None

            # 获取前一日收盘价
            prev_price = None
            if 'close' in result[stock]:
                close_data = result[stock]['close']
                if not close_data.empty:
                    prev_price = close_data.iloc[0]

            if prev_price is None:
                return None

            # 获取当前价格
            current_price = StockPriceUtils.get_current_price(stock, target_date)
            if current_price is None:
                return None

            # 计算涨跌幅
            return (current_price - prev_price) / prev_price * 100

        except Exception as e:
            logging.error(f"获取股票{stock}涨跌幅时出错: {str(e)}")
            return None

    @staticmethod
    def get_current_price(stock: str, target_date: Optional[str] = None) -> Optional[float]:
        """
        获取股票当前价格
        
        Args:
            stock: 股票代码
            target_date: 目标日期，格式为YYYYMMDD，默认为当前日期
            
        Returns:
            Optional[float]: 当前价格，如果获取失败则返回None
        """
        try:
            # 使用TradingTimeUtils判断是否为交易时间
            if TradingTimeUtils.is_trading_time():
                # 在交易时间内，获取实时数据
                quote = xtdata.get_full_tick([stock])
                if not quote or stock not in quote:
                    return None

                return quote[stock].get('lastPrice', 0.0)
            else:
                # 非交易时间，获取最近的收盘价
                if target_date is None:
                    target_date = DateUtils.now().strftime('%Y%m%d')

                # 获取最近的交易日数据
                result = xtdata.get_market_data_ex(field_list=['close'],
                                                   stock_list=[stock],
                                                   period='1d',
                                                   end_time=target_date,
                                                   count=1)

                if result is None or stock not in result:
                    return None

                if 'close' in result[stock]:
                    close_data = result[stock]['close']
                    if not close_data.empty:
                        return close_data.iloc[-1]

                return None

        except Exception as e:
            logging.error(f"获取股票{stock}当前价格时出错: {str(e)}")
            return None

    @staticmethod
    def get_stock_price_changes(stocks: List[str], target_date: Optional[str] = None) -> Dict[str, float]:
        """
        批量获取股票涨跌幅
        
        Args:
            stocks: 股票代码列表
            target_date: 目标日期，格式为YYYYMMDD，默认为当前日期
            
        Returns:
            Dict[str, float]: 股票涨跌幅字典，key为股票代码，value为涨跌幅
        """
        try:
            changes = {}
            for stock in stocks:
                pct_chg = StockPriceUtils.get_stock_price_change(stock, target_date)
                if pct_chg is not None:
                    changes[stock] = pct_chg
            return changes

        except Exception as e:
            logging.error(f"批量获取股票涨跌幅时出错: {str(e)}")
            return {}

    @staticmethod
    def get_preclose(code):
        try:
            end_time = DateUtils.now().strftime('%Y%m%d')
            daily = xtdata.get_market_data_ex([], [code], period='1d', count=2, end_time=end_time)
            if code in daily and not daily[code].empty and len(daily[code]) >= 2:
                pre_item = daily[code].iloc[0]
                return pre_item['close']
        except Exception as e:
            logging.error(f"获取{code}前收盘价失败: {e}")
        return None

    @staticmethod
    def get_all_preclose(code_list):
        for i in code_list:
            xtdata.download_history_data(i, period='1d', incrementally=True)
        preclose_dict = {}
        for code in code_list:
            preclose = StockPriceUtils.get_preclose(code)
            if preclose:
                preclose_dict[code] = preclose
        logging.info(f"成功拉取上个日数据 {len(preclose_dict)} 条")
        return preclose_dict
