import environment
import os

import logging
import time
import re
from datetime import datetime, timedelta
import pandas as pd
from threading import Timer

from database_helper import DatabaseHelper
from date_utils import DateUtils
from environment import group_chat_name_vip
from feature_info import FeatureInfo
import matplotlib.pyplot as plt

from pilot_helper import PilotHelper
from wechat_helper import WeChatHelper
import matplotlib
from tushare_helper import TushareHelper  # 新增

matplotlib.use('Agg')


class FeaturesDailyReport:
    def get_futures_change_daily(ts_codes, end_date):
        # 计算日期范围
        start_date = (datetime.strptime(end_date, '%Y%m%d') - timedelta(days=60)).strftime('%Y%m%d')

        db_helper = DatabaseHelper()
        # 获取有效的 trade_date
        sample_df = TushareHelper.fut_daily(ts_code=ts_codes[0], start_date=start_date, end_date=end_date)
        if sample_df.empty:
            logging.error("No trading data available for the given end_date.")
            return []
        valid_trade_date = sample_df.iloc[0]['trade_date']

        existing_data = db_helper.get_existing_daily_changes(ts_codes, valid_trade_date)
        existing_ts_codes = set(existing_data['ts_code']) if not existing_data.empty else set()

        rst_df = []
        for ts_code in ts_codes:
            if ts_code in existing_ts_codes:
                # 如果数据库中已有数据，跳过请求
                logging.info(f"Data for {ts_code} already exists in the database.")
                # 从 existing_ts_codes 中根据 ts_code 获取数据并添加到 rst_df
                row = existing_data[existing_data['ts_code'] == ts_code].iloc[0]
                rst_df.append(row.to_dict())
                continue

            # 获取期货日线数据
            daily_df = TushareHelper.fut_daily(ts_code=ts_code, start_date=start_date, end_date=valid_trade_date)
            time.sleep(2)
            latest_daily = daily_df.iloc[0].copy()  # 使用 copy() 确保是副本
            latest_daily['daily_pct_change'] = (latest_daily['close'] - latest_daily['pre_close']) / latest_daily[
                'pre_close'] * 100

            # 计算20日线数值
            if len(daily_df) >= 20:
                ma20 = daily_df['close'].rolling(window=20).mean().iloc[19]
            else:
                ma20 = None

            # 计算5日线数值
            if len(daily_df) >= 5:
                ma5 = daily_df['close'].rolling(window=5).mean().iloc[4]
            else:
                ma5 = None

            # 合并数据
            combined_df = latest_daily[['ts_code', 'close', 'trade_date', 'daily_pct_change']].copy()
            combined_df['ma20'] = ma20
            combined_df['ma5'] = ma5
            logging.info(f"add one more: {combined_df}")
            # 获取商品期货名
            product_type_match = re.match(r"^[A-Za-z]+", ts_code)
            product_type = product_type_match.group(0) if product_type_match else ""
            product_name = FeatureInfo.get_product_name(product_type)
            combined_df['product_name'] = product_name

            # 存储到数据库
            db_helper.store_daily_change(
                ts_code=combined_df['ts_code'],
                trade_date=combined_df['trade_date'],
                daily_pct_change=combined_df['daily_pct_change'],
                close=combined_df['close'],
                product_name=product_name,
                ma20=ma20,
                ma5=ma5
            )
            rst_df.append(combined_df)

        # 只保留最新的日数据
        return rst_df

    @staticmethod
    def generate_sorted_report(result):
        # 将结果转换为 DataFrame
        df = pd.DataFrame(result)
        # 按涨跌幅排序
        df = df.sort_values(by='daily_pct_change', ascending=False)
        return df

    @staticmethod
    def plot_sorted_report(df):
        PilotHelper.get_cn_font(plt)
        # 绘制柱状图
        plt.figure(figsize=(10, 12))
        colors = ['#ff4444' if x >= 0 else '#33aa33' for x in df['daily_pct_change']]
        bars = plt.barh(y=df['product_name'], width=df['daily_pct_change'], color=colors, height=0.6)

        # 添加数据标签
        for bar in bars:
            width = bar.get_width()
            label_x = width if width > 0 else width - 0.1  # 调整标签位置
            plt.text(label_x, bar.get_y() + bar.get_height() / 2, f'{width:.2f}%', va='center',
                     ha='left' if width < 0 else 'right', fontsize=10)

        # 美化图表
        day = df['trade_date'].iloc[-1]
        title = f"期货涨跌幅日报（{day}）"
        plt.title(title, fontsize=14, pad=20)
        plt.xlabel("涨跌幅 (%)", fontsize=12)
        plt.grid(axis='x', linestyle='--', alpha=0.6)
        plt.axvline(0, color='gray', linewidth=0.8)
        plt.tight_layout()
        file_path = f'data/feature_daily_report_{day}.png'
        plt.savefig(file_path)
        plt.close()
        return file_path

    @staticmethod
    def generate_price_above_ma_tables(df):
        PilotHelper.get_cn_font(plt)

        # 计算是否在均线之上
        df['above_ma5'] = df['close'] > df['ma5']
        df['above_ma20'] = df['close'] > df['ma20']

        # 计算ma5和ma20相对于收盘价的百分比差异
        df['ma5_diff_pct'] = ((df['close'] - df['ma5']) / df['close']) * 100
        df['ma20_diff_pct'] = ((df['close'] - df['ma20']) / df['close']) * 100

        # 创建图表
        def create_table(df, title, diff_column, file_suffix):
            table_data = {
                '商品名': df['product_name'],
                '超买（线之上）': df[f'above_{file_suffix}'].apply(lambda x: '是' if x else '否'),
                '超买百分比': df[diff_column].apply(lambda x: f'{x:.2f}%')
            }
            table_df = pd.DataFrame(table_data)

            # 先转为 float
            table_df['超买百分比_float'] = table_df['超买百分比'].str.rstrip('%').astype(float)
            # 按数值排序
            table_df = table_df.sort_values(by='超买百分比_float', ascending=False)
            # 如果只展示字符串列，排序后可以 drop 掉 float 列
            table_df = table_df.drop(columns=['超买百分比_float'])

            # 在计算颜色渐变之前，将'超买百分比'列的数据转换回数值类型
            table_df['超买百分比'] = table_df['超买百分比'].str.rstrip('%').astype(float)
            colors = plt.cm.RdYlGn_r((table_df['超买百分比'] - table_df['超买百分比'].min()) / (
                        table_df['超买百分比'].max() - table_df['超买百分比'].min()))

            # 绘制表格
            fig, ax = plt.subplots(figsize=(14, len(table_df) * 0.24))
            ax.axis('tight')
            ax.axis('off')

            table = ax.table(cellText=table_df.values, colLabels=table_df.columns, cellLoc='center', loc='center')

            # 设置每行的背景颜色
            for i in range(len(table_df)):
                for j in range(len(table_df.columns)):
                    table[(i + 1, j)].set_facecolor(colors[i])

            # 添加表格标题
            plt.title(title, fontsize=16)

            # 使用紧凑布局
            plt.tight_layout()

            # 保存图像
            day = df['trade_date'].iloc[-1]
            file_path = f'data/price_above_{file_suffix}_table_{day}.png'
            os.makedirs(os.path.dirname(file_path), exist_ok=True)  # 确保目录存在
            plt.savefig(file_path)
            plt.close()
            return file_path

        # 生成两个图表
        ma5_file_path = create_table(df, '短期超买（MA5）行情一览', 'ma5_diff_pct', 'ma5')
        ma20_file_path = create_table(df, '中期超买（MA20）行情一览', 'ma20_diff_pct', 'ma20')

        return ma5_file_path, ma20_file_path

    @staticmethod
    def summarize_daily_pct_change_report(df):
        """
        生成期货日报统计总结
        """
        total_count = len(df)
        product_types = df['product_name'].nunique()
        up_count = (df['daily_pct_change'] > 0).sum()
        down_count = (df['daily_pct_change'] < 0).sum()
        up_pct = up_count / total_count * 100 if total_count else 0
        down_pct = down_count / total_count * 100 if total_count else 0
        return (
            f"总结如下：上个交易日期货市场中，统计了{product_types}种期货"
            f"其中上涨家数{up_count}家，占总数的{up_pct:.2f}%；"
            f"下跌家数{down_count}家，占总家数的{down_pct:.2f}%。"
        )

    @staticmethod
    def summarize_above_ma_report(df, ma_col='ma5', above_col='above_ma5', ma_name='5日线'):
        """
        生成均线之上/之下统计总结
        """
        total_count = len(df)
        above_count = df[above_col].sum() if df[above_col].dtype == bool else (df[above_col] == True).sum()
        below_count = total_count - above_count
        above_pct = above_count / total_count * 100 if total_count else 0
        below_pct = below_count / total_count * 100 if total_count else 0
        return (
            f"有{above_count}家位于{ma_name}之上，占总商品数的{above_pct:.2f}%；"
            f"{below_count}家位于{ma_name}之下，占总商品数的{below_pct:.2f}%。"
        )


# 定义定时任务
def run_daily_report():
    db_helper = DatabaseHelper()
    mapping_ts_codes = db_helper.get_all_mapping_ts_codes()
    if len(mapping_ts_codes) > 0:
        result = FeaturesDailyReport.get_futures_change_daily(ts_codes=mapping_ts_codes,
                                                   end_date=datetime.now().strftime('%Y%m%d'))
        sorted_report = FeaturesDailyReport.generate_sorted_report(result)
        ma5_report_file_path, ma20_report_file_path = FeaturesDailyReport.generate_price_above_ma_tables(sorted_report)

        file_path = FeaturesDailyReport.plot_sorted_report(sorted_report)

        wechat_helper = WeChatHelper()
        wechat_helper.send_message("早安，以下是今天的商品期货日报：\n 1.商品涨跌日报：\n", group_chat_name_vip)
        wechat_helper.send_file(file_path)

        # 生成并发送总结
        summary_msg = FeaturesDailyReport.summarize_daily_pct_change_report(sorted_report)
        wechat_helper.send_message(summary_msg, group_chat_name_vip)

        time.sleep(3)
        wechat_helper.send_message("2.商品超买超卖日报：\n（1）5日线超买超卖\n", group_chat_name_vip)
        wechat_helper.send_file(ma5_report_file_path)
        # 生成并发送5日线总结
        ma5_summary_msg = FeaturesDailyReport.summarize_above_ma_report(sorted_report, ma_col='ma5',
                                                                        above_col='above_ma5', ma_name='5日线')
        wechat_helper.send_message(ma5_summary_msg, group_chat_name_vip)

        time.sleep(3)
        wechat_helper.send_message("（2）20日线超买超卖", group_chat_name_vip)
        wechat_helper.send_file(ma20_report_file_path)
        # 生成并发送20日线总结
        ma20_summary_msg = FeaturesDailyReport.summarize_above_ma_report(sorted_report, ma_col='ma20', above_col='above_ma20', ma_name='20日线')
        wechat_helper.send_message(ma20_summary_msg, group_chat_name_vip)
    else:
        logging.error("缺少主力合约数据，请先启动 preload_main_constracts")


def schedule_task():
    # 设置下次运行时间
    now = DateUtils.now()
    next_run = now.replace(hour=8, minute=1, second=0, microsecond=0)
    if now >= next_run:
        next_run += timedelta(days=1)
    delay = (next_run - now).total_seconds()

    # 如果是 debug 模式，则立刻执行
    if os.getenv('DEBUG_MODE') == '1':
        delay = 3

    logging.info(f"日报即将在{delay}秒后执行，请等待...")
    Timer(delay, run_daily_report).start()


if __name__ == "__main__":
    schedule_task()
