import logging
import time
from datetime import datetime, timedelta
from threading import Timer
import pandas as pd
from wechat_helper import WeChatHelper
from trading_time_helper import TradingTimeHelper
from database_helper import DatabaseHelper


# 假设数据库接口如下（请根据实际情况替换）
def get_latest_minute_timestamp(product_type):
    db = DatabaseHelper()
    df = db.read_feature_data(product_type)
    if df is not None and not df.empty and 'time' in df.columns:
        latest_time = pd.to_datetime(df['time']).max()
        return latest_time
    return None


def check_minute_data():
    now = datetime.now()
    product_types = ["AU", "IM"]
    missing_products = []
    for product in product_types:
        trading_helper = TradingTimeHelper(product)
        if trading_helper.is_trading_time():
            latest_ts = get_latest_minute_timestamp(product)
            # 允许1分钟误差（防止刚好整点没入库）
            if latest_ts is None or (now - latest_ts) > timedelta(minutes=2):
                missing_products.append(product)
    if missing_products:
        wx = WeChatHelper()
        msg = f"【分钟数据监控】{','.join(missing_products)} 最近一分钟数据未入库，请检查数据服务！"
        wx.send_message(msg, "老公老婆")
    else:
        logging.debug("ok,no problem")

    # 每5分钟检查一次
    Timer(300, check_minute_data).start()


if __name__ == "__main__":
    check_minute_data()
