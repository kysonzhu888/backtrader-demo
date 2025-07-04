#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常检测器测试脚本
"""

import logging
import time
from datetime import datetime, timedelta
from mini_stock.alert_detector import get_alert_detector, AlertType
from mini_stock.redis_cache_manager import get_cache_manager

def test_alert_detector():
    """测试异常检测器"""
    logger = logging.getLogger(__name__)

    # 获取检测器和缓存管理器
    detector = get_alert_detector()
    cache_manager = get_cache_manager()

    logger.info("开始测试异常检测器...")

    # 测试1: 检查缓存统计
    logger.info("1. 检查缓存统计...")
    stats = cache_manager.get_cache_stats()
    logger.info(f"缓存统计: {stats}")

    # 测试2: 获取所有股票的最新数据
    logger.info("2. 获取所有股票的最新数据...")
    latest_data = cache_manager.get_multiple_latest_data([])
    logger.info(f"共有 {len(latest_data)} 只股票的数据")

    if latest_data:
        # 显示前几只股票的数据
        for i, (code, data) in enumerate(list(latest_data.items())[:3]):
            logger.info(f"  {code}: {data}")

    # 测试3: 获取最近的异常提示
    logger.info("3. 获取最近的异常提示...")
    recent_alerts = detector.get_recent_alerts(minutes=30)
    logger.info(f"最近30分钟有 {len(recent_alerts)} 条异常提示")

    for alert in recent_alerts[:5]:  # 显示前5条
        logger.info(f"  {alert.message}")

    # 测试4: 获取异常统计
    logger.info("4. 获取异常统计...")
    alert_stats = detector.get_alert_stats()
    logger.info(f"异常统计: {alert_stats}")

    # 测试5: 按类型获取异常
    logger.info("5. 按类型获取异常...")
    for alert_type in AlertType:
        alerts = detector.get_alerts_by_type(alert_type, minutes=30)
        if alerts:
            logger.info(f"  {alert_type.value}: {len(alerts)} 条")

    # 测试6: 模拟检测过程
    logger.info("6. 模拟检测过程...")
    logger.info("等待5秒让检测器运行...")
    time.sleep(5)

    # 再次获取异常提示
    recent_alerts = detector.get_recent_alerts(minutes=1)
    logger.info(f"最近1分钟有 {len(recent_alerts)} 条异常提示")

    logger.info("测试完成！")


def test_single_stock_alert():
    """测试单只股票的异常检测"""
    logger = logging.getLogger(__name__)

    detector = get_alert_detector()
    cache_manager = get_cache_manager()

    # 获取一只股票的数据进行测试
    latest_data = cache_manager.get_multiple_latest_data([])
    if not latest_data:
        logger.warning("没有股票数据，无法测试")
        return

    test_stock = list(latest_data.keys())[0]
    logger.info(f"测试股票: {test_stock}")

    # 获取该股票的当天数据
    today_data = cache_manager.get_stock_data_today(test_stock)
    logger.info(f"当天数据条数: {len(today_data)}")

    if today_data:
        # 显示数据格式
        logger.info(f"数据格式示例: {today_data[0]}")

        # 检查是否有前收盘价
        first_record = today_data[0]
        preclose = first_record.get('preclose', 0)
        logger.info(f"前收盘价: {preclose}")

        # 检查价格变化
        if len(today_data) >= 2:
            latest_record = today_data[-1]
            current_price = latest_record.get('close', latest_record.get('price', 0))
            if preclose > 0 and current_price > 0:
                change_pct = (current_price - preclose) / preclose
                logger.info(f"当前价格: {current_price}, 涨幅: {change_pct:.2%}")


if __name__ == "__main__":
    try:
        test_alert_detector()
        print("\n" + "=" * 50)
        test_single_stock_alert()
    except Exception as e:
        logging.error(f"测试失败: {e}")
        raise
