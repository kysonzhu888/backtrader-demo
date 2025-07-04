# coding:utf-8
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from xtquant import xtdata
from date_utils import DateUtils

@dataclass
class StockInfo:
    """股票信息"""
    code: str  # 股票代码
    name: str  # 股票名称
    price: float  # 当前价格
    market_value: float  # 市值（元）
    days_listed: int  # 上市天数
    min_investment: float  # 最小投资金额（一手）
    market_value_in_yi: float  # 市值（亿元）

@dataclass
class StockFilter:
    """股票筛选条件"""
    min_listed_days: int = 90  # 最小上市天数
    exclude_st: bool = True  # 是否排除ST股票
    exclude_delisted: bool = True  # 是否排除退市股票
    exclude_limit_up: bool = True  # 是否排除涨停股票
    exclude_suspended: bool = True  # 是否排除停牌股票

@dataclass
class ExchangeStats:
    """交易所统计信息"""
    sh_count: int = 0  # 上交所股票数量
    sh_kcb_count: int = 0  # 科创板股票数量
    sz_count: int = 0  # 深交所股票数量
    sz_cyb_count: int = 0  # 创业板股票数量

class StockDataManager:
    @staticmethod
    def get_stock_info(stock: str, date: Optional[datetime] = None) -> Optional[StockInfo]:
        """
        获取单个股票的信息
        
        Args:
            stock: 股票代码
            date: 指定日期，默认为当前日期
            
        Returns:
            Optional[StockInfo]: 股票信息对象，如果获取失败则返回None
        """
        try:
            # 获取股票基本信息
            stock_info = xtdata.get_instrument_detail(stock)
            if stock_info is None:
                return None
                
            # 获取指定日期，如果未指定则使用当前日期
            target_date = date if date else DateUtils.now()
            
            # 检查上市日期
            open_date = stock_info.get('OpenDate', '')
            if not open_date or open_date == '0' or open_date == '19700101':
                logging.warning(f"股票 {stock} 没有有效的上市日期信息")
                return None
                
            # 计算上市天数
            try:
                open_date = datetime.strptime(open_date, '%Y%m%d')
                days_listed = (target_date - open_date).days
                
                # 检查上市日期是否合理（不能早于1990年，不能晚于指定日期）
                if open_date.year < 1990 or open_date > target_date:
                    logging.warning(f"股票 {stock} 上市日期不合理: {open_date.strftime('%Y-%m-%d')}")
                    return None
                    
            except ValueError as e:
                logging.warning(f"股票 {stock} 上市日期格式错误: {open_date}")
                return None
            
            # 获取市值数据
            quote_data = xtdata.get_full_tick([stock])
            if not quote_data or stock not in quote_data:
                return None
                
            quote = quote_data[stock]
            
            # 检查是否停牌
            if quote.get('openInt', 0) == 1:
                logging.info(f"股票 {stock} 当前停牌")
                return None
            
            # 获取总市值（股价 * 总股本）
            market_value = quote['lastPrice'] * stock_info['TotalVolume']
            
            # 计算最小投资金额（一手）
            min_investment = quote['lastPrice'] * 100
            
            # 创建StockInfo对象
            return StockInfo(
                code=stock,
                name=stock_info['InstrumentName'],
                price=quote['lastPrice'],
                market_value=market_value,
                days_listed=days_listed,
                min_investment=min_investment,
                market_value_in_yi=market_value / 100000000
            )
            
        except Exception as e:
            logging.error(f"获取股票{stock}信息时出错: {str(e)}")
            return None

    @staticmethod
    def get_market_share(stocks: List[str], target_date: Optional[datetime] = None) -> Dict[str, float]:
        """
        计算股票列表的市值占比
        
        Args:
            stocks: 股票代码列表
            target_date: 目标日期，默认为当前日期
            
        Returns:
            Dict[str, float]: 包含总市值和占比的字典
            {
                'strategy_value': float,  # 策略总市值（元）
                'market_value': float,    # 市场总市值（元）
                'share_percent': float    # 占比（百分比）
            }
        """
        try:
            # 获取所有A股股票
            all_stocks = xtdata.get_stock_list_in_sector('沪深A股')
            if not all_stocks:
                logging.error("获取股票列表失败")
                return {
                    'strategy_value': 0.0,
                    'market_value': 0.0,
                    'share_percent': 0.0
                }
                
            # 计算市场总市值
            market_value = 0.0
            strategy_value = 0.0
            
            # 批量获取股票信息
            for stock in all_stocks:
                try:
                    # 获取股票基本信息
                    stock_info = xtdata.get_instrument_detail(stock)
                    if stock_info is None:
                        continue
                        
                    # 获取市值数据
                    quote_data = xtdata.get_full_tick([stock])
                    if not quote_data or stock not in quote_data:
                        continue
                        
                    quote = quote_data[stock]
                    
                    # 计算总市值（股价 * 总股本）
                    stock_market_value = quote['lastPrice'] * stock_info['TotalVolume']
                    market_value += stock_market_value
                    
                    # 如果是策略中的股票，累加到策略市值中
                    if stock in stocks:
                        strategy_value += stock_market_value
                    
                except Exception as e:
                    logging.error(f"计算股票{stock}市值时出错: {str(e)}")
                    continue
            
            # 计算占比
            share_percent = (strategy_value / market_value * 100) if market_value > 0 else 0
            
            return {
                'strategy_value': strategy_value,
                'market_value': market_value,
                'share_percent': share_percent
            }
            
        except Exception as e:
            logging.error(f"计算市值占比时出错: {str(e)}")
            return {
                'strategy_value': 0.0,
                'market_value': 0.0,
                'share_percent': 0.0
            }
            
    @staticmethod
    def filter_stocks(filter_condition: StockFilter, target_date: Optional[datetime] = None) -> Dict[str, StockInfo]:
        """
        根据条件筛选股票
        
        Args:
            filter_condition: 筛选条件
            target_date: 目标日期，默认为当前日期
            
        Returns:
            Dict[str, StockInfo]: 股票信息字典，key为股票代码，value为StockInfo对象
        """
        try:
            # 获取所有A股股票
            stocks = xtdata.get_stock_list_in_sector('沪深A股')
            if not stocks:
                logging.error("获取股票列表失败")
                return {}
                
            # 获取目标日期
            target_date = target_date if target_date else DateUtils.now()
            
            # 获取股票信息
            stock_info_dict = {}
            for stock in stocks:
                try:
                    # 获取股票基本信息
                    stock_info = xtdata.get_instrument_detail(stock)
                    
                    # 排除ST和退市股票
                    if stock_info is None:
                        continue
                        
                    if filter_condition.exclude_st and ('ST' in stock_info['InstrumentName'] or stock_info['InstrumentStatus'] > 0):
                        continue

                    if filter_condition.exclude_delisted and ('退' in stock_info['InstrumentName'] or stock_info['InstrumentStatus'] > 0):
                        continue

                    if filter_condition.exclude_delisted and ('退市' in stock_info['InstrumentName'] or stock_info['InstrumentStatus'] > 0):
                        continue
                    
                    # 检查上市日期
                    open_date = stock_info.get('OpenDate', '')
                    if not open_date or open_date == '0' or open_date == '19700101':
                        logging.warning(f"股票 {stock} 没有有效的上市日期信息")
                        continue
                        
                    # 计算上市天数
                    try:
                        open_date = datetime.strptime(open_date, '%Y%m%d')
                        days_listed = (target_date - open_date).days
                        
                        # 检查上市日期是否合理（不能早于1990年，不能晚于目标日期）
                        if open_date.year < 1990 or open_date > target_date:
                            logging.warning(f"股票 {stock} 上市日期不合理: {open_date.strftime('%Y-%m-%d')}")
                            continue
                            
                    except ValueError as e:
                        logging.warning(f"股票 {stock} 上市日期格式错误: {open_date}")
                        continue
                    
                    # 排除上市不足指定天数的股票
                    if days_listed < filter_condition.min_listed_days:
                        logging.info(f"股票 {stock} 上市天数不足{filter_condition.min_listed_days}天: {days_listed}天")
                        continue
                    
                    # 获取市值数据
                    quote_data = xtdata.get_full_tick([stock])
                    if not quote_data or stock not in quote_data:
                        continue
                        
                    quote = quote_data[stock]
                    
                    # 排除停牌股票
                    if filter_condition.exclude_suspended and quote.get('openInt', 0) == 1:
                        logging.info(f"股票 {stock} 当前停牌")
                        continue
                    
                    # 计算涨跌幅
                    pct_chg = (quote['lastPrice'] - quote['lastClose']) / quote['lastClose'] * 100
                    
                    # 排除涨停股票
                    if filter_condition.exclude_limit_up and pct_chg >= 9.5:  # 涨停阈值设为9.5%
                        continue
                    
                    # 获取总市值（股价 * 总股本）
                    market_value = quote['lastPrice'] * stock_info['TotalVolume']
                    
                    # 计算最小投资金额（一手）
                    min_investment = quote['lastPrice'] * 100
                    
                    # 创建StockInfo对象
                    stock_info_obj = StockInfo(
                        code=stock,
                        name=stock_info['InstrumentName'],
                        price=quote['lastPrice'],
                        market_value=market_value,
                        days_listed=days_listed,
                        min_investment=min_investment,
                        market_value_in_yi=market_value / 100000000
                    )
                    
                    stock_info_dict[stock] = stock_info_obj
                    
                except Exception as e:
                    logging.error(f"处理股票{stock}时出错: {str(e)}")
                    continue
                    
            return stock_info_dict
            
        except Exception as e:
            logging.error(f"筛选股票时出错: {str(e)}")
            return {}
            
    @staticmethod
    def get_stock_info_from_dict(stocks: Dict[str, StockInfo], stock: str) -> Optional[StockInfo]:
        """
        从股票字典中获取股票信息
        
        Args:
            stocks: 股票信息字典
            stock: 股票代码
            
        Returns:
            Optional[StockInfo]: 股票信息对象，如果不存在则返回None
        """
        return stocks.get(stock)
        
    @staticmethod
    def get_stock_market_value_from_dict(stocks: Dict[str, StockInfo], stock: str) -> float:
        """
        从股票字典中获取股票市值
        
        Args:
            stocks: 股票信息字典
            stock: 股票代码
            
        Returns:
            float: 股票市值，如果不存在则返回0
        """
        stock_info = stocks.get(stock)
        return stock_info.market_value if stock_info else 0
        
    @staticmethod
    def get_stock_price_change(stock: str) -> Optional[float]:
        """
        获取股票涨跌幅
        
        Args:
            stock: 股票代码
            
        Returns:
            Optional[float]: 涨跌幅，如果获取失败则返回None
        """
        try:
            # 获取最新行情
            quote = xtdata.get_full_tick([stock])
            if not quote or stock not in quote:
                return None
                
            return quote[stock].change_percent
            
        except Exception as e:
            logging.error(f"获取股票{stock}涨跌幅时出错: {str(e)}")
            return None
            
    @staticmethod
    def get_top_stocks_by_market_value(stocks: Dict[str, StockInfo], count: int) -> List[str]:
        """
        获取市值最小的前N只股票
        
        Args:
            stocks: 股票信息字典
            count: 返回的股票数量
            
        Returns:
            List[str]: 股票代码列表
        """
        try:
            # 按市值排序
            sorted_stocks = sorted(stocks.items(), key=lambda x: x[1].market_value)
            
            # 返回前N只股票的代码
            return [stock[0] for stock in sorted_stocks[:count]]
            
        except Exception as e:
            logging.error(f"获取市值最小的股票时出错: {str(e)}")
            return []

    @staticmethod
    def get_exchange_stats(stocks: List[str]) -> ExchangeStats:
        """
        统计股票列表的交易所和板块分布
        
        Args:
            stocks: 股票代码列表
            
        Returns:
            ExchangeStats: 交易所统计信息
        """
        stats = ExchangeStats()
        
        for stock in stocks:
            if stock.endswith('.SH'):
                stats.sh_count += 1
                if stock.startswith('688'):  # 科创板股票代码以688开头
                    stats.sh_kcb_count += 1
            elif stock.endswith('.SZ'):
                stats.sz_count += 1
                if stock.startswith('300'):  # 创业板股票代码以300开头
                    stats.sz_cyb_count += 1
                    
        return stats
        
    @staticmethod
    def format_exchange_stats(stats: ExchangeStats) -> str:
        """
        格式化交易所统计信息
        
        Args:
            stats: 交易所统计信息
            
        Returns:
            str: 格式化后的统计信息
        """
        report = "【成分股分布】\n"
        report += f"上交所: {stats.sh_count}只 (科创板: {stats.sh_kcb_count}只)\n"
        report += f"深交所: {stats.sz_count}只 (创业板: {stats.sz_cyb_count}只)\n"
        return report 