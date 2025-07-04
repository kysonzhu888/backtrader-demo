import time
from feature_info import FeatureInfo
from tushare_helper import TushareHelper
import logging
import os
from datetime import datetime, timedelta
from threading import Timer


def preload_main_constracts():
    exchange_product_types = FeatureInfo.get_exchange_product_types()

    # 一层遍历
    for exchange, product_types in exchange_product_types.items():

        # 二层遍历
        logging.warning(f"start get_main_contracts of {exchange}... ")
        product_type_list = []
        for product_type_item in product_types:
            TushareHelper.get_main_contract(exchange, product_type_item)
            product_type_list.append(product_type_item)
            time.sleep(1)
        logging.warning(f"get_main_contract of {exchange}:{product_type_list} completed. ")


# 启动后立即执行一次
preload_main_constracts()


# 使用Timer进行调度
def schedule_preload_task():
    # 设置下次运行时间
    now = datetime.now()
    specific_times = ['07:30', '10:20', '12:00', '20:00']
    next_run = None
    for time_point in specific_times:
        run_time = now.replace(hour=int(time_point.split(':')[0]), minute=int(time_point.split(':')[1]), second=0,
                               microsecond=0)
        if now < run_time:
            next_run = run_time
            break
    if not next_run:
        next_run = now.replace(hour=int(specific_times[0].split(':')[0]), minute=int(specific_times[0].split(':')[1]),
                               second=0, microsecond=0) + timedelta(days=1)
    delay = (next_run - now).total_seconds()

    # 如果是 debug 模式，则立刻执行
    if os.getenv('DEBUG_MODE') == '1':
        delay = 3

    logging.info(f"预加载（期货主力合约代号）任务将在{delay}秒后执行，请等待...")
    Timer(delay, preload_main_constracts).start()


# 启动调度任务
schedule_preload_task()

logging.info("预加载主力合约数据任务已启动")
