import time
from tools.feature_info import FeatureInfo
from utils.tushare_helper import TushareHelper
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


# 统一调度器调用的函数
def run_data_preloader():
    """期货数据预加载任务 - 由统一调度器调用"""
    logging.info("期货数据预加载任务开始执行...")
preload_main_constracts()
    logging.info("期货数据预加载任务执行完毕。")


if __name__ == "__main__":
    # 直接运行任务（用于测试）
    run_data_preloader()
