import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import pytz  # 处理时区问题


def preprocess_data():
    print("开始数据预处理...")

    # 1. 修正数据加载路径和方法
    data_path = "../data/split/AU9999.XSGE_2025.csv"

    # 检查文件是否存在
    if not os.path.exists(data_path):
        print(f"错误：数据文件不存在 - {data_path}")
        return

    # 加载数据 - 确保日期列解析正确
    raw_data = pd.read_csv(
        data_path,
        parse_dates=["date"],
        dtype={
            'open': float,
            'high': float,
            'low': float,
            'close': float,
            'volume': float
        }
    )

    # 确保datetime时区一致（国内通常用上海时区）
    shanghai_tz = pytz.timezone('Asia/Shanghai')
    raw_data['date'] = raw_data['date'].dt.tz_localize(shanghai_tz)

    # 检查数据质量
    if raw_data.empty:
        print("错误：加载的数据为空！")
        return

    print(f"原始数据加载完成，共 {len(raw_data)} 条记录")

    # 创建多级采样（离线预处理）
    resolutions = {
        '1min': ('1min', {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}),
        '5min': ('5min', {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}),
        '15min': ('15min', {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}),
        '30min': ('30min', {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}),
        '1H': ('1H', {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}),
        '4H': ('4H', {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}),
        '1D': ('1D', {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
    }

    # 确保缓存目录存在
    os.makedirs("cache", exist_ok=True)

    # 为每种时间周期生成预处理数据
    for res, (freq, agg_dict) in resolutions.items():
        print(f"开始处理 {res} 周期数据...")

        # 创建分辨率目录
        res_dir = f"cache/{res}"
        os.makedirs(res_dir, exist_ok=True)

        # 重采样并聚合
        df_res = raw_data.set_index('date').copy()

        if res != '1min':  # 1分钟数据不需要重采样
            df_res = df_res.resample(freq).agg(agg_dict)

            # 确保重采样后数据不为空
            if df_res.empty:
                print(f"警告：{res} 重采样后数据为空！")
                continue

            # 重置索引（使date成为普通列）
            df_res = df_res.reset_index()

            # 清理数据 - 去除NaN值
            df_res.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)

            # 确保索引连续
            df_res['date'] = df_res['date'].dt.tz_localize(None)  # 移除时区信息
        else:
            # 1分钟数据直接处理
            df_res = df_res.reset_index()

        # 添加技术指标
        df_res['MA20'] = df_res['close'].rolling(20, min_periods=1).mean()
        df_res['MA50'] = df_res['close'].rolling(50, min_periods=1).mean()

        # 添加日期时间相关列
        df_res['year'] = df_res['date'].dt.year

        # 按年分割存储
        for year, group in df_res.groupby('year'):
            if not group.empty:
                file_path = f"{res_dir}/{year}.parquet"
                print(f"保存 {res} {year}年数据到 {file_path} ({len(group)}条)")

                # 移除不必要的列
                group_to_save = group.drop(columns=['year'], errors='ignore')

                # 确保日期列作为普通列保存
                if 'date' not in group_to_save.columns:
                    group_to_save = group_to_save.reset_index()

                # 保存为Parquet格式
                group_to_save.to_parquet(file_path)

                # 检查文件是否生成成功
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    print(f"文件保存成功 ({os.path.getsize(file_path) / 1024:.2f} KB)")
                else:
                    print(f"错误：文件未能正确保存 - {file_path}")

    print("数据预处理完成！")
    print("--------------------------------------")
    print("检查缓存目录内容:")
    os.system("tree -d cache || dir /s cache")  # 列出缓存目录结构


if __name__ == '__main__':
    preprocess_data()