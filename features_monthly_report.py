import environment
import logging
import time
import re
import tushare as ts
from datetime import datetime, timedelta
import pandas as pd

from database_helper import DatabaseHelper
from feature_info import FeatureInfo
import matplotlib.pyplot as plt
import matplotlib.font_manager as font_manager


class FeaturesMonthlyReport:
    def __init__(self, api_key):
        self.pro = ts.pro_api(api_key)

    @staticmethod
    def plot_monthly_sorted_report(df):
        font_path = "/System/Library/Fonts/STHeiti Medium.ttc"
        font_prop = font_manager.FontProperties(fname=font_path)
        font_manager.fontManager.addfont(font_path)
        plt.rcParams['font.family'] = font_prop.get_name()
        plt.rcParams['axes.unicode_minus'] = False

        plt.figure(figsize=(10, 12))
        colors = ['#ff4444' if x >= 0 else '#33aa33' for x in df['monthly_pct_change']]
        bars = plt.barh(y=df['product_name'], width=df['monthly_pct_change'], color=colors, height=0.6)

        for bar in bars:
            width = bar.get_width()
            label_x = width if width > 0 else width - 0.5
            plt.text(label_x, bar.get_y() + bar.get_height() / 2, f'{width:.2f}%', va='center',
                     ha='left' if width < 0 else 'right', fontsize=10)

        current_month = df['trade_date'].iloc[-1]
        plt.title(f"期货月涨跌幅({current_month} 月)", fontsize=14, pad=20)
        plt.xlabel("涨跌幅 (%)", fontsize=12)
        plt.grid(axis='x', linestyle='--', alpha=0.6)
        plt.axvline(0, color='gray', linewidth=0.8)
        plt.tight_layout()
        pic_path = f'data/monthly_{current_month}_sorted_report.png'
        plt.savefig(pic_path)
        plt.close()
        logging.info(f"{pic_path} 图片生成成功")

    def get_futures_change_monthly(self, ts_codes, end_date):
        db_helper = DatabaseHelper()
        rst_df = []

        # 获取有效的 trade_date
        sample_df = self.pro.fut_weekly_monthly(ts_code=ts_codes[0], end_date=end_date, freq='month')
        if sample_df.empty:
            logging.error("No monthly data available for the given end_date.")
            return []
        valid_trade_date = sample_df.iloc[0]['trade_date']

        existing_data = db_helper.get_existing_monthly_changes(ts_codes, valid_trade_date)
        existing_ts_codes = set(existing_data['ts_code']) if not existing_data.empty else set()

        for ts_code in ts_codes:
            if ts_code in existing_ts_codes:
                logging.info(f"Data for {ts_code} already exists in the monthly database.")
                row = existing_data[existing_data['ts_code'] == ts_code].iloc[0]
                rst_df.append(row.to_dict())
                continue

            monthly_df = self.pro.fut_weekly_monthly(ts_code=ts_code, end_date=valid_trade_date, freq='month')
            time.sleep(2)
            if monthly_df.empty:
                logging.error(f"No monthly data available for {ts_code}.")
                continue
            latest_monthly = monthly_df.iloc[0].copy()
            latest_monthly['monthly_pct_change'] = (latest_monthly['close'] - latest_monthly['pre_close']) / latest_monthly['pre_close'] * 100
            combined_df = latest_monthly[['ts_code', 'trade_date', 'monthly_pct_change']].copy()
            logging.info(f"add one more:\n {combined_df}")
            product_type_match = re.match(r"^[A-Za-z]+", ts_code)
            product_type = product_type_match.group(0) if product_type_match else ""
            product_name = FeatureInfo.get_product_name(product_type)
            db_helper.store_monthly_change(
                ts_code=combined_df['ts_code'],
                trade_date=combined_df['trade_date'],
                monthly_pct_change=combined_df['monthly_pct_change'],
                product_name=product_name
            )
            rst_df.append(combined_df)
        return rst_df

    def generate_sorted_report(self, result):
        # 将结果转换为 DataFrame
        df = pd.DataFrame(result)
        # 按涨跌幅排序
        df = df.sort_values(by='monthly_pct_change', ascending=False)
        return df


# 示例调用
if __name__ == "__main__":
    api_key = environment.tushare_token  # 替换为你的API密钥
    reportor = FeaturesMonthlyReport(api_key)

    db_helper = DatabaseHelper()
    mapping_ts_codes = db_helper.get_all_mapping_ts_codes()
    if len(mapping_ts_codes) > 0:
        # end_time = datetime.now().strftime('%Y%m%d')
        end_time = (datetime.now() - timedelta(days=31)).strftime('%Y%m%d')
        result = reportor.get_futures_change_monthly(ts_codes=mapping_ts_codes,end_date=end_time)
        sorted_report = reportor.generate_sorted_report(result)
        FeaturesMonthlyReport.plot_monthly_sorted_report(sorted_report)
    else:
        logging.error("缺少主力合约数据，请先启动 preload_main_constracts")

