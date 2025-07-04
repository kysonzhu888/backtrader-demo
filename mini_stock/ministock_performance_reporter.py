# coding:utf-8
import os
import logging
from datetime import datetime
from date_utils import DateUtils
from wechat_helper import WeChatHelper
import environment
from stock_data_manager import StockDataManager
from mini_stock.utils.stock_price_utils import StockPriceUtils
from typing import Optional, Tuple
from dataclasses import dataclass
from xtquant import xtdata
from mini_stock_report_reader import MiniStockReportReader
from stock_cache_manager import StockCacheManager
import matplotlib
matplotlib.use('Agg')
from report_image_generator import ReportImageGenerator

@dataclass
class StockInfo:
    """股票信息类"""
    code: str  # 股票代码
    index: int  # 序号
    name: str  # 股票名称

class MiniStockPerformanceReporter:
    def __init__(self):
        self.report_dir = "reports"
        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)
            
    def _save_report(self, report: str, date_str: str) -> Optional[str]:
        """
        保存报告到文件
        
        Args:
            report: 报告内容
            date_str: 日期字符串，格式为YYYYMMDD
            
        Returns:
            Optional[str]: 报告文件路径，如果保存失败则返回None
        """
        try:
            # 生成报告文件名
            report_file = os.path.join(self.report_dir, f"ministock_performance_{date_str}.txt")
            
            # 保存报告
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
                
            logging.info(f"报告已保存到文件: {report_file}")
            return report_file
            
        except Exception as e:
            logging.error(f"保存报告时出错: {str(e)}")
            return None
            
    def _calculate_stock_performance(self, stock: str, start_date: str, target_date: Optional[str] = None) -> Tuple[float, float, float]:
        """
        计算单个股票的表现
        
        Returns:
            Tuple[float, float, float]: (当日收益, 当日收益率, 累计收益率)
        """
        try:
            # 获取当前价格
            current_price = StockPriceUtils.get_current_price(stock, target_date)
            if current_price is None:
                return 0.0, 0.0, 0.0

            # 获取目标日期和前一交易日
            if target_date:
                target_date_str = target_date
            else:
                target_date_str = DateUtils.now().strftime('%Y%m%d')
            prev_trade_date = StockPriceUtils.get_prev_trade_date(target_date_str)

            # 获取前一交易日收盘价
            xtdata.download_history_data(stock, period='1d', incrementally=True)
            prev_result = xtdata.get_market_data_ex(field_list=['close'],
                                                    stock_list=[stock],
                                                    period='1d',
                                                    start_time=prev_trade_date,
                                                    end_time=prev_trade_date,
                                                    count=1)
            prev_close = None
            if prev_result and stock in prev_result and 'close' in prev_result[stock]:
                close_data = prev_result[stock]['close']
                if not close_data.empty:
                    prev_close = close_data.iloc[0]
            if prev_close is None:
                return 0.0, 0.0, 0.0

            # 获取调仓日价格
            start_result = xtdata.get_market_data_ex(field_list=['close'],
                                                     stock_list=[stock],
                                                     period='1d',
                                                     start_time=start_date,
                                                     end_time=start_date,
                                                     count=1)
            start_price = None
            if start_result and stock in start_result and 'close' in start_result[stock]:
                close_data = start_result[stock]['close']
                if not close_data.empty:
                    start_price = close_data.iloc[0]
            if start_price is None:
                return 0.0, 0.0, 0.0

            # 计算
            daily_profit = (current_price - prev_close) * 100
            daily_pct_chg = (current_price - prev_close) / prev_close * 100
            total_return = (current_price - start_price) / start_price * 100

            return daily_profit, daily_pct_chg, total_return

        except Exception as e:
            logging.error(f"计算股票{stock}表现时出错: {str(e)}")
            return 0.0, 0.0, 0.0
            
    def broadcast_performance(self, report_date: str, target_date: Optional[str] = None) -> None:
        """
        播报微盘股绩效
        
        Args:
            report_date: 微盘股调仓日期，格式为YYYYMMDD
            target_date: 指定日期，格式为YYYYMMDD，默认为当前日期
        """
        try:
            # 读取股票列表
            codes = MiniStockReportReader.read_stock_codes(self.report_dir, report_date)
            # 加载股票名称缓存
            cache_manager = StockCacheManager()
            cache = cache_manager.load_cache()
            stocks = []
            for idx, code in enumerate(codes, 1):
                name = cache.get(code, "")
                stock = StockInfo(code=code, index=idx, name=name)
                stocks.append(stock)

            if not stocks:
                return
            
            # 计算每只股票的表现
            stock_performances = {}
            total_daily_profit = 0.0
            total_daily_return = 0.0
            total_investment = 0.0
            total_cum_profit = 0.0
            total_cum_return = 0.0
            
            # 转换目标日期为datetime对象
            target_datetime = None
            if target_date:
                try:
                    target_datetime = datetime.strptime(target_date, '%Y%m%d')
                except ValueError as e:
                    logging.error(f"目标日期格式错误: {target_date}")
                    return
            
            for stock_info in stocks:
                daily_profit, daily_return, total_return = self._calculate_stock_performance(
                    stock_info.code, report_date, target_date)
                stock_data = StockDataManager.get_stock_info(stock_info.code, target_datetime)
                if stock_data:
                    stock_performances[stock_info.code] = {
                        'name': stock_data.name,
                        'index': stock_info.index,
                        'daily_profit': daily_profit,
                        'daily_return': daily_return,
                        'total_return': total_return,
                        'price': stock_data.price,
                        'market_value': stock_data.market_value
                    }
                    total_daily_profit += daily_profit
                    total_daily_return += daily_return
                    total_investment += stock_data.price * 100
                    total_cum_profit += (stock_data.price - self._get_start_price(stock_info.code, report_date)) * 100
                    total_cum_return += total_return
            
            # 计算总收益率
            total_daily_return_rate = total_daily_return / len(stocks) if stocks else 0
            total_cum_return_rate = total_cum_return / len(stocks) if stocks else 0
            
            # 生成播报消息
            message = f"【微盘股策略绩效播报】\n"
            message += f"日期: {target_date if target_date else DateUtils.now().strftime('%Y-%m-%d')}\n\n"
            
            # 添加总体表现
            message += "【总体表现】\n"
            message += f"持仓数量: {len(stocks)}\n"
            message += f"总市值: {sum(p['market_value'] for p in stock_performances.values())/100000000:.2f}亿\n"
            message += f"当日收益: {total_daily_profit:.2f}元\n"
            message += f"当日收益率: {total_daily_return_rate:.2f}%\n"
            message += f"累计收益: {total_cum_profit:.2f}元\n"
            message += f"累计收益率: {total_cum_return_rate:.2f}%\n"
            message += f"每只股票买一手所需总资金: {total_investment:.2f}元\n\n"
            
            # 添加收益最高的前10只股票
            message += "【收益最高的前10只股票】\n"
            sorted_stocks = sorted(stock_performances.items(), 
                                 key=lambda x: x[1]['daily_profit'], 
                                 reverse=True)[:10]
            for i, (stock, perf) in enumerate(sorted_stocks, 1):
                message += f"{i}. {perf['name']}({stock}) "
                message += f"收益: {perf['daily_profit']:.2f}元 "
                message += f"收益率: {perf['daily_return']:.2f}%\n"
            message += "\n"
            
            # 添加收益最差的10只股票
            message += "【收益最差的10只股票】\n"
            worst_stocks = sorted(stock_performances.items(), 
                                key=lambda x: x[1]['daily_profit'])[:10]
            for i, (stock, perf) in enumerate(worst_stocks, 1):
                message += f"{i}. {perf['name']}({stock}) "
                message += f"收益: {perf['daily_profit']:.2f}元 "
                message += f"收益率: {perf['daily_return']:.2f}%\n"
            message += "\n"
            
            # 添加持仓明细（按序号排序）
            message += "【持仓明细】\n"
            sorted_details = sorted(stock_performances.items(), 
                                  key=lambda x: x[1]['index'])
            for stock, perf in sorted_details:
                start_price = self._get_start_price(stock, report_date)
                message += f"{perf['index']}.{perf['name']}({stock}) "
                message += f"市值: {perf['market_value']/100000000:.2f}亿 "
                message += f"现价: {perf['price']:.2f} "
                message += f"调仓日价: {start_price:.2f} "
                message += f"当日收益: {perf['daily_profit']:.2f}元 "
                message += f"当日收益率: {perf['daily_return']:.2f}% "
                message += f"累计收益率: {perf['total_return']:.2f}%\n"
                
            # 保存报告到文件
            report_file = self._save_report(message, target_date if target_date else report_date)
            if report_file is None:
                logging.error("保存报告失败")
                return
                
            # 发送消息
            wechat_helper = WeChatHelper()
            wechat_helper.send_message(message, environment.group_chat_name_vip)
            logging.info("微盘股绩效播报已发送")
            
            # 生成图片
            img_path = ReportImageGenerator.text_to_image(message)
            logging.info(f"图片已保存到文件: {img_path}")
            
        except Exception as e:
            logging.error(f"播报微盘股绩效时出错: {str(e)}")
            
    def _get_start_price(self, stock: str, start_date: str) -> float:
        """
        获取调仓日收盘价
        """
        try:
            xtdata.download_history_data(stock, period='1d', incrementally=True)
            result = xtdata.get_market_data_ex(field_list=['close'],
                                               stock_list=[stock],
                                               period='1d',
                                               start_time=start_date,
                                               end_time=start_date,
                                               count=1)
            if result and stock in result and 'close' in result[stock]:
                close_data = result[stock]['close']
                if not close_data.empty:
                    return close_data.iloc[0]
            return 0.0
        except Exception as e:
            logging.error(f"获取股票{stock}调仓日收盘价时出错: {str(e)}")
            return 0.0
            
if __name__ == "__main__":
    # 创建播报器实例
    reporter = MiniStockPerformanceReporter()
    
    # 执行播报，使用指定的日期
    reporter.broadcast_performance("20250612", "20250616")