#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
期货持仓数据分析器
自动获取IH、IF、IC、IM四个品种的持仓数据
计算净空单量和变化量
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import logging
import os
import io

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FuturesPositionAnalyzer:
    def __init__(self):
        self.base_url = "http://www.cffex.com.cn/sj/ccpm"
        self.symbols = ['IH', 'IF', 'IC', 'IM']
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_date_str(self, date=None):
        """获取日期字符串"""
        if date is None:
            now = datetime.now()
            # 如果当前时间比下午5点早，取昨天的数据
            if now.hour < 17:
                date = now - timedelta(days=1)
            else:
                date = now
        return date.strftime("%Y%m/%d")

    def get_csv_url(self, symbol, date_str):
        """构建CSV文件URL"""
        return f"{self.base_url}/{date_str}/{symbol}_1.csv"

    def download_csv(self, symbol, date_str):
        """下载CSV文件"""
        url = self.get_csv_url(symbol, date_str)
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            # 使用正确的编码
            response.encoding = 'gbk'
            return response.text
        except Exception as e:
            logger.error(f"下载{symbol}数据失败: {e}")
            return None

    def parse_csv(self, csv_content, symbol):
        """解析CSV内容"""
        if not csv_content:
            return None

        try:
            # 使用pandas解析CSV，跳过第一行（标题行）
            df = pd.read_csv(io.StringIO(csv_content), encoding='gbk', skiprows=1)

            # 根据实际数据结构重命名列
            if len(df.columns) >= 12:
                df.columns = ['日期', '合约', '排名', '期货公司', '多头持仓', '多头增减',
                              '期货公司2', '空头持仓', '空头增减', '期货公司3', '净持仓', '净持仓增减']

            # 只保留前20名数据
            df = df.head(20)

            # 转换数据类型
            numeric_columns = ['多头持仓', '多头增减', '空头持仓', '空头增减', '净持仓', '净持仓增减']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            return df

        except Exception as e:
            logger.error(f"解析{symbol} CSV失败: {e}")
            return None

    def calculate_summary(self, df, symbol):
        """计算汇总数据"""
        if df is None or df.empty:
            return None

        try:
            # 找到中信期货的数据（处理编码问题）
            citic_data = df[df['期货公司'].str.contains('中信', na=False, case=False)]
            if citic_data.empty:
                # 尝试其他可能的名称
                citic_data = df[df['期货公司'].str.contains('中信期货', na=False, case=False)]
            if citic_data.empty:
                # 尝试英文名称
                citic_data = df[df['期货公司'].str.contains('CITIC', na=False, case=False)]

            other_data = df[~df['期货公司'].str.contains('中信', na=False, case=False)]
            if not citic_data.empty:
                other_data = df[~df.index.isin(citic_data.index)]

            # 中信期货的空单量和变化量
            citic_short = citic_data['空头持仓'].sum() if not citic_data.empty else 0
            citic_short_change = citic_data['空头增减'].sum() if not citic_data.empty else 0

            # 其他玩家的空单量和变化量
            other_short = other_data['空头持仓'].sum() if not other_data.empty else 0
            other_short_change = other_data['空头增减'].sum() if not other_data.empty else 0

            # 总空单量和变化量
            total_short = citic_short + other_short
            total_short_change = citic_short_change + other_short_change

            # 计算净空单（多头-空头）
            total_long = df['多头持仓'].sum()
            net_position = total_long - total_short

            # 净空单变化量
            total_long_change = df['多头增减'].sum()
            net_change = total_long_change - total_short_change

            return {
                'symbol': symbol,
                'citic_short': citic_short,
                'citic_short_change': citic_short_change,
                'other_short': other_short,
                'other_short_change': other_short_change,
                'total_short': total_short,
                'total_short_change': total_short_change,
                'net_position': net_position,
                'net_change': net_change
            }

        except Exception as e:
            logger.error(f"计算{symbol}汇总失败: {e}")
            return None

    def get_daily_data(self, date=None):
        """获取指定日期的所有数据"""
        date_str = self.get_date_str(date)
        logger.info(f"开始获取 {date_str} 的持仓数据")

        results = {}

        for symbol in self.symbols:
            logger.info(f"正在获取 {symbol} 数据...")

            # 下载数据
            csv_content = self.download_csv(symbol, date_str)
            if csv_content:
                # 解析数据
                df = self.parse_csv(csv_content, symbol)
                if df is not None:
                    # 计算汇总
                    summary = self.calculate_summary(df, symbol)
                    if summary:
                        results[symbol] = summary
                        logger.info(f"{symbol} 数据获取成功")
                    else:
                        logger.warning(f"{symbol} 汇总计算失败")
                else:
                    logger.warning(f"{symbol} 数据解析失败")
            else:
                logger.warning(f"{symbol} 数据下载失败")

        return results

    def generate_report(self, daily_data):
        """生成播报内容"""
        if not daily_data:
            return "今日数据获取失败"

        report = f"【{datetime.now().strftime('%Y年%m月%d日')} 期货持仓播报】\n\n"

        # 计算总计
        total_citic_short_change = 0
        total_other_short_change = 0
        total_net_change = 0

        for symbol, data in daily_data.items():
            citic_change = data['citic_short_change']
            other_change = data['other_short_change']
            net_change = data['net_change']

            total_citic_short_change += citic_change
            total_other_short_change += other_change
            total_net_change += net_change

            # 中信期货变化
            citic_text = "减空" if citic_change < 0 else "加空"
            # 其他玩家变化
            other_text = "减空" if other_change < 0 else "加空"
            # 净空单变化
            net_text = "减空" if net_change < 0 else "加空"

            report += f"{symbol}：\n"
            report += f"  中信期货：{citic_text} {abs(citic_change):,.0f} 手\n"
            report += f"  其他玩家：{other_text} {abs(other_change):,.0f} 手\n"
            report += f"  净空单：{net_text} {abs(net_change):,.0f} 手\n\n"

        report += f"【总计】\n"
        report += f"中信期货：{'减空' if total_citic_short_change < 0 else '加空'} {abs(total_citic_short_change):,.0f} 手\n"
        report += f"其他玩家：{'减空' if total_other_short_change < 0 else '加空'} {abs(total_other_short_change):,.0f} 手\n"
        report += f"合计：{'减空' if total_net_change < 0 else '加空'} {abs(total_net_change):,.0f} 手"

        return report


def main():
    """主函数"""
    analyzer = FuturesPositionAnalyzer()

    # 获取今日数据
    daily_data = analyzer.get_daily_data()

    # 生成播报
    report = analyzer.generate_report(daily_data)

    print(report)

    # 保存到文件
    with open('daily_position_report.txt', 'w', encoding='utf-8') as f:
        f.write(report)

    logger.info("播报内容已保存到 daily_position_report.txt")


if __name__ == "__main__":
    main() 