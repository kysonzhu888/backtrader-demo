import environment
import os

import logging
import time
import tushare as ts
from datetime import datetime, timedelta
from threading import Timer

from database_helper import DatabaseHelper
from date_utils import DateUtils


class FeatureDailyLoader:

    def __init__(self, api_key):
        self.pro = ts.pro_api(api_key)

    def get_futures_daily(self, ts_codes, end_date):
        # 计算日期范围
        start_date = (datetime.strptime(end_date, '%Y%m%d') - timedelta(days=80)).strftime('%Y%m%d')

        # 获取有效的 trade_date
        sample_df = self.pro.fut_daily(ts_code=ts_codes[0], start_date=start_date, end_date=end_date)
        if sample_df.empty:
            logging.error("No trading data available for the given end_date.")
            return []
        valid_trade_date = sample_df.iloc[0]['trade_date']

        db_helper = DatabaseHelper()

        def extract_product_type(ts_code):
            import re
            match = re.match(r"^[A-Za-z]+", ts_code)
            return match.group(0) if match else ts_code

        for ts_code in ts_codes:
            # 获取期货日线数据
            daily_df = self.pro.fut_daily(ts_code=ts_code, start_date=start_date, end_date=valid_trade_date)
            '''
            表头，示例数据如下
            ts_code	trade_date	pre_close	pre_settle	open	high	low	close	settle	change1	change2	vol	amount	oi	oi_chg
            AU2508.SHF	20250509	790.78	800.94	795.86	797.5	777.1	788.42	788.16	-12.52	-12.78	663192	52270662.4	205859	7304
            '''
            time.sleep(2)
            if daily_df.empty:
                logging.warning(f"{ts_code} 没有获取到日线数据，跳过。")
                continue

            # 保证字段顺序和表结构一致
            columns = [
                'ts_code', 'trade_date', 'pre_close', 'pre_settle', 'open', 'high', 'low', 'close',
                'settle', 'change1', 'change2', 'vol', 'amount', 'oi', 'oi_chg'
            ]
            for col in columns:
                if col not in daily_df.columns:
                    daily_df[col] = None
            daily_df = daily_df[columns]

            product_type = extract_product_type(ts_code)
            # 只需调用一次插入方法，内部会自动建表
            db_helper.store_daily_feature_data(daily_df, product_type)
            logging.info(f"{ts_code} 日线数据已存入 futures_daily_data_{product_type} 表。")

        # 只保留最新的日数据
        return daily_df


def run_daily_loader():
    db_helper = DatabaseHelper()
    mapping_ts_codes = db_helper.get_all_mapping_ts_codes()
    if len(mapping_ts_codes) > 0:
        api_key = environment.tushare_token  # 替换为你的API密钥
        loader = FeatureDailyLoader(api_key)
        time_str = datetime.now().strftime('%Y%m%d')
        loader.get_futures_daily(mapping_ts_codes, end_date=time_str)


def schedule_daily_loader_task():
    # 设置下次运行时间
    now = DateUtils.now()
    next_run = now.replace(hour=7, minute=48, second=0, microsecond=0)
    if now >= next_run:
        next_run += timedelta(days=1)
    delay = (next_run - now).total_seconds()

    # 如果是 debug 模式，则立刻执行
    if os.getenv('DEBUG_MODE') == '1':
        delay = 3

    logging.info(f"日线数据加载器即将在{delay}秒后执行，请等待...")
    Timer(delay, run_daily_loader).start()


if __name__ == "__main__":
    schedule_daily_loader_task()
