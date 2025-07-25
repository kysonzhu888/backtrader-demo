import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json

# 使用导入工具设置项目路径
from utils.import_utils import setup_project_path
setup_project_path()

from .mysterious_fund_alert_detector import get_mysterious_fund_alert_detector, MysteriousFundAlertDetector
from trading_time_helper import TradingTimeHelper

# 导入真实数据获取相关的模块
from xtquant import xtdata
from date_utils import DateUtils
from mini_stock.utils.trading_time_utils import TradingTimeUtils
from mini_stock.utils.stock_price_utils import StockPriceUtils
from mini_stock.utils.market_data_utils import MarketDataUtils
from mini_stock.redis_cache_manager import RedisCacheManager
from mini_stock.stock_data_model import StockDataFactory
import environment



class MysteriousFundMarketService:
    """神秘资金市场服务"""

    def __init__(self):
        self.fund_code = '510300.SH'  # 沪深300 ETF
        self.alert_detector = get_mysterious_fund_alert_detector()
        self.fund_data = {}  # 基金数据缓存
        self.running = True
        self.data_lock = threading.Lock()  # 数据锁
        
        # 初始化Redis缓存管理器
        self.cache_manager = RedisCacheManager(
            host=getattr(environment, 'REDIS_HOST', 'localhost'),
            port=getattr(environment, 'REDIS_PORT', 6379),
            db=getattr(environment, 'REDIS_DB', 0),
            password=getattr(environment, 'REDIS_PASSWORD', None)
        )
        
        # 交易时间助手
        self.trading_time_helper = TradingTimeHelper('IF')  # 使用股指期货的交易时间
        
        # 分钟级别监控配置
        self.minute_amount_threshold = 100000000  # 1亿成交金额阈值
        self.last_minute_time = None  # 记录上次处理的分钟时间
        
        # 获取前收盘价
        self.preclose_price = self._get_preclose_price()
        
        # 订阅分钟级别行情数据
        self._subscribe_fund_data()
        
        # 启动数据更新线程
        self.update_thread = threading.Thread(target=self._update_data_loop, daemon=True)
        self.update_thread.start()
        
        logging.info("神秘资金市场服务已启动（Redis缓存模式）")

    def _subscribe_fund_data(self):
        """订阅基金行情数据"""
        try:
            # 订阅1分钟级别数据
            MarketDataUtils.subscribe_minute_data([self.fund_code], period='1m')
            logging.info(f"已订阅基金分钟级别行情数据: {self.fund_code}")
        except Exception as e:
            logging.error(f"订阅基金行情数据失败: {e}")

    def _get_preclose_price(self) -> Optional[float]:
        """获取前收盘价"""
        try:
            # 下载历史数据
            xtdata.download_history_data(self.fund_code, period='1d', incrementally=True)
            
            # 获取前收盘价
            preclose = StockPriceUtils.get_preclose(self.fund_code)
            if preclose:
                logging.info(f"获取到前收盘价: {preclose}")
                return preclose
            else:
                logging.warning("无法获取前收盘价，使用默认值")
                return 3.5  # 默认值
        except Exception as e:
            logging.error(f"获取前收盘价失败: {e}")
            return 3.5  # 默认值

    def _update_data_loop(self):
        """数据更新循环"""
        while self.running:
            try:
                if self.trading_time_helper.is_trading_time():
                    # 交易时间内，更新数据
                    self._update_fund_data()
                    time.sleep(60)  # 每分钟更新一次（与分钟级别数据同步）
                else:
                    # 非交易时间，减少更新频率
                    time.sleep(300)  # 5分钟检查一次
            except Exception as e:
                logging.error(f"神秘资金数据更新循环出错: {e}")
                time.sleep(60)

    def _update_fund_data(self):
        """更新基金数据"""
        try:
            # 使用 MarketDataUtils 获取最新分钟级别数据
            kline_data = MarketDataUtils.get_latest_trading_data_with_period([self.fund_code], DateUtils.now(), period='1m')
            
            if not kline_data or self.fund_code not in kline_data:
                logging.warning(f"无法获取基金 {self.fund_code} 的分钟级别行情数据")
                return
            
            fund_kline = kline_data[self.fund_code]
            current_time = datetime.now()
            
            # 解析分钟级别行情数据
            price = 0
            volume = 0
            amount = 0
            minute_time = None
            
            if isinstance(fund_kline, dict):
                # 如果是字典格式，直接使用
                price = fund_kline.get('lastPrice', fund_kline.get('close', 0))
                volume = fund_kline.get('volume', 0)
                amount = fund_kline.get('amount', 0)
                minute_time = fund_kline.get('time', None)
            elif hasattr(fund_kline, 'iloc') and len(fund_kline) > 0:
                # 如果是DataFrame格式，获取最新一行
                try:
                    latest_data = fund_kline.iloc[-1]
                    if isinstance(latest_data, dict):
                        price = latest_data.get('lastPrice', latest_data.get('close', 0))
                        volume = latest_data.get('volume', 0)
                        amount = latest_data.get('amount', 0)
                        minute_time = latest_data.get('time', None)
                    else:
                        # 如果是Series格式
                        price = getattr(latest_data, 'lastPrice', getattr(latest_data, 'close', 0))
                        volume = getattr(latest_data, 'volume', 0)
                        amount = getattr(latest_data, 'amount', 0)
                        minute_time = getattr(latest_data, 'time', None)
                except Exception as e:
                    logging.warning(f"解析DataFrame数据失败: {e}")
                    return
            elif hasattr(fund_kline, 'to_dict'):
                # 如果是可以转换为字典的对象
                try:
                    data_dict = fund_kline.to_dict()
                    price = data_dict.get('lastPrice', data_dict.get('close', 0))
                    volume = data_dict.get('volume', 0)
                    amount = data_dict.get('amount', 0)
                    minute_time = data_dict.get('time', None)
                except Exception as e:
                    logging.warning(f"转换对象数据失败: {e}")
                    return
            else:
                logging.warning(f"不支持的行情数据格式: {type(fund_kline)}")
                return
            
            # 检查是否是新的一分钟数据
            if minute_time and minute_time != self.last_minute_time:
                self.last_minute_time = minute_time
                
                # 检查分钟成交金额是否超过阈值
                if amount and amount > self.minute_amount_threshold:
                    # 生成异常提示数据
                    alert_data = {
                        'type': 'minute_amount_exceed',
                        'message': f"【神秘资金异动】{self.fund_code} 一分钟成交额{amount/100000000:.2f}亿，超过1亿阈值",
                        'fund_code': self.fund_code,
                        'amount': amount,
                        'amount_yi': amount / 100000000,
                        'threshold': self.minute_amount_threshold,
                        'threshold_yi': self.minute_amount_threshold / 100000000,
                        'timestamp': current_time.isoformat(),
                        'minute_time': minute_time,
                        'level': 'high',
                        'created_at': current_time.isoformat()
                    }
                    
                    # 存储到Redis
                    self._store_alert_to_redis(minute_time, alert_data)
                    
                    logging.warning(f"检测到神秘资金异动: {alert_data['message']}")
            
            # 确保前收盘价存在
            if self.preclose_price is None:
                self.preclose_price = self._get_preclose_price()
            
            # 计算涨跌幅
            if self.preclose_price and self.preclose_price > 0:
                change = price - self.preclose_price
                change_pct = (change / self.preclose_price) * 100
            else:
                change = 0
                change_pct = 0
            
            # 构建基金数据
            fund_data = {
                'code': self.fund_code,
                'name': '沪深300ETF',
                'price': round(price, 3) if price else 0,
                'preclose': self.preclose_price or 0,
                'change': round(change, 3),
                'change_pct': round(change_pct, 2),
                'volume': volume or 0,
                'amount': amount or 0,
                'amount_yi': round((amount or 0) / 100000000, 2),  # 转换为亿元
                'timestamp': current_time.isoformat(),
                'time': current_time.strftime('%H:%M:%S'),
                'minute_time': minute_time,
                'minute_amount_threshold': self.minute_amount_threshold / 100000000  # 阈值（亿元）
            }
            
            # 线程安全地更新数据
            with self.data_lock:
                self.fund_data = fund_data
            
            # 缓存数据到Redis
            if self.cache_manager and TradingTimeUtils.is_trading_time():
                try:
                    # 将原始数据转换为StockTickData实例
                    stock_data_dict = StockDataFactory.create_batch_from_xtquant_data(kline_data)
                    
                    # 批量缓存到Redis
                    self.cache_manager.cache_stocks_batch(stock_data_dict)
                    
                except Exception as e:
                    logging.error(f"缓存基金数据到Redis失败: {e}")
            
            logging.debug(f"基金数据更新成功: 价格={fund_data['price']}, 涨跌幅={fund_data['change_pct']}%, 分钟成交额={fund_data['amount_yi']}亿")
            
        except Exception as e:
            logging.error(f"更新基金数据时出错: {e}")

    def _store_alert_to_redis(self, minute_time: str, alert_data: Dict[str, Any]):
        """
        将异常提示存储到Redis
        
        Args:
            minute_time: 分钟时间，格式：YYYYMMDDHHMM
            alert_data: 异常提示数据
        """
        if not self.cache_manager.redis_client:
            logging.warning("Redis连接失败，无法存储异常提示")
            return
        
        try:
            # 格式化分钟时间为 YYYYMMDDHHMM 格式
            if isinstance(minute_time, str):
                if len(minute_time) >= 12:  # YYYYMMDDHHMMSS
                    minute_time_formatted = minute_time[:12]  # 取前12位
                else:
                    minute_time_formatted = minute_time
            else:
                # 如果是时间对象，转换为字符串
                minute_time_formatted = minute_time.strftime('%Y%m%d%H%M')
            
            # 生成Redis键名
            redis_key = f"mysterious_fund:minute_alert:{self.fund_code}:{minute_time_formatted}"
            
            # 存储异常提示数据
            alert_data['minute_time'] = minute_time_formatted
            
            # 设置过期时间（1小时后过期）
            self.cache_manager.redis_client.setex(
                redis_key, 
                3600,  # 1小时过期
                json.dumps(alert_data, ensure_ascii=False)
            )
            
            logging.info(f"异常提示已存储到Redis: {redis_key}")
            
        except Exception as e:
            logging.error(f"存储异常提示到Redis失败: {e}")

    def _convert_to_json_serializable(self, data):
        """将数据转换为JSON可序列化格式"""
        import numpy as np
        
        if isinstance(data, dict):
            return {k: self._convert_to_json_serializable(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_to_json_serializable(item) for item in data]
        elif hasattr(data, 'dtype') and hasattr(data, 'item'):  # numpy 数组或标量
            return data.item()
        elif isinstance(data, (int, float, str, bool, type(None))):
            return data
        else:
            return str(data)

    def get_fund_data(self) -> Dict[str, Any]:
        """获取基金数据"""
        try:
            with self.data_lock:
                fund_data = self.fund_data.copy()
                # 确保数据是JSON可序列化的
                converted_data = self._convert_to_json_serializable(fund_data)
                if isinstance(converted_data, dict):
                    return converted_data
                else:
                    return {"error": "数据格式错误"}
        except Exception as e:
            logging.error(f"获取基金数据时出错: {e}")
            return {}

    def get_fund_list(self) -> List[str]:
        """获取基金列表"""
        return [self.fund_code]

    def get_mysterious_fund_alerts(self, minutes: int = 30) -> List[Dict[str, Any]]:
        """获取神秘资金异常提示"""
        try:
            return self.alert_detector.get_recent_alerts(minutes)
        except Exception as e:
            logging.error(f"获取神秘资金异常提示时出错: {e}")
            return []

    def get_mysterious_fund_alerts_by_type(self, alert_type: str, minutes: int = 30) -> List[Dict[str, Any]]:
        """获取指定类型的神秘资金异常提示"""
        try:
            return self.alert_detector.get_alerts_by_type(alert_type, minutes)
        except Exception as e:
            logging.error(f"获取指定类型神秘资金异常提示时出错: {e}")
            return []

    def get_mysterious_fund_alert_stats(self) -> Dict[str, Any]:
        """获取神秘资金异常提示统计"""
        try:
            return self.alert_detector.get_alert_stats()
        except Exception as e:
            logging.error(f"获取神秘资金异常提示统计时出错: {e}")
            return {
                'today_alerts': 0,
                'total_alerts': 0,
                'by_type': {},
                'daily_alert_count': 0
            }

    def get_service_stats(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        try:
            return {
                'service_name': 'mysterious_fund_market_service',
                'fund_code': self.fund_code,
                'is_trading_time': self.trading_time_helper.is_trading_time(),
                'last_update': datetime.now().isoformat(),
                'alert_detector_running': self.alert_detector.running if self.alert_detector else False,
                'preclose_price': self.preclose_price,
                'monitor_mode': 'Redis缓存模式',
                'minute_amount_threshold': self.minute_amount_threshold / 100000000
            }
        except Exception as e:
            logging.error(f"获取服务统计时出错: {e}")
            return {}

    def stop(self):
        """停止服务"""
        self.running = False
        if self.alert_detector:
            self.alert_detector.stop()


# 全局服务实例
mysterious_fund_service = None


def init_mysterious_fund_service():
    """初始化神秘资金市场服务"""
    global mysterious_fund_service
    if mysterious_fund_service is None:
        mysterious_fund_service = MysteriousFundMarketService()
    return mysterious_fund_service


def get_mysterious_fund_service() -> MysteriousFundMarketService:
    """获取神秘资金市场服务实例"""
    global mysterious_fund_service
    if mysterious_fund_service is None:
        mysterious_fund_service = init_mysterious_fund_service()
    return mysterious_fund_service 