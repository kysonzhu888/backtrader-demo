import environment
import logging
from threading import Timer

import time
from date_utils import DateUtils
from load_feature_data import FeatureDataLoader
from feature_info import FeatureInfo
from trading_time_helper import TradingTimeHelper


def load_data_for_product():
    exchange_product_types = FeatureInfo.get_exchange_product_types()

    # 一层遍历
    for exchange, product_types in exchange_product_types.items():

        trading_time_product_types = []
        # 二层遍历
        for product_type_item in product_types:
            trading_time_helper = TradingTimeHelper(product_type_item)
            if trading_time_helper.is_trading_time():
                trading_time_product_types.append(product_type_item)
        if len(trading_time_product_types) > 0:
            loader = FeatureDataLoader(exchange=exchange, product_types=trading_time_product_types)
            loader.load_data()
        else:
            logging.info(f"no feature is now in trading time of {exchange}. waiting for next loop...")


def run_scheduled_tasks():
    """
    定时执行任务，每隔 6 秒执行一次。
    """
    # 获取当前时间
    now = DateUtils.now()
    current_second = now.second

    #避免频繁打印日志
    if current_second % 4 == 0:
        logging.info(f"[features min loader ] current system time :{DateUtils.now()} ,looping...")

    if current_second in range(0, 8):
        load_data_for_product()
        Timer(6, run_scheduled_tasks).start()

    else:
        # 设置定时器，每隔10秒执行一次
        Timer(6, run_scheduled_tasks).start()


def main():
    # 启动定时任务
    run_scheduled_tasks()


if __name__ == "__main__":
    main()
