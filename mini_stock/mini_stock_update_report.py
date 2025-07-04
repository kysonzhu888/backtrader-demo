# coding:utf-8
import os
import logging
from datetime import timedelta
from date_utils import DateUtils
from wechat_helper import WeChatHelper
import environment
from stock_data_manager import StockDataManager, StockFilter
from mini_stock.utils.stock_price_utils import StockPriceUtils
from typing import List, Optional, Set

class MiniStockUpdateReporter:
    def __init__(self):
        self.report_dir = "reports"
        
        # 初始化股票数据
        try:
            # 获取过滤后的股票
            self.stocks = StockDataManager.filter_stocks(StockFilter(
                min_listed_days=90,
                exclude_st=True,
                exclude_delisted=True,
                exclude_limit_up=True,
                exclude_suspended=True  # 排除停牌股票
            ))
        except Exception as e:
            logging.error(f"初始化股票数据时出错: {str(e)}")
            self.stocks = {}
            
    @staticmethod
    def _standardize_stock_code(code: str) -> str:
        """
        标准化股票代码格式
        
        Args:
            code: 原始股票代码
            
        Returns:
            str: 标准化后的股票代码
        """
        # 移除可能的括号和空格
        code = code.strip('()').strip()
        
        # 如果代码不包含市场后缀，添加市场后缀
        if '.' not in code:
            if code.startswith('6'):
                code = f"{code}.SH"
            elif code.startswith(('0', '3')):
                code = f"{code}.SZ"
                
        return code
        
    def _read_old_stocks(self, date_str: str) -> Optional[Set[str]]:
        """
        读取指定日期的微盘股列表
        
        Args:
            date_str: 日期字符串，格式为YYYYMMDD
            
        Returns:
            Optional[Set[str]]: 股票代码集合
        """
        try:
            report_file = os.path.join(self.report_dir, f"ministock_report_{date_str}.txt")
            if not os.path.exists(report_file):
                logging.error(f"未找到报告文件: {report_file}")
                return None
                
            old_stocks = set()
            with open(report_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines:
                    if "持仓明细:" in line:
                        break
                        
                # 读取股票明细
                for line in lines:
                    if line.strip().startswith(tuple('0123456789')):
                        parts = line.strip().split()
                        if len(parts) >= 3:
                            # 找到包含股票代码的部分（通常包含.SH或.SZ的部分）
                            code_part = next((part for part in parts if '.SH' in part or '.SZ' in part), None)
                            if code_part:
                                # 提取股票代码（去掉括号和序号）
                                stock_code = code_part.split('(')[-1].split(')')[0]
                                old_stocks.add(stock_code)
                            
            return old_stocks
            
        except Exception as e:
            logging.error(f"读取旧股票列表时出错: {str(e)}")
            return None
            
    def _select_stocks(self) -> List[str]:
        """
        选择市值最小的股票
        
        Returns:
            List[str]: 股票代码列表
        """
        try:
            # 获取市值最小的前100只股票
            return StockDataManager.get_top_stocks_by_market_value(self.stocks, 100)
            
        except Exception as e:
            logging.error(f"选择股票时出错: {str(e)}")
            return []
            
    def broadcast_update(self, date_str: Optional[str] = None) -> None:
        """
        播报微盘股更新情况
        
        Args:
            date_str: 日期字符串，格式为YYYYMMDD，如果为None则使用当前日期
        """
        try:
            # 如果没有指定日期，使用当前日期
            if date_str is None:
                date_str = DateUtils.now().strftime('%Y%m%d')
                
            # 读取旧股票列表
            old_stocks = self._read_old_stocks(date_str)
            if old_stocks is None:
                return
                
            # 获取新股票列表
            new_stocks = self._select_stocks()
            
            # 转换为集合格式
            new_stocks_set = set(new_stocks)
                    
            # 找出新增和剔除的股票
            added_stocks = new_stocks_set - old_stocks
            removed_stocks = old_stocks - new_stocks_set
            
            # 生成播报消息
            message = f"【微盘股成分股更新播报】\n"
            message += f"日期: {DateUtils.now().strftime('%Y-%m-%d')}\n\n"
            
            # 添加新增股票信息
            if added_stocks:
                message += "新增成分股:\n"
                for stock in added_stocks:
                    stock_info = StockDataManager.get_stock_info_from_dict(self.stocks, stock)
                    if stock_info:
                        message += f"{stock_info.name}({stock})\n"
                message += "\n"
                
            # 添加剔除股票信息
            if removed_stocks:
                message += "剔除成分股:\n"
                # 批量获取涨跌幅
                price_changes = StockPriceUtils.get_stock_price_changes(list(removed_stocks))
                for stock in removed_stocks:
                    pct_chg = price_changes.get(stock)
                    if pct_chg is not None:
                        message += f"{stock} 涨跌幅: {pct_chg:.2f}%\n"
                    else:
                        message += f"{stock} 涨跌幅: 未知\n"
                        
            # 发送消息
            if added_stocks or removed_stocks:
                wechat_helper = WeChatHelper()
                wechat_helper.send_message(message, environment.group_chat_name_vip)
                logging.info("微盘股更新播报已发送")
            else:
                logging.info("没有成分股变动，无需播报")
                
        except Exception as e:
            logging.error(f"播报微盘股更新时出错: {str(e)}")
            
if __name__ == "__main__":
    # 创建播报器实例
    reporter = MiniStockUpdateReporter()
    
    # 获取昨天的日期
    yesterday = DateUtils.now() - timedelta(days=1)
    yesterday_str = yesterday.strftime('%Y%m%d')
    
    # 执行播报，使用昨天的日期
    reporter.broadcast_update(yesterday_str)
