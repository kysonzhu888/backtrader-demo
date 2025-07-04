import environment
import os
from threading import Timer

import logging
import time
import re
from datetime import datetime, timedelta
import pandas as pd
from database_helper import DatabaseHelper
from date_utils import DateUtils
from feature_info import FeatureInfo
import matplotlib.pyplot as plt

from pilot_helper import PilotHelper
import matplotlib

from tushare_helper import TushareHelper
from wechat_helper import WeChatHelper

matplotlib.use('Agg')


class FeaturesWeeklyReport:

    @staticmethod
    def get_futures_change_weekly(ts_codes, end_date):
        db_helper = DatabaseHelper()
        rst_df = []

        # 获取有效的 trade_date
        sample_df = TushareHelper.fut_weekly(ts_codes[0], end_date=end_date)
        if sample_df.empty:
            logging.error("No weekly data available for the given end_date.")
            return []
        valid_trade_date = sample_df.iloc[0]['trade_date']

        existing_data = db_helper.get_existing_weekly_changes(ts_codes, valid_trade_date)
        existing_ts_codes = set(existing_data['ts_code']) if not existing_data.empty else set()

        for ts_code in ts_codes:
            if ts_code in existing_ts_codes:
                logging.info(f"Data for {ts_code} already exists in the weekly database.")
                row = existing_data[existing_data['ts_code'] == ts_code].iloc[0]
                rst_df.append(row.to_dict())
                continue

            weekly_df = TushareHelper.fut_weekly(ts_code=ts_code, end_date=valid_trade_date)
            time.sleep(2)
            if weekly_df.empty:
                logging.error(f"No weekly data available for {ts_code}.")
                continue
            latest_weekly = weekly_df.iloc[0].copy()
            latest_weekly['weekly_pct_change'] = (latest_weekly['close'] - latest_weekly['pre_close']) / latest_weekly[
                'pre_close'] * 100
            combined_df = latest_weekly[['ts_code', 'trade_date', 'weekly_pct_change']].copy()
            logging.info(f"add one more:\n {combined_df}")
            product_type_match = re.match(r"^[A-Za-z]+", ts_code)
            product_type = product_type_match.group(0) if product_type_match else ""

            product_name = FeatureInfo.get_product_name(product_type)
            combined_df['product_name'] = product_name

            db_helper.store_weekly_change(
                ts_code=combined_df['ts_code'],
                trade_date=combined_df['trade_date'],
                weekly_pct_change=combined_df['weekly_pct_change'],
                product_name=product_name
            )
            rst_df.append(combined_df)
        return rst_df

    @staticmethod
    def generate_sorted_report(result):
        # 将结果转换为 DataFrame
        df = pd.DataFrame(result)
        # 按涨跌幅排序
        df = df.sort_values(by='weekly_pct_change', ascending=False)
        return df

    @staticmethod
    def plot_sorted_report(df):
        PilotHelper.get_cn_font(plt)

        plt.figure(figsize=(10, 12))
        colors = ['#ff4444' if x >= 0 else '#33aa33' for x in df['weekly_pct_change']]
        bars = plt.barh(y=df['product_name'], width=df['weekly_pct_change'], color=colors, height=0.6)

        for bar in bars:
            width = bar.get_width()
            label_x = width if width > 0 else width - 0.5
            plt.text(label_x, bar.get_y() + bar.get_height() / 2, f'{width:.2f}%', va='center',
                     ha='left' if width < 0 else 'right', fontsize=10)

        current_week = df['trade_date'].iloc[-1]
        plt.title(f"期货周涨跌幅({current_week} 周)", fontsize=14, pad=20)
        plt.xlabel("涨跌幅 (%)", fontsize=12)
        plt.grid(axis='x', linestyle='--', alpha=0.6)
        plt.axvline(0, color='gray', linewidth=0.8)
        plt.tight_layout()
        file_path = f'data/weekly_{current_week}_sorted_report.png'
        os.makedirs(os.path.dirname(file_path), exist_ok=True)  # 确保目录存在

        plt.savefig(file_path)
        logging.info(f"{file_path} 图片生成成功")
        plt.close()
        return file_path

    @staticmethod
    def summarize_weekly_pct_change_report(df):
        """
        生成期货日报统计总结
        """
        total_count = len(df)
        product_types = df['product_name'].nunique()
        up_count = (df['weekly_pct_change'] > 0).sum()
        down_count = (df['weekly_pct_change'] < 0).sum()
        up_pct = up_count / total_count * 100 if total_count else 0
        down_pct = down_count / total_count * 100 if total_count else 0
        return (
            f"总结如下：上周期货市场中，统计了{product_types}种期货"
            f"其中上涨家数{up_count}家，占总数的{up_pct:.2f}%；"
            f"下跌家数{down_count}家，占总家数的{down_pct:.2f}%。"
        )


# 示例调用
def run_weekly_report():
    db_helper = DatabaseHelper()
    mapping_ts_codes = db_helper.get_all_mapping_ts_codes()
    if len(mapping_ts_codes) > 0:
        result = FeaturesWeeklyReport.get_futures_change_weekly(ts_codes=mapping_ts_codes,
                                                                end_date=datetime.now().strftime('%Y%m%d'))
        sorted_report = FeaturesWeeklyReport.generate_sorted_report(result)
        file_path = FeaturesWeeklyReport.plot_sorted_report(sorted_report)

        wechat_helper = WeChatHelper()
        wechat_helper.send_message("早安，以下是上周的商品期货周报：\n", environment.group_chat_name_vip)
        wechat_helper.send_file(file_path)

        # 生成并发送总结
        summary_msg = FeaturesWeeklyReport.summarize_weekly_pct_change_report(sorted_report)
        wechat_helper.send_message(summary_msg, environment.group_chat_name_vip)

    else:
        logging.error("缺少主力合约数据，请先启动 preload_main_constracts")


def schedule_weekly_task():
    # 设置下次运行时间
    now = DateUtils.now()
    next_run = now.replace(hour=7, minute=25, second=0, microsecond=0)
    if now >= next_run:
        next_run += timedelta(days=1)
    delay = (next_run - now).total_seconds()

    # 如果是 debug 模式，则立刻执行
    if os.getenv('DEBUG_MODE') == '1':
        delay = 3

    logging.info(f"周报即将在{delay}秒后执行，请等待...")
    Timer(delay, run_weekly_report).start()


if __name__ == "__main__":
    schedule_weekly_task()
