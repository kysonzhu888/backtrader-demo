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
from mini_stock.stock_data_model import StockTickData, StockDataFactory


class AlertType(Enum):
    """提示类型枚举"""
    OPEN_LIMIT_UP = "开板"  # 涨停后开板
    LIMIT_UP = "涨停"  # 涨停
    LIMIT_DOWN = "跌停"  # 跌停
    HIGH_VOLUME = "异常放量"  # 异常放量
    PRICE_SURGE = "价格异动"  # 价格异动
    VOLUME_SURGE = "成交量异动"  # 成交量异动
    BREAKOUT = "突破"  # 突破重要价位
    REVERSAL = "反转"  # 价格反转


class AlertLevel(Enum):
    """提示级别枚举"""
    LOW = "低"
    MEDIUM = "中"
    HIGH = "高"
    CRITICAL = "紧急"


class StockAlert:
    """股票提示信息"""

    def __init__(self, stock_code: str, alert_type: AlertType, level: AlertLevel,
                 message: str, data: Dict[str, Any], timestamp: datetime):
        self.stock_code = stock_code
        self.alert_type = alert_type
        self.level = level
        self.message = message
        self.data = data
        self.timestamp = timestamp

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "stock_code": self.stock_code,
            "alert_type": self.alert_type.value,
            "level": self.level.value,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }


class AlertDetector:
    """异常检测器 - 基于Redis历史数据"""

    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.alert_history = []  # 提示历史记录
        self.max_history = 1000  # 最大历史记录数
        self.detected_alerts = set()  # 已检测的异常，避免重复提示

        # 配置参数
        self.volume_surge_threshold = 3.0  # 成交量异动阈值（3倍）
        self.price_surge_threshold = 0.05  # 价格异动阈值（5%）
        self.breakout_threshold = 0.02  # 突破阈值（2%）

        # 启动检测线程
        self.running = True
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()

        logging.info("异常检测器已启动")

    def _get_limit_threshold(self, stock_code: str) -> tuple:
        """
        获取股票的涨跌停阈值
        
        Args:
            stock_code: 股票代码
            
        Returns:
            tuple: (涨停阈值, 跌停阈值)
        """
        # 根据股票代码判断市场类型
        if stock_code.startswith(('300', '301')):  # 创业板
            return 0.199, -0.199  # 20%
        elif stock_code.startswith('688'):  # 科创板
            return 0.199, -0.199  # 20%
        elif stock_code.startswith('8'):  # 北交所
            return 0.299, -0.299  # 30%
        else:  # 主板（包括000、001、002、600、601、603等）
            return 0.099, -0.099  # 10%

    def _detection_loop(self):
        """检测循环"""
        while self.running:
            try:
                # 只在交易时间内进行检测
                if TradingTimeUtils.is_trading_time():
                    self._detect_all_alerts()
                    time.sleep(5)  # 交易时间内每5秒检测一次
                else:
                    # 非交易时间，减少检测频率
                    time.sleep(60)  # 非交易时间每60秒检查一次
            except Exception as e:
                logging.error(f"异常检测循环出错: {e}")
                time.sleep(10)

    def _detect_all_alerts(self):
        """检测所有股票的异常情况"""
        try:
            # 再次确认是否在交易时间
            if not TradingTimeUtils.is_trading_time():
                return

            # 检查缓存管理器是否可用
            if not self.cache_manager:
                logging.warning("缓存管理器不可用，跳过异常检测")
                return

            # 获取缓存统计，了解有哪些股票
            stats = self.cache_manager.get_cache_stats()
            today_stocks = stats.get('today_stocks', 0)

            if today_stocks == 0:
                return

            # 获取所有股票的最新数据
            latest_data = self.cache_manager.get_multiple_latest_data([])  # 空列表会返回所有股票

            for stock_code, latest_record in latest_data.items():
                self._detect_stock_alerts(stock_code, latest_record)

        except Exception as e:
            logging.error(f"检测所有异常时出错: {e}")

    def _detect_stock_alerts(self, stock_code: str, latest_record: Dict[str, Any]):
        """检测单只股票的异常情况"""
        try:
            # 检查缓存管理器是否可用
            if not self.cache_manager:
                return

            # 获取该股票当天的所有历史数据
            today_data = self.cache_manager.get_stock_data_today(stock_code)
            if not today_data or len(today_data) < 2:
                return

            # 按时间排序
            sorted_data = sorted(today_data, key=lambda x: x.get('timestamp', ''))

            # 从Redis缓存获取前收盘价
            preclose = self.cache_manager.get_stock_preclose(stock_code)
            
            # 如果无法获取前收盘价，则跳过
            if preclose <= 0:
                logging.info(f"无法获取 {stock_code} 的前收盘价，跳过检测")
                return

            # 获取该股票的涨跌停阈值
            limit_up_threshold, limit_down_threshold = self._get_limit_threshold(stock_code)

            # 检测开板
            self._detect_open_limit_up(stock_code, sorted_data, preclose, limit_up_threshold)

            # 检测其他异常
            self._detect_other_alerts(stock_code, sorted_data, preclose, limit_up_threshold, limit_down_threshold)

        except Exception as e:
            logging.error(f"检测股票 {stock_code} 异常时出错: {e}")

    def _detect_open_limit_up(self, stock_code: str, sorted_data: List[Dict], preclose: float, limit_up_threshold: float):
        """检测开板"""
        try:
            # 检查是否有过涨停
            had_limit_up = False
            limit_up_time = None

            for record in sorted_data:
                # 首先尝试使用原有的数据提取逻辑（经过验证的）
                current_price = 0
                current_time = ""

                # 尝试使用StockTickData格式
                try:
                    stock_data = StockTickData.from_dict(record)
                    current_price = stock_data.lastPrice
                    current_time = stock_data.time
                except Exception as e:
                    # 如果StockTickData转换失败，使用原始字段
                    current_price = record.get('lastPrice', record.get('lastClose', 0))
                    current_time = record.get('time', record.get('timestamp', ''))
                    logging.info(f"使用原始字段提取数据 {stock_code}: {e}")


                if current_price <= 0:
                    continue

                change_pct = (current_price - preclose) / preclose

                # 检查是否涨停
                if change_pct >= limit_up_threshold:
                    if not had_limit_up:
                        had_limit_up = True
                        limit_up_time = record.get('timestamp')
                # 检查是否开板（之前涨停过，现在不是涨停）
                elif had_limit_up and change_pct < limit_up_threshold:
                    # 生成唯一标识，避免重复提示
                    alert_id = f"{stock_code}_open_limit_up_{limit_up_time}"
                    if alert_id not in self.detected_alerts:
                        self.detected_alerts.add(alert_id)

                        # 计算涨停持续时间
                        if limit_up_time:
                            try:
                                limit_up_dt = datetime.fromisoformat(limit_up_time.replace('Z', '+00:00'))
                                current_dt = datetime.fromisoformat(record.get('timestamp', '').replace('Z', '+00:00'))
                                duration = (current_dt - limit_up_dt).total_seconds()
                            except:
                                duration = 0
                        else:
                            duration = 0

                        # 获取涨停幅度描述
                        limit_pct = limit_up_threshold * 100
                        alert = StockAlert(
                            stock_code=stock_code,
                            alert_type=AlertType.OPEN_LIMIT_UP,
                            level=AlertLevel.CRITICAL,
                            message=f"{stock_code} 开板！涨停({limit_pct:.0f}%)持续 {duration:.0f}秒，当前涨幅 {change_pct:.2%}",
                            data={
                                'change_pct': change_pct,
                                'current_price': current_price,
                                'limit_up_duration': duration,
                                'limit_up_time': limit_up_time,
                                'limit_up_threshold': limit_up_threshold
                            },
                            timestamp=datetime.now()
                        )

                        self._add_alert(alert)
                        logging.warning(f"[ALERT] {alert.message}")

                    # 重置涨停状态，允许检测下一次开板
                    had_limit_up = False
                    limit_up_time = None

        except Exception as e:
            logging.error(f"检测开板时出错 {stock_code}: {e}")

    def _detect_other_alerts(self, stock_code: str, sorted_data: List[Dict], preclose: float, 
                           limit_up_threshold: float, limit_down_threshold: float):
        """检测其他异常情况"""
        try:
            if len(sorted_data) < 2:
                return

            latest_record = sorted_data[-1]

            # 尝试使用StockTickData格式
            try:
                stock_data = StockTickData.from_dict(latest_record)
                current_price = stock_data.lastPrice
                current_volume = stock_data.volume
            except Exception as e:
                # 如果StockTickData转换失败，使用原始字段
                current_price = latest_record.get('lastPrice',
                                                  latest_record.get('close', latest_record.get('price', 0)))
                current_volume = latest_record.get('volume', 0)
                logging.debug(f"使用原始字段提取数据 {stock_code}: {e}")


            if current_price <= 0:
                return

            change_pct = (current_price - preclose) / preclose

            # 检测涨停
            if change_pct >= limit_up_threshold:
                alert_id = f"{stock_code}_limit_up"
                if alert_id not in self.detected_alerts:
                    self.detected_alerts.add(alert_id)
                    limit_pct = limit_up_threshold * 100
                    alert = StockAlert(
                        stock_code=stock_code,
                        alert_type=AlertType.LIMIT_UP,
                        level=AlertLevel.HIGH,
                        message=f"{stock_code} 涨停({limit_pct:.0f}%)！涨幅 {change_pct:.2%}",
                        data={
                            'change_pct': change_pct,
                            'current_price': current_price,
                            'preclose': preclose,
                            'limit_up_threshold': limit_up_threshold
                        },
                        timestamp=datetime.now()
                    )
                    self._add_alert(alert)

            # 检测跌停
            if change_pct <= limit_down_threshold:
                alert_id = f"{stock_code}_limit_down"
                if alert_id not in self.detected_alerts:
                    self.detected_alerts.add(alert_id)
                    limit_pct = abs(limit_down_threshold) * 100
                    alert = StockAlert(
                        stock_code=stock_code,
                        alert_type=AlertType.LIMIT_DOWN,
                        level=AlertLevel.HIGH,
                        message=f"{stock_code} 跌停({limit_pct:.0f}%)！跌幅 {change_pct:.2%}",
                        data={
                            'change_pct': change_pct,
                            'current_price': current_price,
                            'preclose': preclose,
                            'limit_down_threshold': limit_down_threshold
                        },
                        timestamp=datetime.now()
                    )
                    self._add_alert(alert)

            # 检测异常放量（需要至少两条记录）
            if len(sorted_data) >= 2:
                prev_record = sorted_data[-2]
                
                # 提取前一条记录的成交量
                try:
                    prev_stock_data = StockTickData.from_dict(prev_record)
                    prev_volume = prev_stock_data.volume
                except Exception as e:
                    prev_volume = prev_record.get('volume', 0)
                    logging.debug(f"使用原始字段提取前一条记录数据 {stock_code}: {e}")


                if prev_volume > 0 and current_volume > 0:
                    volume_ratio = current_volume / prev_volume
                    if volume_ratio >= self.volume_surge_threshold:
                        alert_id = f"{stock_code}_volume_surge_{latest_record.get('timestamp', '')}"
                        if alert_id not in self.detected_alerts:
                            self.detected_alerts.add(alert_id)
                            alert = StockAlert(
                                stock_code=stock_code,
                                alert_type=AlertType.HIGH_VOLUME,
                                level=AlertLevel.MEDIUM,
                                message=f"{stock_code} 异常放量！成交量放大 {volume_ratio:.1f}倍",
                                data={
                                    'volume_ratio': volume_ratio,
                                    'current_volume': current_volume,
                                    'prev_volume': prev_volume
                                },
                                timestamp=datetime.now()
                            )
                            self._add_alert(alert)

            # 检测价格异动
            if len(sorted_data) >= 2:
                prev_record = sorted_data[-2]

                try:
                    prev_stock_data = StockTickData.from_dict(prev_record)
                    prev_price = prev_stock_data.lastPrice
                except Exception as e:
                    prev_price = prev_record.get('lastPrice', prev_record.get('close', prev_record.get('price', 0)))
                    logging.debug(f"使用原始字段提取前一条记录价格 {stock_code}: {e}")


                if prev_price > 0:
                    price_change = abs(current_price - prev_price) / prev_price
                    if price_change >= self.price_surge_threshold:
                        alert_id = f"{stock_code}_price_surge_{latest_record.get('timestamp', '')}"
                        if alert_id not in self.detected_alerts:
                            self.detected_alerts.add(alert_id)
                            alert = StockAlert(
                                stock_code=stock_code,
                                alert_type=AlertType.PRICE_SURGE,
                                level=AlertLevel.MEDIUM,
                                message=f"{stock_code} 价格异动！价格变化 {price_change:.2%}",
                                data={
                                    'price_change': price_change,
                                    'current_price': current_price,
                                    'prev_price': prev_price
                                },
                                timestamp=datetime.now()
                            )
                            self._add_alert(alert)

            # 检测突破（当日新高）
            high_prices = []
            for r in sorted_data[:-1]:
                try:
                    stock_data = StockTickData.from_dict(r)
                    high_prices.append(stock_data.lastPrice)
                except Exception as e:
                    high_prices.append(r.get('lastPrice', r.get('close', r.get('price', 0))))
                    logging.debug(f"使用原始字段提取历史价格 {stock_code}: {e}")

            
            high_price = max(high_prices, default=0)
            if high_price > 0 and current_price > high_price * (1 + self.breakout_threshold):
                alert_id = f"{stock_code}_breakout_{latest_record.get('timestamp', '')}"
                if alert_id not in self.detected_alerts:
                    self.detected_alerts.add(alert_id)
                    alert = StockAlert(
                        stock_code=stock_code,
                        alert_type=AlertType.BREAKOUT,
                        level=AlertLevel.MEDIUM,
                        message=f"{stock_code} 突破新高！当前价格 {current_price}",
                        data={
                            'current_price': current_price,
                            'high_price': high_price,
                            'breakout_pct': (current_price - high_price) / high_price
                        },
                        timestamp=datetime.now()
                    )
                    self._add_alert(alert)

        except Exception as e:
            logging.error(f"检测其他异常时出错 {stock_code}: {e}")

    def _add_alert(self, alert: StockAlert):
        """添加异常提示"""
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history.pop(0)

        # 缓存到Redis
        try:
            if self.cache_manager:
                alert_data = [alert.to_dict()]
                self.cache_manager.cache_filter_result(
                    {'type': 'alerts', 'timestamp': datetime.now().isoformat()},
                    alert_data,
                    300  # 5分钟过期
                )
        except Exception as e:
            logging.error(f"缓存异常提示失败: {e}")

    def get_recent_alerts(self, minutes: int = 30) -> List[StockAlert]:
        """获取最近的异常提示"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [alert for alert in self.alert_history if alert.timestamp >= cutoff_time]

    def get_alerts_by_type(self, alert_type: AlertType, minutes: int = 30) -> List[StockAlert]:
        """获取指定类型的最近提示"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [alert for alert in self.alert_history
                if alert.alert_type == alert_type and alert.timestamp >= cutoff_time]

    def get_alerts_by_stock(self, stock_code: str, minutes: int = 30) -> List[StockAlert]:
        """获取指定股票的最近提示"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [alert for alert in self.alert_history
                if alert.stock_code == stock_code and alert.timestamp >= cutoff_time]

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
        for alert_type in AlertType:
            count = len([a for a in today_alerts if a.alert_type == alert_type])
            if count > 0:
                stats['by_type'][alert_type.value] = count

        # 按级别统计
        for level in AlertLevel:
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
alert_detector = None


def get_alert_detector() -> AlertDetector:
    """获取全局异常检测器实例"""
    global alert_detector
    if alert_detector is None:
        alert_detector = AlertDetector()
    return alert_detector
