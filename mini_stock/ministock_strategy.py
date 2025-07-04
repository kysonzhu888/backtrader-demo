# coding:utf-8
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from date_utils import DateUtils
from wechat_helper import WeChatHelper
import environment
from xtquant import xtdata
# from xtquant.xttype import StockItem
from xtquant import xtconstant
import os
from stock_data_manager import StockDataManager, StockFilter, ExchangeStats
from typing import Dict, List, Optional, Any

class MiniStockStrategy:
    # 最小上市天数
    MIN_LISTED_DAYS = 90
    
    def __init__(self, rebalance_days: int = 30, stock_count: int = 300, target_date: Optional[datetime] = None):
        """
        初始化小市值策略
        
        Args:
            rebalance_days: 调仓周期（天）
            stock_count: 持有股票数量
            target_date: 目标日期，默认为当前日期
        """
        self.rebalance_days = rebalance_days  # 调仓周期（天）
        self.stock_count = stock_count    # 持有股票数量
        self.last_rebalance = None  # 上次调仓日期
        self.target_date = target_date if target_date else DateUtils.now()  # 目标日期
        
        # 设置报告文件目录
        self.report_dir = "reports"
        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)
            
        # 初始化股票数据
        try:
            # 获取过滤后的股票
            self.stocks = StockDataManager.filter_stocks(
                StockFilter(
                    min_listed_days=self.MIN_LISTED_DAYS,
                    exclude_st=True,
                    exclude_delisted=True,
                    exclude_limit_up=True,
                    exclude_suspended=True  # 排除停牌股票
                ),
                self.target_date  # 使用目标日期
            )
        except Exception as e:
            logging.error(f"初始化股票数据时出错: {str(e)}")
            self.stocks = {}
        
    def _select_stocks(self) -> List[str]:
        """
        选择市值最小的股票
        
        Returns:
            List[str]: 股票代码列表
        """
        try:
            # 获取市值最小的前N只股票
            return StockDataManager.get_top_stocks_by_market_value(self.stocks, self.stock_count)
            
        except Exception as e:
            logging.error(f"选择股票时出错: {str(e)}")
            return []
            
    def _save_report(self, report: str) -> Optional[str]:
        """
        保存报告到文件
        
        Args:
            report: 报告内容
            
        Returns:
            Optional[str]: 报告文件路径，如果保存失败则返回None
        """
        try:
            # 生成报告文件名
            report_file = os.path.join(self.report_dir, f"ministock_report_{self.target_date.strftime('%Y%m%d')}.txt")
            
            # 保存报告
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
                
            logging.info(f"报告已保存到文件: {report_file}")
            return report_file
            
        except Exception as e:
            logging.error(f"保存报告时出错: {str(e)}")
            return None
            
    def _broadcast_report(self) -> None:
        """播报报告"""
        try:
            # 获取今天的报告文件
            report_file = os.path.join(self.report_dir, f"ministock_report_{self.target_date.strftime('%Y%m%d')}.txt")
            
            if os.path.exists(report_file):
                # 读取报告内容
                with open(report_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 生成总结性概括
                summary = "【小市值策略每日总结】\n"
                summary += f"日期: {self.target_date.strftime('%Y-%m-%d')}\n"
                
                # 提取关键信息
                lines = content.split('\n')
                for line in lines:
                    if "持仓数量:" in line:
                        summary += line + "\n"
                    elif "总市值:" in line:
                        summary += line + "\n"
                    elif "每只股票买一手所需总资金:" in line:
                        summary += line + "\n"
                    elif "总收益:" in line:
                        summary += line + "\n"
                    elif "总收益率:" in line:
                        summary += line + "\n"
                        break
                
                # 发送总结到微信群
                wechat_helper = WeChatHelper()
                wechat_helper.send_message(summary, environment.group_chat_name_vip)
                
                logging.info("总结报告已发送到微信群")
            else:
                logging.warning("未找到今天的报告文件")
                
        except Exception as e:
            logging.error(f"播报报告时出错: {str(e)}")
            
    def rebalance(self) -> Optional[str]:
        """
        执行调仓
        
        Returns:
            Optional[str]: 调仓报告，如果调仓失败则返回None
        """
        try:
            # 检查是否需要调仓
            if self.last_rebalance is None or \
               (self.target_date - self.last_rebalance).days >= self.rebalance_days:
                
                logging.info("开始执行调仓...")
                
                # 更新股票数据
                logging.info("正在更新股票数据...")
                self.stocks = StockDataManager.filter_stocks(
                    StockFilter(
                        min_listed_days=self.MIN_LISTED_DAYS,
                        exclude_st=True,
                        exclude_delisted=True,
                        exclude_limit_up=True,
                        exclude_suspended=True
                    ),
                    self.target_date  # 使用目标日期
                )
                
                if not self.stocks:
                    logging.error("获取股票数据失败，没有符合条件的股票")
                    return None
                
                # 选择新股票
                logging.info("正在选择新股票...")
                new_stocks = self._select_stocks()
                
                if not new_stocks:
                    logging.error("选择股票失败，没有选到合适的股票")
                    return None
                
                # 生成调仓报告
                logging.info("正在生成调仓报告...")
                report = self._generate_rebalance_report(new_stocks)
                
                if not report:
                    logging.error("生成调仓报告失败")
                    return None
                
                # 保存报告到文件
                logging.info("正在保存报告到文件...")
                report_file = self._save_report(report)
                
                if not report_file:
                    logging.error("保存报告到文件失败")
                    return None
                
                # 发送调仓报告
                try:
                    logging.info("正在发送调仓报告...")
                    wechat_helper = WeChatHelper()
                    wechat_helper.send_message(report, environment.group_chat_name_vip)
                except Exception as e:
                    logging.error(f"发送调仓报告时出错: {str(e)}")
                    # 继续执行，不中断流程
                
                # 更新调仓日期
                self.last_rebalance = self.target_date
                logging.info("调仓完成")
                
                return report
                
            logging.info("当前不需要调仓")
            return None
                
        except Exception as e:
            logging.error(f"调仓时出错: {str(e)}")
            logging.exception("调仓详细错误信息:")  # 添加详细的错误堆栈信息
            return None
            
    def _calculate_daily_returns(self, stocks: List[str]) -> Optional[Dict[str, Any]]:
        """
        计算每日收益
        
        Args:
            stocks: 股票代码列表
            
        Returns:
            Optional[Dict[str, Any]]: 收益信息字典，如果计算失败则返回None
        """
        try:
            # 获取当前日期
            current_date = DateUtils.now()
            current_date_str = current_date.strftime('%Y%m%d')
            
            # 获取前一个交易日（简单使用前一天）
            prev_date = current_date - timedelta(days=1)
            prev_date_str = prev_date.strftime('%Y%m%d')
            
            # 过滤掉新股（上市不足指定天数的股票）
            valid_stocks = []
            for stock in stocks:
                stock_info = StockDataManager.get_stock_info_from_dict(self.stocks, stock)
                if stock_info and stock_info.days_listed >= self.MIN_LISTED_DAYS:
                    valid_stocks.append(stock)
            
            if not valid_stocks:
                logging.error("没有符合条件的股票（上市超过指定天数）")
                return None
                
            # 获取所有股票的前一日收盘价
            prev_prices = {}

            # 增量下载行情数据
            for stock in valid_stocks:
                xtdata.download_history_data(stock, period='1d', incrementally=True)
            
            # 获取历史数据
            result = xtdata.get_market_data_ex(field_list=['close'], 
                                             stock_list=valid_stocks, 
                                             period='1d',
                                             start_time=prev_date_str,
                                             end_time=prev_date_str,
                                             count=1)
            
            if result is None:
                logging.error("获取历史数据失败")
                return None
                
            # 处理返回的数据
            for stock, data in result.items():
                try:
                    if 'close' in data:
                        close_data = data['close']
                        if not close_data.empty:
                            prev_prices[stock] = close_data.iloc[0]
                except Exception as e:
                    logging.error(f"处理股票{stock}数据时出错: {str(e)}")
                    continue
            
            # 计算每只股票的收益
            total_profit = 0
            total_investment = 0
            stock_returns = []
            
            for stock in valid_stocks:
                stock_info = StockDataManager.get_stock_info_from_dict(self.stocks, stock)
                if stock_info and stock in prev_prices:
                    current_price = stock_info.price
                    prev_price = prev_prices[stock]
                    
                    # 计算一手（100股）的收益
                    profit = (current_price - prev_price) * 100
                    total_profit += profit
                    
                    # 计算投资金额
                    investment = current_price * 100
                    total_investment += investment
                    
                    # 计算收益率
                    return_rate = (current_price - prev_price) / prev_price * 100
                    
                    stock_returns.append({
                        'stock': stock,
                        'name': stock_info.name,
                        'profit': profit,
                        'return_rate': return_rate
                    })
            
            # 计算总收益率
            total_return_rate = (total_profit / total_investment * 100) if total_investment > 0 else 0
            
            return {
                'total_profit': total_profit,
                'total_investment': total_investment,
                'total_return_rate': total_return_rate,
                'stock_returns': stock_returns
            }
            
        except Exception as e:
            logging.error(f"计算每日收益时出错: {str(e)}")
            return None
            
    def _generate_rebalance_report(self, stocks: List[str]) -> str:
        """
        生成调仓报告
        
        Args:
            stocks: 股票代码列表
            
        Returns:
            str: 调仓报告
        """
        try:
            report = f"【小市值策略调仓报告】\n"
            report += f"调仓日期: {self.target_date.strftime('%Y-%m-%d')}\n"
            report += f"持仓数量: {len(stocks)}\n\n"
            
            # 获取交易所统计信息
            stats = StockDataManager.get_exchange_stats(stocks)
            report += StockDataManager.format_exchange_stats(stats) + "\n"
            
            # 计算市值和占比
            market_share = StockDataManager.get_market_share(stocks, self.target_date)
            report += f"小市值策略总市值: {market_share['strategy_value']/100000000:.2f}亿\n"
            report += f"全市场总市值: {market_share['market_value']/1000000000000:.2f}万亿\n"
            report += f"小市值策略市值占比: {market_share['share_percent']:.4f}%\n\n"
            
            # 计算每只股票买一手所需的总资金
            total_investment = sum(StockDataManager.get_stock_info_from_dict(self.stocks, stock).min_investment for stock in stocks)
            report += f"每只股票买一手所需总资金: {total_investment:.2f}元\n\n"
            
            # 计算每日收益
            daily_returns = self._calculate_daily_returns(stocks)
            if daily_returns:
                report += f"【每日收益统计】\n"
                report += f"总收益: {daily_returns['total_profit']:.2f}元\n"
                report += f"总收益率: {daily_returns['total_return_rate']:.2f}%\n\n"
                
                # 添加收益最高的前10只股票
                report += "收益最高的前 10 只股票:\n"
                sorted_returns = sorted(daily_returns['stock_returns'], 
                                     key=lambda x: x['profit'], 
                                     reverse=True)[:10]
                for i, stock_return in enumerate(sorted_returns, 1):
                    report += f"{i}. {stock_return['name']}({stock_return['stock']}) "
                    report += f"收益: {stock_return['profit']:.2f}元 "
                    report += f"收益率: {stock_return['return_rate']:.2f}%\n"
                
                report += "\n"
            
            # 添加股票明细
            report += "持仓明细:\n"
            for i, stock in enumerate(stocks, 1):
                stock_info = StockDataManager.get_stock_info_from_dict(self.stocks, stock)
                if stock_info:
                    report += f"{i}. {stock_info.name}({stock_info.code}) "
                    report += f"市值: {stock_info.market_value_in_yi:.2f}亿 "
                    report += f"现价: {stock_info.price:.2f} "
                    report += f"买一手需: {stock_info.min_investment:.2f}元\n"
                
            return report
            
        except Exception as e:
            logging.error(f"生成调仓报告时出错: {str(e)}")
            return "生成调仓报告失败"


if __name__ == "__main__":
    # 创建策略实例，指定目标日期为6月12日
    target_date = datetime(2025, 6, 12)
    strategy = MiniStockStrategy(stock_count=100, target_date=target_date)
    
    # 执行调仓
    report = strategy.rebalance()
    
    # 检查是否收盘时间（15:00）
    current_time = DateUtils.now().time()
    if current_time.hour == 15 and current_time.minute == 5:
        # 播报报告
        strategy._broadcast_report()
