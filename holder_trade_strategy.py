# coding:utf-8
import logging
import environment
from datetime import datetime, timedelta
import threading
import time
import os
from tushare_helper import TushareHelper
from wechat_helper import WeChatHelper
from date_utils import DateUtils
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
            wechat_helper = WeChatHelper()
            wechat_helper.send_message("今日A股减持一览：", environment.group_chat_name_vip)
            time.sleep(2)
            wechat_helper.send_file(file_path)

            
            logging.info("减持信息播报完成")
            
        except Exception as e:
            logging.error(f"播报减持信息时出错: {str(e)}")
            
        # 播报完成后，调度下一次播报
        self.schedule_next_broadcast()
            
    def schedule_next_broadcast(self):
        """
        计算下一次播报的时间并启动 Timer
        """
        now = DateUtils.now()
        # 计算距离下一个21:00的秒数
        next_time = now.replace(hour=23, minute=30, second=0)
        if now >= next_time:
            next_time = next_time + timedelta(days=1)
            
        delay_seconds = (next_time - now).total_seconds()
        
        # 如果是 debug 模式，则立刻执行
        if os.getenv('DEBUG_MODE') == '1':
            delay_seconds = 3
            
        logging.info(f"下一次减持播报将在 {delay_seconds:.2f} 秒后执行 ({next_time})...")
        
        # 使用 Timer 调度任务
        threading.Timer(delay_seconds, self.broadcast_holder_trade).start()
            
    def run(self):
        """运行策略"""
        try:
            logging.info("减持播报策略已启动，将在每天晚上9点播报")
            # 启动第一次调度
            self.schedule_next_broadcast()
            
        except Exception as e:
            logging.error(f"运行减持播报策略时出错: {str(e)}")
            
if __name__ == "__main__":
    # 创建策略实例，使用默认日期（今天）
    # date = datetime(2025, 6, 14)
    strategy = HolderTradeStrategy()
    
    # 运行策略
    strategy.run() 