from environment import tushare_token
import logging
from datetime import datetime, timedelta
import tushare as ts
from typing import List, Dict, Optional
import os
import json

from date_utils import DateUtils
from database_helper import DatabaseHelper
from logger_utils import Logger
from stock_cache_manager import StockCacheManager


def initialize_tushare():
    # 设置 tushare token
    ts.set_token(tushare_token)
    # 初始化 pro 接口
    return ts.pro_api()


class TushareHelper:

    def __init__(self, product_types, exchange='SHFE'):
        self.product_types = product_types
        self.exchange = exchange
        self.pro = initialize_tushare()
        self.stock_cache = StockCacheManager()

        main_contracts = []
        for product_type in self.product_types:
            main_contract = TushareHelper.get_main_contract(self.exchange, product_type)
            main_contracts.append(main_contract)
        self.main_contracts = main_contracts

    @staticmethod
    def get_main_contract(exchange, product_type):
        pro = initialize_tushare()

        # 使用 DatabaseHelper 处理数据库操作
        db_helper = DatabaseHelper()

        # 从数据库中读取数据（数据库超过 4 小时没有更新也会返回空，这样会强制 main_contract 不定期更新）
        mapping_ts_code = db_helper.get_mapping_ts_code(product_type)

        # 检查数据库中是否有
        if mapping_ts_code is None:
            # 获取期货基础信息
            futures_info = pro.fut_basic(exchange=exchange, fut_type='2', fut_code=product_type)
            if not futures_info.empty:
                main_contract = None
                for index, row in futures_info.iterrows():
                    if '主力' in row['name']:
                        main_contract = row['ts_code']
                        break
                if main_contract is None:
                    if len(futures_info) < 2:
                        main_contract = futures_info['ts_code'].iloc[0]
                    else:
                        main_contract = futures_info['ts_code'].iloc[0]

                # 获取主力合约每日对应的月合约
                df = pro.fut_mapping(ts_code=main_contract)
                mapping_ts_code = df['mapping_ts_code'].iloc[0]
                logging.debug(f"拉取的 ts code 为 {mapping_ts_code}")

                # 将数据写入数据库
                db_helper.insert_or_update_futures_basic_cache(product_type, mapping_ts_code)
        else:
            logging.debug(f"从数据库缓存中获取数据，{product_type}:{mapping_ts_code}")

        return mapping_ts_code

    def fetch_minute_data(self):
        # 获取分钟线数据
        ts_codes = ",".join(self.main_contracts)
        return self.pro.rt_fut_min(ts_code=ts_codes, freq='1MIN')

    @staticmethod
    def fut_daily(ts_code, start_date, end_date):
        """
        封装 tushare 的 fut_daily 方法，返回 DataFrame
        """
        pro = initialize_tushare()
        return pro.fut_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)

    @staticmethod
    def fut_weekly(ts_code, end_date):
        """
        封装 tushare 的 fut_daily 方法，返回 DataFrame
        """
        pro = initialize_tushare()
        return pro.fut_weekly_monthly(ts_code=ts_code, end_date=end_date, freq='week')

    @staticmethod
    def ggt_top10(trade_date=None, market_type=None):
        """
        获取港股通每日成交数据
        
        Args:
            trade_date: 交易日期，格式：YYYYMMDD
            market_type: 市场类型 2：港股通（沪） 4：港股通（深）
            
        Returns:
            DataFrame: 包含以下字段的数据框
                - ts_code: 股票代码
                - name: 股票名称
                - amount: 成交金额（元）
                - net_amount: 净买入金额（元）
                - buy_amount: 买入金额（元）
                - sell_amount: 卖出金额（元）
                - trade_date: 交易日期
        """
        try:
            # 如果没有指定日期，使用当前日期
            if trade_date is None:
                trade_date = datetime.now().strftime('%Y%m%d')
            
            # 调用 Tushare API
            pro = initialize_tushare()
            df = pro.ggt_top10(
                trade_date=trade_date,
                market_type=market_type
            )
            
            if df is None or df.empty:
                Logger.warning(f"未获取到港股通数据，日期：{trade_date}，市场类型：{market_type}", save_to_file=True)
                return None
                
            # 重命名列以保持一致性
            df = df.rename(columns={
                'ts_code': 'ts_code',
                'name': 'name',
                'amount': 'amount',
                'net_amount': 'net_amount',
                'buy_amount': 'buy_amount',
                'sell_amount': 'sell_amount',
                'trade_date': 'trade_date'
            })
            
            # 按成交金额排序
            df = df.sort_values('amount', ascending=False)
            
            Logger.info(f"成功获取港股通数据，日期：{trade_date}，市场类型：{market_type}，数据条数：{len(df)}", save_to_file=True)
            return df
            
        except Exception as e:
            Logger.error(f"获取港股通数据时发生错误: {e}", save_to_file=True)
            return None

    @staticmethod
    def live_news(start_date=None, end_date=None, src=None):
        """
        获取实时新闻
        
        Args:
            start_date: 开始日期，格式：YYYY-MM-DD HH:MM:SS
            end_date: 结束日期，格式：YYYY-MM-DD HH:MM:SS
            src: 新闻来源
            
        Returns:
            DataFrame: 包含新闻数据的数据框
        """
        try:
            # 如果没有指定日期，使用当前时间
            if end_date is None:
                end_date = datetime.now()
            if start_date is None:
                start_date = end_date - timedelta(hours=1)
                
            # 转换日期格式
            start_date = start_date.strftime('%Y-%m-%d %H:%M:%S')
            end_date = end_date.strftime('%Y-%m-%d %H:%M:%S')
                    
            pro = initialize_tushare()

            # 调用 Tushare API
            df = pro.news(
                start_date=start_date,
                end_date=end_date,
                src=src
            )
            
            if df is None or df.empty:
                Logger.warning(f"未获取到新闻数据，时间范围：{start_date} 到 {end_date}，来源：{src}", save_to_file=False)
                return None
                
            Logger.info(f"成功获取新闻数据，时间范围：{start_date} 到 {end_date}，来源：{src}，数据条数：{len(df)}", save_to_file=False)
            return df
            
        except Exception as e:
            Logger.error(f"获取新闻数据时发生错误: {e}", save_to_file=False)
            return None

    @staticmethod
    def get_holder_trade(trade_date: str) -> List[Dict]:
        """
        获取股东增减持数据
        
        Args:
            trade_date: 交易日期，格式：YYYYMMDD
            
        Returns:
            List[Dict]: 增减持数据列表
        """
        try:
            # 获取增减持数据
            pro = initialize_tushare()
            df = pro.stk_holdertrade(ann_date=trade_date)
            
            if df is None or df.empty:
                logging.info(f"日期 {trade_date} 没有增减持数据")
                return []
                
            # 转换为字典列表
            records = df.to_dict('records')
            
            # 只保留减持数据
            reduce_records = [record for record in records if record['in_de'] == 'DE']
            
            # 按减持比例排序
            reduce_records.sort(key=lambda x: x['change_ratio'], reverse=True)
            
            return reduce_records
            
        except Exception as e:
            logging.error(f"获取增减持数据时出错: {str(e)}")
            return []

    @staticmethod
    def _get_latest_trade_date(date: str) -> str:
        """
        获取最近的交易日
        
        Args:
            date: 日期，格式：YYYYMMDD
            
        Returns:
            str: 最近的交易日，格式：YYYYMMDD
        """
        try:
            pro = initialize_tushare()
            # 获取最近30个交易日历
            df = pro.trade_cal(start_date=date, end_date=date, is_open='1')
            if df is not None and not df.empty:
                return date
                
            # 如果当天不是交易日，向前查找最近的交易日
            df = pro.trade_cal(start_date=(datetime.strptime(date, '%Y%m%d') - timedelta(days=30)).strftime('%Y%m%d'),
                             end_date=date,
                             is_open='1')
            if df is not None and not df.empty:
                return df.iloc[0]['cal_date']
                
            return date
            
        except Exception as e:
            logging.error(f"获取最近交易日失败: {str(e)}")
            return date

    @staticmethod
    def format_holder_trade_report(records: List[Dict], report_date: Optional[str] = None) -> str:
        """
        格式化增减持报告
        
        Args:
            records: 增减持数据列表
            report_date: 报告日期，格式：YYYY-MM-DD，默认为今天
            
        Returns:
            str: 格式化后的报告
        """
        if not records:
            return "今日无减持数据"
            
        # 如果没有指定日期，使用今天的日期
        if not report_date:
            report_date = DateUtils.now().strftime('%Y-%m-%d')
            
        report = "【A股减持信息播报】\n"
        report += f"日期: {report_date}\n\n"
        
        # 获取所有公司代码
        ts_codes = [record['ts_code'] for record in records[:10]]
        
        # 从缓存获取公司名称
        stock_cache = StockCacheManager()
        company_dict = stock_cache.update_cache(ts_codes)
        
        # 获取股价数据
        pro = initialize_tushare()
        trade_date = report_date.replace('-', '')
        latest_trade_date = TushareHelper._get_latest_trade_date(trade_date)
        price_df = pro.daily(trade_date=latest_trade_date, ts_code=','.join(ts_codes))
        price_dict = dict(zip(price_df['ts_code'], price_df['close']))
        
        # 计算总减持金额
        total_amount = 0
        
        # 添加减持前10名
        report += "减持前10名:\n"
        for i, record in enumerate(records[:10], 1):
            company_name = company_dict.get(record['ts_code'], '未知公司')
            price = price_dict.get(record['ts_code'], 0)
            amount = record['change_vol'] * price / 10000  # 转换为万元
            total_amount += amount
            
            report += f"{i}. {company_name}({record['ts_code']}) "
            report += f"{record['holder_name']}({record['holder_type']}) "
            report += f"减持{record['change_vol']/10000:.2f}万股 "
            report += f"减持金额{amount/10000:.2f}亿元 "
            report += f"占流通股比例{record['change_ratio']:.2f}% "
            report += f"减持后持股{record['after_share']/10000:.2f}万股\n"
            
        report += f"\n今日总减持金额: {total_amount/10000:.2f}亿元\n"
        if latest_trade_date != trade_date:
            report += f"注：股价数据来自{latest_trade_date[:4]}-{latest_trade_date[4:6]}-{latest_trade_date[6:]}（最近交易日）\n"
            
        # 统计减持类型分布
        holder_types = {}
        for record in records:
            holder_type = record['holder_type']
            holder_types[holder_type] = holder_types.get(holder_type, 0) + 1
            
        report += "\n减持类型分布:\n"
        for holder_type, count in holder_types.items():
            type_name = {
                'C': '公司',
                'P': '个人',
                'G': '高管'
            }.get(holder_type, holder_type)
            report += f"{type_name}: {count}家\n"
            
        return report
