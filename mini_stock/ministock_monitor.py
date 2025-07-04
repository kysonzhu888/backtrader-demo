import os
import time
import logging
import requests
from datetime import datetime
from date_utils import DateUtils
import environment
from wechat_helper import WeChatHelper
import threading

class MiniStockMonitor:
    def __init__(self, market_data_url="http://localhost:5000", report_dir="reports", date: datetime = None):
        self.market_data_url = market_data_url
        self.report_dir = report_dir
        self.date = date if date else DateUtils.now()
        self.group_name = environment.group_chat_name_vip
        self.notified_9_5 = {}  # 记录每只股票是否已播报过涨幅超9.5%
        self.last_is_limit_up = {}  # 记录每只股票上一tick是否涨停
        self.broadcast_cache = {}  # 消息广播缓存
        
        # 初始化数据
        self.code_list = self._fetch_stock_list()
        self.preclose_dict = self._fetch_preclose()
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    def _fetch_stock_list(self):
        """从服务获取股票列表"""
        try:
            response = requests.get(f"{self.market_data_url}/stock_list")
            if response.status_code == 200:
                return response.json()
            logging.error(f"[mini stork monitor]获取股票列表失败: {response.status_code}")
            return []
        except Exception as e:
            logging.error(f"[mini stork monitor]获取股票列表失败: {e}")
            return []

    def _fetch_preclose(self):
        """从服务获取前收盘价"""
        try:
            response = requests.get(f"{self.market_data_url}/preclose")
            if response.status_code == 200:
                return response.json()
            logging.error(f"获取前收盘价失败: {response.status_code}")
            return {}
        except Exception as e:
            logging.error(f"获取前收盘价失败: {e}")
            return {}

    def _fetch_market_data(self):
        """从服务获取市场数据"""
        try:
            response = requests.get(f"{self.market_data_url}/market_data")
            if response.status_code == 200:
                return response.json()
            logging.error(f"获取市场数据失败: {response.status_code}")
            return {}
        except Exception as e:
            logging.error(f"获取市场数据失败: {e}")
            return {}

    def get_limit_up_ratio(self, code):
        """获取涨停比例"""
        if code.startswith("688") or code.startswith("300") or code.startswith("301"):
            return 1.2
        return 1.1

    def broadcast_message(self, message, code):
        """广播消息，确保消息只发送一次"""
        message_key = f"{code}_{message}"
        if message_key in self.broadcast_cache:
            return
            
        self.broadcast_cache[message_key] = datetime.now()
        try:
            wechat = WeChatHelper()
            wechat.send_message(message, self.group_name)
            logging.info(f"已发送微信播报: {message}")
        except Exception as e:
            logging.error(f"微信播报失败: {e}")

    def monitor(self):
        while True:
            logging.info("开始监控...")
            kline_data = self._fetch_market_data()
            now = DateUtils.now().strftime("%Y-%m-%d %H:%M:%S")
            
            for code in self.code_list:
                kline = kline_data.get(code)
                if kline is None or kline.empty:
                    logging.info(f"{now} {code} 无行情数据")
                    continue
                    
                k = kline.iloc[-1] if hasattr(kline, 'iloc') else kline[-1]
                lastPrice = k.get("lastPrice", None)
                preclose = self.preclose_dict.get(code)
                limit_up_ratio = self.get_limit_up_ratio(code)
                limit_up_price = round(preclose * limit_up_ratio, 2) if preclose is not None else None
                
                if lastPrice is not None and preclose is not None:
                    pct_chg = (lastPrice - preclose) / preclose * 100
                    is_limit_up = abs(lastPrice - limit_up_price) < 1e-4
                    
                    # 1. 检查是否开板
                    if self.last_is_limit_up.get(code, False) and lastPrice < limit_up_price:
                        msg = f"【小市值异动播报】{now} {code} 涨停后开板！最新价: {lastPrice:.2f} 涨停价: {limit_up_price:.2f}"
                        self.broadcast_message(msg, code)
                        self.last_is_limit_up[code] = False

                    # 2. 正常涨停/涨幅逻辑
                    if is_limit_up:
                        if not self.last_is_limit_up.get(code, False):
                            msg = f"【小市值异动播报】{now} {code} 涨停！最新价: {lastPrice:.2f} 前收: {preclose:.2f} 涨停价: {limit_up_price:.2f}"
                            self.broadcast_message(msg, code)
                            self.notified_9_5[code] = False
                        self.last_is_limit_up[code] = True
                    elif pct_chg > 9.5:
                        if not self.notified_9_5.get(code, False):
                            msg = f"【小市值异动播报】{now} {code} 涨幅超9.5%：{pct_chg:.2f}% 最新价: {lastPrice:.2f} 前收: {preclose:.2f}，请关注！"
                            self.broadcast_message(msg, code)
                            self.notified_9_5[code] = True
                        self.last_status[code] = False
                        self.last_is_limit_up[code] = False
                    else:
                        self.last_status[code] = False
                        self.notified_9_5[code] = False
                        self.last_is_limit_up[code] = False

            # 清理过期的广播缓存（保留最近1小时的消息）
            current_time = datetime.now()
            self.broadcast_cache = {
                k: v for k, v in self.broadcast_cache.items()
                if (current_time - v).total_seconds() < 3600
            }
            
            time.sleep(6)

    def run(self):
        # 发送启动消息
        wechat_helper = WeChatHelper()
        wechat_helper.send_message("小市值股票监控启动...", environment.group_chat_name_monitor)
        
        # 开始监控
        self.monitor()

if __name__ == "__main__":
    # 示例：传入指定日期
    # monitor = MiniStockMonitor(date=datetime(2025, 6, 12))
    monitor = MiniStockMonitor()
    monitor.run()