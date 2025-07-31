# coding:utf-8
import logging
from threading import Timer
from time import sleep

import environment
from datetime import datetime
import time
import os
from utils.tushare_helper import TushareHelper
from utils.wechat_helper import send_message, send_file
from utils.date_utils import DateUtils
from typing import Optional

class HolderTradeStrategy:
    def __init__(self, target_date: Optional[datetime] = None):
        """
        初始化减持播报策略
        
        Args:
            target_date: 目标日期，默认为今天
        """
        self.target_date = target_date if target_date else DateUtils.today()

        # 设置报告文件目录
        self.report_dir = "reports"
        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)
        
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
            report_file = os.path.join(self.report_dir, f"holder_trade_report_{self.target_date.strftime('%Y%m%d')}.txt")
            
            # 保存报告
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
                
            logging.info(f"报告已保存到文件: {report_file}")
            return report_file
            
        except Exception as e:
            logging.error(f"保存报告时出错: {str(e)}")
            return None
        
    def broadcast_holder_trade(self):
        """播报减持信息"""
        try:
            logging.info("开始获取减持数据...")
            
            # 获取减持数据
            trade_date = self.target_date.strftime('%Y%m%d')
            records = TushareHelper.get_holder_trade(trade_date)
            
            # 生成报告
            report_date = self.target_date.strftime('%Y-%m-%d')
            report = TushareHelper.format_holder_trade_report(records, report_date)
            
            # 保存报告到文件
            file_path = self._save_report(report)
            
            # 发送到微信群
            send_message("今日A股减持一览：", environment.group_chat_name_vip)
            time.sleep(2)
            send_file(file_path, environment.group_chat_name_vip)

            
            logging.info("减持信息播报完成")
            
        except Exception as e:
            logging.error(f"播报减持信息时出错: {str(e)}")
            
# 统一调度器调用的函数
def run_strategy():

    # 获取当前时间
    now = DateUtils.now()
    current_hour = now.hour
    task_hour = 23
    if current_hour in [task_hour]:
        logging.info("持仓交易策略任务开始执行...")
        sleep(15)
        strategy = HolderTradeStrategy()
        strategy.broadcast_holder_trade()
        logging.info("持仓交易策略任务执行完毕。")
    else:
        logging.info(f"持仓交易策略任务在 {task_hour} 点 开始执行...")

    Timer(60 * 60, run_strategy).start()


            
if __name__ == "__main__":
    # 直接运行任务（用于测试）
    run_strategy() 