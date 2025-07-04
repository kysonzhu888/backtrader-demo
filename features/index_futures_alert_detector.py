"""
股指期货异常检测器
用于监控股指期货的异常情况，如价格异动、成交量异常等
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import json

from mini_stock.utils.time_utils import TimeUtils
from mini_stock.redis_cache_manager import get_cache_manager
from mini_stock.utils.trading_time_utils import TradingTimeUtils
from mini_stock.futures_instrument_model import FuturesInstrumentModel


class IndexFuturesAlertType(Enum):
    """股指期货提示类型枚举"""
    PRICE_SURGE = "价格异动"  # 价格异动
    VOLUME_SURGE = "成交量异动"  # 成交量异动
    BREAKOUT = "突破"  # 突破重要价位
    REVERSAL = "反转"  # 价格反转
    HIGH_VOLATILITY = "高波动"  # 高波动
    LIQUIDITY_CRISIS = "流动性危机"  # 流动性危机


class IndexFuturesAlertLevel(Enum):
    """股指期货提示级别枚举"""
    LOW = "低"
    MEDIUM = "中"
    HIGH = "高"
    CRITICAL = "紧急"


class IndexFuturesAlert:
    """股指期货提示信息"""

    def __init__(self, futures_code: str, alert_type: IndexFuturesAlertType, level: IndexFuturesAlertLevel,
                 message: str, data: Dict[str, Any], timestamp: datetime):
        self.futures_code = futures_code
        self.alert_type = alert_type
        self.level = level
        self.message = message
        self.data = data
        self.timestamp = timestamp

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "futures_code": self.futures_code,
            "alert_type": self.alert_type.value,
            "level": self.level.value,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }


class IndexFuturesAlertDetector:
    """股指期货异常检测器"""

    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.alert_history = []  # 提示历史记录
        self.max_history = 1000  # 最大历史记录数
        self.detected_alerts = set()  # 已检测的异常，避免重复提示

        # 配置参数 - 股指期货的阈值通常比股票更严格
        self.volume_surge_threshold = 2.0  # 成交量异动阈值（2倍）
        self.price_surge_threshold = 0.02  # 价格异动阈值（2%）
        self.breakout_threshold = 0.01  # 突破阈值（1%）
        self.volatility_threshold = 0.03  # 高波动阈值（3%）
        self.liquidity_threshold = 1000  # 流动性阈值（成交量）

        # 启动检测线程
        self.running = True
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()

        logging.info("股指期货异常检测器已启动")

    def _detection_loop(self):
        """检测循环"""
        while self.running:
            try:
                # 只在交易时间内进行检测
                if TradingTimeUtils.is_trading_time():
                    self._detect_all_futures_alerts()
                    time.sleep(5)  # 交易时间内每5秒检测一次
                else:
                    # 非交易时间，减少检测频率
                    time.sleep(60)  # 非交易时间每60秒检查一次
            except Exception as e:
                logging.error(f"股指期货异常检测循环出错: {e}")
                time.sleep(10)

    def _detect_all_futures_alerts(self):
        """检测所有股指期货的异常情况"""
        try:
            # 再次确认是否在交易时间
            if not TradingTimeUtils.is_trading_time():
                return

            # 检查缓存管理器是否可用
            if not self.cache_manager:
                logging.warning("缓存管理器不可用，跳过股指期货异常检测")
                return

            # 获取股指期货的最新数据
            # 这里需要根据实际的缓存键模式来获取股指期货数据
            futures_data = self._get_futures_data()
            
            if not futures_data:
                return

            for futures_code, data in futures_data.items():
                self._detect_futures_alerts(futures_code, data)

        except Exception as e:
            logging.error(f"检测所有股指期货异常时出错: {e}")

    def _get_futures_data(self) -> Dict[str, Any]:
        """获取股指期货数据"""
        try:
            # 这里需要根据实际的缓存键模式来获取股指期货数据
            # 假设股指期货数据存储在特定的键模式中
            futures_keys = self.cache_manager.redis_client.keys("futures_latest:*")
            futures_data = {}
            
            for key in futures_keys:
                futures_code = key.decode().split(":")[1]  # 提取期货代码
                data = self.cache_manager.redis_client.get(key)
                if data:
                    futures_data[futures_code] = json.loads(data)
            
            return futures_data
        except Exception as e:
            logging.error(f"获取股指期货数据失败: {e}")
            return {}

    def _detect_futures_alerts(self, futures_code: str, data: Dict[str, Any]):
        """检测单个股指期货的异常情况"""
        try:
            # 获取该股指期货当天的所有历史数据
            today_data = self._get_futures_data_today(futures_code)
            if not today_data or len(today_data) < 2:
                return

            # 按时间排序
            sorted_data = sorted(today_data, key=lambda x: x.get('timestamp', ''))

            # 检测各种异常
            self._detect_price_alerts(futures_code, sorted_data)
            self._detect_volume_alerts(futures_code, sorted_data)
            self._detect_volatility_alerts(futures_code, sorted_data)
            self._detect_liquidity_alerts(futures_code, sorted_data)

        except Exception as e:
            logging.error(f"检测股指期货 {futures_code} 异常时出错: {e}")

    def _get_futures_data_today(self, futures_code: str) -> List[Dict]:
        """获取股指期货当天的历史数据"""
        try:
            # 这里需要根据实际的缓存键模式来获取历史数据
            today_key = f"futures_data_today:{futures_code}"
            data = self.cache_manager.redis_client.get(today_key)
            if data:
                return json.loads(data)
            return []
        except Exception as e:
            logging.error(f"获取股指期货 {futures_code} 当天数据失败: {e}")
            return []

    def _detect_price_alerts(self, futures_code: str, sorted_data: List[Dict]):
        """检测价格相关异常"""
        try:
            if len(sorted_data) < 2:
                return

            latest_record = sorted_data[-1]
            prev_record = sorted_data[-2]

            # 提取价格数据
            current_price = latest_record.get('close', latest_record.get('lastPrice', 0))
            prev_price = prev_record.get('close', prev_record.get('lastPrice', 0))

            if current_price <= 0 or prev_price <= 0:
                return

            # 检测价格异动
            price_change = abs(current_price - prev_price) / prev_price
            if price_change >= self.price_surge_threshold:
                alert_id = f"{futures_code}_price_surge_{latest_record.get('timestamp', '')}"
                if alert_id not in self.detected_alerts:
                    self.detected_alerts.add(alert_id)
                    alert = IndexFuturesAlert(
                        futures_code=futures_code,
                        alert_type=IndexFuturesAlertType.PRICE_SURGE,
                        level=IndexFuturesAlertLevel.MEDIUM,
                        message=f"{futures_code} 价格异动！价格变化 {price_change:.2%}",
                        data={
                            'price_change': price_change,
                            'current_price': current_price,
                            'prev_price': prev_price
                        },
                        timestamp=datetime.now()
                    )
                    self._add_alert(alert)

            # 检测突破
            high_prices = [r.get('close', r.get('lastPrice', 0)) for r in sorted_data[:-1]]
            high_price = max(high_prices, default=0)
            if high_price > 0 and current_price > high_price * (1 + self.breakout_threshold):
                alert_id = f"{futures_code}_breakout_{latest_record.get('timestamp', '')}"
                if alert_id not in self.detected_alerts:
                    self.detected_alerts.add(alert_id)
                    alert = IndexFuturesAlert(
                        futures_code=futures_code,
                        alert_type=IndexFuturesAlertType.BREAKOUT,
                        level=IndexFuturesAlertLevel.MEDIUM,
                        message=f"{futures_code} 突破新高！当前价格 {current_price}",
                        data={
                            'current_price': current_price,
                            'high_price': high_price,
                            'breakout_pct': (current_price - high_price) / high_price
                        },
                        timestamp=datetime.now()
                    )
                    self._add_alert(alert)

        except Exception as e:
            logging.error(f"检测价格异常时出错 {futures_code}: {e}")

    def _detect_volume_alerts(self, futures_code: str, sorted_data: List[Dict]):
        """检测成交量相关异常"""
        try:
            if len(sorted_data) < 2:
                return

            latest_record = sorted_data[-1]
            prev_record = sorted_data[-2]

            # 提取成交量数据
            current_volume = latest_record.get('volume', 0)
            prev_volume = prev_record.get('volume', 0)

            if prev_volume > 0 and current_volume > 0:
                volume_ratio = current_volume / prev_volume
                if volume_ratio >= self.volume_surge_threshold:
                    alert_id = f"{futures_code}_volume_surge_{latest_record.get('timestamp', '')}"
                    if alert_id not in self.detected_alerts:
                        self.detected_alerts.add(alert_id)
                        alert = IndexFuturesAlert(
                            futures_code=futures_code,
                            alert_type=IndexFuturesAlertType.VOLUME_SURGE,
                            level=IndexFuturesAlertLevel.MEDIUM,
                            message=f"{futures_code} 成交量异动！成交量放大 {volume_ratio:.1f}倍",
                            data={
                                'volume_ratio': volume_ratio,
                                'current_volume': current_volume,
                                'prev_volume': prev_volume
                            },
                            timestamp=datetime.now()
                        )
                        self._add_alert(alert)

        except Exception as e:
            logging.error(f"检测成交量异常时出错 {futures_code}: {e}")

    def _detect_volatility_alerts(self, futures_code: str, sorted_data: List[Dict]):
        """检测波动性异常"""
        try:
            if len(sorted_data) < 10:  # 需要足够的数据来计算波动性
                return

            # 计算最近10个价格点的波动性
            recent_prices = [r.get('close', r.get('lastPrice', 0)) for r in sorted_data[-10:]]
            recent_prices = [p for p in recent_prices if p > 0]

            if len(recent_prices) < 5:
                return

            # 计算价格变化的标准差
            price_changes = []
            for i in range(1, len(recent_prices)):
                if recent_prices[i-1] > 0:
                    change = abs(recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1]
                    price_changes.append(change)

            if price_changes:
                avg_volatility = sum(price_changes) / len(price_changes)
                if avg_volatility >= self.volatility_threshold:
                    alert_id = f"{futures_code}_high_volatility_{datetime.now().strftime('%Y%m%d%H%M')}"
                    if alert_id not in self.detected_alerts:
                        self.detected_alerts.add(alert_id)
                        alert = IndexFuturesAlert(
                            futures_code=futures_code,
                            alert_type=IndexFuturesAlertType.HIGH_VOLATILITY,
                            level=IndexFuturesAlertLevel.HIGH,
                            message=f"{futures_code} 高波动！平均波动率 {avg_volatility:.2%}",
                            data={
                                'avg_volatility': avg_volatility,
                                'price_changes': price_changes
                            },
                            timestamp=datetime.now()
                        )
                        self._add_alert(alert)

        except Exception as e:
            logging.error(f"检测波动性异常时出错 {futures_code}: {e}")

    def _detect_liquidity_alerts(self, futures_code: str, sorted_data: List[Dict]):
        """检测流动性异常"""
        try:
            if len(sorted_data) < 5:
                return

            # 检查最近5个时间点的成交量
            recent_volumes = [r.get('volume', 0) for r in sorted_data[-5:]]
            avg_volume = sum(recent_volumes) / len(recent_volumes)

            if avg_volume < self.liquidity_threshold:
                alert_id = f"{futures_code}_liquidity_crisis_{datetime.now().strftime('%Y%m%d%H%M')}"
                if alert_id not in self.detected_alerts:
                    self.detected_alerts.add(alert_id)
                    alert = IndexFuturesAlert(
                        futures_code=futures_code,
                        alert_type=IndexFuturesAlertType.LIQUIDITY_CRISIS,
                        level=IndexFuturesAlertLevel.CRITICAL,
                        message=f"{futures_code} 流动性危机！平均成交量 {avg_volume:.0f}",
                        data={
                            'avg_volume': avg_volume,
                            'recent_volumes': recent_volumes
                        },
                        timestamp=datetime.now()
                    )
                    self._add_alert(alert)

        except Exception as e:
            logging.error(f"检测流动性异常时出错 {futures_code}: {e}")

    def _add_alert(self, alert: IndexFuturesAlert):
        """添加异常提示"""
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history.pop(0)

        # 缓存到Redis
        try:
            if self.cache_manager:
                alert_data = [alert.to_dict()]
                self.cache_manager.cache_filter_result(
                    {'type': 'index_futures_alerts', 'timestamp': datetime.now().isoformat()},
                    alert_data,
                    300  # 5分钟过期
                )
        except Exception as e:
            logging.error(f"缓存股指期货异常提示失败: {e}")

    def get_recent_alerts(self, minutes: int = 30) -> List[IndexFuturesAlert]:
        """获取最近的异常提示"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [alert for alert in self.alert_history if alert.timestamp >= cutoff_time]

    def get_alerts_by_type(self, alert_type: IndexFuturesAlertType, minutes: int = 30) -> List[IndexFuturesAlert]:
        """获取指定类型的最近提示"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [alert for alert in self.alert_history
                if alert.alert_type == alert_type and alert.timestamp >= cutoff_time]

    def get_alerts_by_futures(self, futures_code: str, minutes: int = 30) -> List[IndexFuturesAlert]:
        """获取指定股指期货的最近提示"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [alert for alert in self.alert_history
                if alert.futures_code == futures_code and alert.timestamp >= cutoff_time]

    def clear_old_alerts(self, hours: int = 24):
        """清理旧提示"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        self.alert_history = [alert for alert in self.alert_history if alert.timestamp >= cutoff_time]

        # 清理已检测的异常标识
        self.detected_alerts.clear()

    def get_alert_stats(self) -> Dict[str, Any]:
        """获取提示统计信息"""
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        today_alerts = [alert for alert in self.alert_history if alert.timestamp >= today_start]

        stats = {
            'total_alerts': len(self.alert_history),
            'today_alerts': len(today_alerts),
            'by_type': {},
            'by_level': {}
        }

        # 按类型统计
        for alert_type in IndexFuturesAlertType:
            count = len([a for a in today_alerts if a.alert_type == alert_type])
            if count > 0:
                stats['by_type'][alert_type.value] = count

        # 按级别统计
        for level in IndexFuturesAlertLevel:
            count = len([a for a in today_alerts if a.level == level])
            if count > 0:
                stats['by_level'][level.value] = count

        return stats

    def stop(self):
        """停止检测器"""
        self.running = False
        if hasattr(self, 'detection_thread'):
            self.detection_thread.join(timeout=5)


# 全局检测器实例
index_futures_alert_detector = None


def get_index_futures_alert_detector() -> IndexFuturesAlertDetector:
    """获取全局股指期货异常检测器实例"""
    global index_futures_alert_detector
    if index_futures_alert_detector is None:
        index_futures_alert_detector = IndexFuturesAlertDetector()
    return index_futures_alert_detector 