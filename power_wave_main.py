import environment  # 确保在其他模块之前导入

import os
from threading import Timer

import threading
import time
import logging

from date_utils import DateUtils
from futures_process_center import FeatureProcessCenter
from feature_info import shfe_product_types, cffex_product_types, dce_product_types, czce_product_types, \
    ine_product_types, gfex_product_types
from pinbar_reporter import PinbarReporter
from trading_time_helper import TradingTimeHelper


def process(interval):
    logging.info(
        f"[power wave] current system time :{DateUtils.now()} , is main tread:  {threading.current_thread() == threading.main_thread()} ,start processing {interval}...")

    logging.info(f"[power wave] start loading data of interval {interval} ...")
    checker = FeatureProcessCenter()
    for product_type in shfe_product_types + cffex_product_types + dce_product_types + czce_product_types + ine_product_types + gfex_product_types:
        # 过滤非交易时段
        if product_type in ['AU']:
            if TradingTimeHelper(product_type).is_trading_time():
                df = checker.resample_data_with(product_type=product_type, interval=interval)
                checker.run_power_wave_strategy_with_resampled_data(df)
            else:
                logging.debug(f"[power wave] {product_type} it's not in trading time...")


def run_scheduled_tasks():
    """
    定时执行任务，每隔15秒执行一次。
    """
    # 获取当前时间
    now = DateUtils.now()
    current_hour = now.hour
    current_minute = now.minute
    current_second = now.second

    if current_second in range(0, 7):
        if current_minute in [5,10,15,20,25,30,35,40,45,50,55,0]:
            process("5min")
            time.sleep(5)
        process("1min")

        logging.info(f"[power wave]{current_minute} candle checking completed,will sleep 10s for next key timestamp......")

        Timer(10, run_scheduled_tasks).start()
    else:
        # 设置定时器，每隔10秒执行一次
        Timer(6, run_scheduled_tasks).start()


def main():
    # 启动定时任务
    run_scheduled_tasks()


if __name__ == "__main__":
    main()
