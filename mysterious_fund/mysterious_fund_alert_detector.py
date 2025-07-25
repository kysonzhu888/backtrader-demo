#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
神秘资金异常检测器
负责从Redis读取异常提示数据，并提供查询接口
"""

import logging
import threading
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# 使用导入工具设置项目路径
from utils.import_utils import setup_project_path
setup_project_path()

from mini_stock.redis_cache_manager import RedisCacheManager
import environment


class MysteriousFundAlertDetector:
    """神秘资金异常检测器"""

    def __init__(self):
        self.running = True
        
        # 初始化Redis缓存管理器
        self.redis_client = RedisCacheManager(
            host=getattr(environment, 'REDIS_HOST', 'localhost'),
            port=getattr(environment, 'REDIS_PORT', 6379),
            db=getattr(environment, 'REDIS_DB', 0),
            password=getattr(environment, 'REDIS_PASSWORD', None)
        )
        
        # 启动数据读取线程
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()
        
        logging.info("神秘资金异常检测器已启动（Redis读取模式）")

    def _reader_loop(self):
        """数据读取循环"""
        while self.running:
            try:
                if self._is_trading_time():
                    # 交易时间内，每5-6秒读取一次
                    self._check_redis_alerts()
                    time.sleep(5)  # 5秒检查一次
                else:
                    # 非交易时间，减少检查频率
                    time.sleep(60)  # 1分钟检查一次
            except Exception as e:
                logging.error(f"神秘资金异常检测器读取循环出错: {e}")
                time.sleep(10)

    def _is_trading_time(self) -> bool:
        """判断是否为交易时间"""
        try:
            from mini_stock.utils.trading_time_utils import TradingTimeUtils
            return TradingTimeUtils.is_trading_time()
        except Exception as e:
            logging.error(f"判断交易时间失败: {e}")
            return False

    def _check_redis_alerts(self):
        """检查Redis中的异常提示"""
        try:
            # 获取最近的异常提示（最近1分钟内的）
            recent_alerts = self._get_recent_alerts_from_redis(minutes=1)
            
            for alert in recent_alerts:
                # 检查是否是新异常（通过时间戳判断）
                if self._is_new_alert(alert):
                    # 处理新异常
                    self._process_new_alert(alert)
                    
        except Exception as e:
            logging.error(f"检查Redis异常提示失败: {e}")

    def _get_recent_alerts_from_redis(self, minutes: int = 30) -> List[Dict[str, Any]]:
        """
        从Redis获取最近的异常提示
        
        Args:
            minutes: 获取最近几分钟的异常提示
            
        Returns:
            List[Dict[str, Any]]: 异常提示列表
        """
        if not self.redis_client.redis_client:
            return []
        
        try:
            alerts = []
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(minutes=minutes)
            
            # 获取所有神秘资金异常提示的Redis键
            pattern = "mysterious_fund:minute_alert:*"
            keys = self.redis_client.redis_client.keys(pattern)  # type: ignore
            
            for key in keys:  # type: ignore
                try:
                    data_str = self.redis_client.redis_client.get(key)
                    if data_str and isinstance(data_str, str):
                        alert_data = json.loads(data_str)
                        alert_time = datetime.fromisoformat(alert_data['created_at'])
                        
                        if alert_time >= cutoff_time:
                            alerts.append(alert_data)
                except Exception as e:
                    logging.warning(f"解析异常提示数据失败: {e}")
                    continue
            
            # 按时间倒序排列
            alerts.sort(key=lambda x: x['created_at'], reverse=True)
            return alerts
            
        except Exception as e:
            logging.error(f"从Redis获取最近异常提示失败: {e}")
            return []

    def _is_new_alert(self, alert: Dict[str, Any]) -> bool:
        """
        判断是否为新的异常提示
        
        Args:
            alert: 异常提示数据
            
        Returns:
            bool: 是否为新异常
        """
        try:
            # 这里可以实现更复杂的逻辑来判断是否为新异常
            # 目前简单判断：如果创建时间在最近30秒内，认为是新异常
            created_at = datetime.fromisoformat(alert['created_at'])
            current_time = datetime.now()
            time_diff = (current_time - created_at).total_seconds()
            
            return time_diff <= 30  # 30秒内的认为是新异常
            
        except Exception as e:
            logging.error(f"判断新异常失败: {e}")
            return False

    def _process_new_alert(self, alert: Dict[str, Any]):
        """
        处理新的异常提示
        
        Args:
            alert: 异常提示数据
        """
        try:
            # 记录日志
            logging.warning(f"检测到新的神秘资金异常: {alert.get('message', '未知异常')}")
            
            # 这里可以添加更多的处理逻辑，比如：
            # - 发送通知
            # - 记录到数据库
            # - 触发其他业务逻辑
            
            # 示例：打印异常信息
            print(f"🚨 {alert.get('message', '未知异常')}")
            print(f"   时间: {alert.get('timestamp', 'N/A')}")
            print(f"   成交额: {alert.get('amount_yi', 0):.2f}亿")
            print(f"   阈值: {alert.get('threshold_yi', 0):.2f}亿")
            print("-" * 50)
            
        except Exception as e:
            logging.error(f"处理新异常失败: {e}")

    def get_recent_alerts(self, minutes: int = 30) -> List[Dict[str, Any]]:
        """
        获取最近的异常提示
        
        Args:
            minutes: 获取最近几分钟的异常提示
            
        Returns:
            List[Dict[str, Any]]: 异常提示列表
        """
        return self._get_recent_alerts_from_redis(minutes)

    def get_alerts_by_type(self, alert_type: str, minutes: int = 30) -> List[Dict[str, Any]]:
        """
        获取指定类型的异常提示
        
        Args:
            alert_type: 异常类型
            minutes: 获取最近几分钟的异常提示
            
        Returns:
            List[Dict[str, Any]]: 异常提示列表
        """
        try:
            all_alerts = self._get_recent_alerts_from_redis(minutes)
            filtered_alerts = [alert for alert in all_alerts if alert.get('type') == alert_type]
            return filtered_alerts
        except Exception as e:
            logging.error(f"获取指定类型异常提示失败: {e}")
            return []

    def get_alert_stats(self) -> Dict[str, Any]:
        """
        获取异常提示统计
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        if not self.redis_client.redis_client:
            return {
                'today_alerts': 0,
                'total_alerts': 0,
                'by_type': {},
                'daily_alert_count': 0
            }
        
        try:
            today = datetime.now().strftime('%Y%m%d')
            pattern = f"mysterious_fund:minute_alert:*:{today}*"
            keys = self.redis_client.redis_client.keys(pattern)  # type: ignore
            
            today_alerts = len(keys) if keys else 0  # type: ignore
            
            # 获取所有异常提示
            all_pattern = "mysterious_fund:minute_alert:*"
            all_keys = self.redis_client.redis_client.keys(all_pattern)  # type: ignore
            total_alerts = len(all_keys) if all_keys else 0  # type: ignore
            
            # 统计类型分布
            by_type = {}
            if keys:
                for key in keys:  # type: ignore
                    try:
                        data_str = self.redis_client.redis_client.get(key)
                        if data_str and isinstance(data_str, str):
                            alert_data = json.loads(data_str)
                            alert_type = alert_data.get('type', 'unknown')
                            by_type[alert_type] = by_type.get(alert_type, 0) + 1
                    except Exception as e:
                        logging.warning(f"解析异常提示数据失败: {e}")
                        continue
            
            return {
                'today_alerts': today_alerts,
                'total_alerts': total_alerts,
                'by_type': by_type,
                'daily_alert_count': today_alerts
            }
            
        except Exception as e:
            logging.error(f"获取异常提示统计失败: {e}")
            return {
                'today_alerts': 0,
                'total_alerts': 0,
                'by_type': {},
                'daily_alert_count': 0
            }

    def stop(self):
        """停止异常检测器"""
        self.running = False
        logging.info("神秘资金异常检测器已停止")


# 全局异常检测器实例
mysterious_fund_alert_detector = None


def init_mysterious_fund_alert_detector() -> MysteriousFundAlertDetector:
    """
    初始化神秘资金异常检测器
    
    Returns:
        MysteriousFundAlertDetector: 异常检测器实例
    """
    global mysterious_fund_alert_detector
    if mysterious_fund_alert_detector is None:
        mysterious_fund_alert_detector = MysteriousFundAlertDetector()
    return mysterious_fund_alert_detector


def get_mysterious_fund_alert_detector() -> MysteriousFundAlertDetector:
    """
    获取神秘资金异常检测器实例
    
    Returns:
        MysteriousFundAlertDetector: 异常检测器实例
    """
    global mysterious_fund_alert_detector
    if mysterious_fund_alert_detector is None:
        mysterious_fund_alert_detector = init_mysterious_fund_alert_detector()
    return mysterious_fund_alert_detector 