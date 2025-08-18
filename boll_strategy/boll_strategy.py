#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
布林线策略
策略逻辑：
- 突破上轨做多，回撤到中轨平多单
- 突破下轨做空，回撤到中轨平空单
- 硬止损：380元（可配置）
- 浮动止盈：盈利超过2个ATR后推保本，之后每盈利2个ATR推进1个ATR
- 开仓保护：开盘后15分钟、收盘前15分钟不开仓，止损后30分钟不开仓
"""

import os
import random
import sys
import time
from time import sleep

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import threading
import redis
import json
import logging

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import environment
from utils.logger_utils import Logger
from utils.wechat import send_message
from utils.trading_time_helper import TradingTimeHelper
from utils.date_utils import DateUtils
from xtquant import xtdata


class BollStrategyConfig:
    """布林线策略配置"""
    
    # 品种配置
    PRODUCT_TYPE = 'OI'  # 菜籽油
    PRODUCT_NAME = '菜籽油'
    CONTRACT_MULTIPLIER = 10  # 菜籽油一个点10元
    
    # 数据配置
    DATA_INTERVAL = 6  # 数据拉取间隔（秒）
    KLINE_PERIOD = '1min'  # 关注的K线周期
    WARMUP_PERIOD = 30  # 预热期（需要足够的数据计算指标）
    
    # 布林线参数
    BOLL_PERIOD = 26  # 布林线周期
    BOLL_STD = 2.0  # 标准差倍数
    
    # ATR参数
    ATR_PERIOD = 14  # ATR周期
    ATR_MULTIPLIER_FOR_PROFIT = 2.0  # 浮动止盈的ATR倍数
    
    # 风控参数
    HARD_STOP_LOSS = 380  # 硬止损金额（元）
    HARD_STOP_LOSS_POINTS = HARD_STOP_LOSS / CONTRACT_MULTIPLIER  # 转换为点数
    
    # 开仓保护时间（可根据需要调整，设为0可关闭对应保护）
    # 开盘后保护
    NO_OPEN_MINUTES_AFTER_MORNING_OPEN = 15  # 早盘09:00开盘后不开仓时间（分钟）
    NO_OPEN_MINUTES_AFTER_NIGHT_OPEN = 15  # 夜盘21:00开盘后不开仓时间（分钟）
    
    # 收盘前保护
    NO_OPEN_MINUTES_BEFORE_MORNING_BREAK = 1  # 早盘10:15休市前不开仓时间（分钟），设为1分钟
    NO_OPEN_MINUTES_BEFORE_MORNING_CLOSE = 15  # 早盘11:30收盘前不开仓时间（分钟）
    NO_OPEN_MINUTES_BEFORE_AFTERNOON_CLOSE = 15  # 午盘15:00收盘前不开仓时间（分钟）
    NO_OPEN_MINUTES_BEFORE_NIGHT_CLOSE = 15  # 夜盘23:00收盘前不开仓时间（分钟）
    
    # 止损后保护
    NO_OPEN_MINUTES_AFTER_LOSS = 30  # 止损后不开仓时间（分钟）
    
    # 强制平仓时间（收盘前强平，避免跳空风险）
    FORCE_CLOSE_TIMES = [
        (14, 58),  # 白天收盘前2分钟
        (22, 58),  # 晚上收盘前2分钟
    ]
    
    # 微信播报
    WECHAT_GROUP = "动力波策略群"
    
    # ==================== 绩效报告配置 ====================
    # 说明：策略会自动在报告时间前后保持短间隔轮询，确保不会错过报告时间
    
    # 日报配置
    DAILY_REPORT_TIME = (15, 0, 1)  # 日报时间 (小时, 开始分钟, 结束分钟)
    
    # 周报配置  
    WEEKLY_REPORT_TIME = (15, 5, 6)  # 周报时间 (小时, 开始分钟, 结束分钟)
    
    # 轮询策略配置
    # 在非交易时段，策略会智能调整轮询频率：
    # - 在报告时间前后自动使用短间隔轮询
    # - 其他时间使用长间隔轮询以节省资源
    SHORT_POLL_INTERVAL = 60      # 短间隔：60秒（用于报告时间附近）
    LONG_POLL_INTERVAL = 1800      # 长间隔：30分钟（用于其他非交易时段）
    REPORT_PREPARE_MINUTES = 5     # 报告前准备时间（提前5分钟开始短轮询）
    REPORT_CLEANUP_MINUTES = 5     # 报告后清理时间（延后5分钟结束短轮询）


class TradeRecord:
    """交易记录"""
    
    def __init__(self):
        self.entry_time = None  # 开仓时间
        self.exit_time = None  # 平仓时间
        self.entry_price = 0.0  # 开仓价格
        self.exit_price = 0.0  # 平仓价格
        self.direction = 0  # 1: 多仓, -1: 空仓
        self.profit = 0.0  # 盈亏金额
        self.exit_reason = ""  # 平仓原因


class Position:
    """持仓信息"""
    
    def __init__(self):
        self.direction = 0  # 0: 空仓, 1: 多仓, -1: 空仓
        self.entry_price = 0.0  # 开仓价格
        self.entry_time = None  # 开仓时间
        self.current_price = 0.0  # 当前价格
        self.stop_loss_price = 0.0  # 止损价格
        self.profit = 0.0  # 当前盈亏
        self.max_profit = 0.0  # 最大盈利
        self.atr_at_entry = 0.0  # 开仓时的ATR值
        self.breakeven_level = 0  # 保本级别（0: 未保本, 1+: 保本级别）
    
    def update_current_price(self, price):
        """更新当前价格和盈亏"""
        self.current_price = price
        if self.direction == 1:  # 多仓
            self.profit = (price - self.entry_price) * BollStrategyConfig.CONTRACT_MULTIPLIER
        elif self.direction == -1:  # 空仓
            self.profit = (self.entry_price - price) * BollStrategyConfig.CONTRACT_MULTIPLIER
        
        if self.profit > self.max_profit:
            self.max_profit = self.profit
    
    def is_empty(self):
        """是否空仓"""
        return self.direction == 0
    
    def is_long(self):
        """是否多仓"""
        return self.direction == 1
    
    def is_short(self):
        """是否空仓"""
        return self.direction == -1
    
    def clear(self):
        """清空持仓"""
        self.__init__()


class BollStrategy:
    """布林线策略主类"""
    
    def __init__(self):
        self.config = BollStrategyConfig()
        self.position = Position()
        self.data_buffer = pd.DataFrame()  # 数据缓冲区
        self.last_loss_time = None  # 上次止损时间
        self.is_running = False
        self.data_lock = threading.Lock()
        self.main_contract = None  # 主力合约代码
        self.trade_history = []  # 交易历史记录
        self.last_daily_report_date = None  # 上次日报日期
        self.last_weekly_report_date = None  # 上次周报日期
        
        # 初始化Redis缓存
        self.redis_client = redis.Redis(
            host=environment.REDIS_HOST,
            port=environment.REDIS_PORT,
            db=environment.REDIS_DB,
            password=environment.REDIS_PASSWORD,
            decode_responses=True
        )
        
        # 交易时间助手
        self.trading_helper = TradingTimeHelper(self.config.PRODUCT_TYPE)
        
        Logger.info(f"布林线策略初始化完成 - 品种: {self.config.PRODUCT_NAME}({self.config.PRODUCT_TYPE})")
    
    def is_option_contract(self, code):
        """判断是否为期权合约"""
        # 先去掉交易所后缀再判断
        code_without_exchange = code.split('.')[0] if '.' in code else code
        
        # 郑商所期权的识别规则：
        # 期货合约格式：OI509.ZF, OI601.ZF 等（OI + 月份）
        # 期权合约格式：OI509C9700.ZF, OI509P9700.ZF 等（包含C或P + 行权价）
        
        # 检查是否包含C或P（表示期权）
        # 注意：不是 -C- 或 -P-，而是直接的C或P后跟数字
        if len(code_without_exchange) > 5:  # 期权代码通常更长
            # 检查是否符合期权格式：品种代码+月份+C/P+行权价
            if 'C' in code_without_exchange[4:] or 'P' in code_without_exchange[4:]:
                # 确认C或P后面跟着数字（行权价）
                for i, char in enumerate(code_without_exchange):
                    if char in ['C', 'P'] and i > 3:  # 确保C/P不是品种代码的一部分
                        if i + 1 < len(code_without_exchange) and code_without_exchange[i + 1].isdigit():
                            return True
        
        return False
    
    def get_main_contract(self):
        """获取主力合约代码"""
        try:
            # 使用迅投市场代码ZF获取郑商所合约列表
            Logger.info("="*50)
            Logger.info("📋 开始获取主力合约...")
            Logger.info(f"品种: {self.config.PRODUCT_NAME}({self.config.PRODUCT_TYPE})")
            
            codes = xtdata.get_stock_list_in_sector("ZF")
            Logger.info(f"获取到郑商所合约总数: {len(codes)}个")
            
            # 过滤出菜籽油期货合约（排除期权）
            oi_futures = []
            oi_options = []
            seen_contracts = set()  # 用于去重
            
            for code in codes:
                if code.startswith("OI"):
                    if self.is_option_contract(code):
                        oi_options.append(code)
                        # Logger.debug(f"排除期权合约: {code}")  # 减少日志输出
                    else:
                        # 进一步过滤：只保留标准的期货合约格式
                        # 标准格式：OI + 3或4位数字 + .ZF
                        code_without_exchange = code.split('.')[0] if '.' in code else code
                        
                        # 过滤掉特殊合约（如OIL0, OIL1, OIL9等）
                        if not any(char.isalpha() for char in code_without_exchange[2:]):
                            # 确保是数字月份格式
                            if len(code_without_exchange) >= 4 and len(code_without_exchange) <= 6:
                                # 去重处理（有些合约可能重复）
                                if code not in seen_contracts:
                                    oi_futures.append(code)
                                    seen_contracts.add(code)
                                    Logger.debug(f"保留期货合约: {code}")
            
            Logger.info(f"菜籽油期货合约数: {len(oi_futures)}个, 期权合约数: {len(oi_options)}个")
            
            # 输出期货合约列表
            if oi_futures:
                Logger.info(f"期货合约代码: {', '.join(sorted(oi_futures)[:5])}...")  # 显示前5个
            
            if not oi_futures:
                Logger.error("未找到菜籽油期货合约")
                return None
            
            # 获取合约详情，选择主力合约（通常成交量最大）
            main_contract = None
            max_volume = 0
            contract_volumes = {}
            
            Logger.info("开始分析各合约成交量...")
            for contract in oi_futures:
                try:
                    # 获取实时行情数据来判断主力合约
                    tick_data = xtdata.get_full_tick([contract])
                    if tick_data and contract in tick_data:
                        volume = tick_data[contract].get('volume', 0)
                        contract_volumes[contract] = volume
                        Logger.debug(f"合约 {contract} 成交量: {volume}")
                        
                        if volume > max_volume:
                            max_volume = volume
                            main_contract = contract
                except Exception as e:
                    Logger.debug(f"获取合约{contract}行情失败: {e}")
                    continue
            
            # 输出成交量排名
            if contract_volumes:
                sorted_contracts = sorted(contract_volumes.items(), key=lambda x: x[1], reverse=True)
                Logger.info("📊 合约成交量排名:")
                for i, (contract, volume) in enumerate(sorted_contracts[:3], 1):
                    Logger.info(f"  第{i}名: {contract} 成交量={volume:,}")
            
            if main_contract:
                Logger.info(f"✅ 选定主力合约: {main_contract} (成交量: {max_volume:,})")
                Logger.info("="*50)
                self.main_contract = main_contract
                return main_contract
            else:
                # 如果无法获取成交量，根据月份选择（通常选择最近的活跃月份）
                # 郑商所菜籽油主力合约通常是1、5、9月
                current_date = datetime.now()
                current_year = current_date.year % 100  # 取年份后两位
                current_month = current_date.month
                
                # 主力合约月份
                main_months = [1, 5, 9]
                
                # 找到最近的主力合约月份
                best_contract = None
                for contract in oi_futures:
                    code_without_exchange = contract.split('.')[0] if '.' in contract else contract
                    # 尝试解析月份（如OI509中的09）
                    if len(code_without_exchange) >= 4:
                        try:
                            month_code = code_without_exchange[2:4]
                            month = int(month_code)
                            if month in [1, 5, 9]:  # 是主力合约月份
                                if best_contract is None:
                                    best_contract = contract
                                    Logger.debug(f"找到主力合约候选: {contract}")
                        except:
                            continue
                
                if best_contract:
                    main_contract = best_contract
                    Logger.warning(f"⚠️ 基于月份规则选择合约: {main_contract}")
                else:
                    main_contract = oi_futures[0]
                    Logger.warning(f"⚠️ 默认选择第一个合约: {main_contract}")
                
                return main_contract
            
        except Exception as e:
            Logger.error(f"获取主力合约失败: {e}")
            return None
    
    def _log_market_status(self, latest_data):
        """记录当前市场状态和布林线位置"""
        try:
            close = latest_data.get('close', 0)
            open_price = latest_data.get('open', 0)
            high = latest_data.get('high', 0)
            low = latest_data.get('low', 0)
            upper = latest_data.get('UPPER', 0)
            middle = latest_data.get('MIDDLE', 0)
            lower = latest_data.get('LOWER', 0)
            atr = latest_data.get('ATR', 0)
            
            # 计算收盘价在布林线中的位置
            position_pct = 0
            if upper > lower:
                position_pct = ((close - lower) / (upper - lower)) * 100
            
            # 判断K线颜色
            color = "红" if close >= open_price else "绿"
            
            # 获取时间信息
            time_str = latest_data.name.strftime('%H:%M:%S') if hasattr(latest_data.name, 'strftime') else str(latest_data.name)
            
            Logger.info(f"📈 [{time_str}] K线 - 开:{open_price:.0f} 高:{high:.0f} 低:{low:.0f} 收:{close:.0f} ({color})")
            Logger.info(f"📍 布林线 - 上轨:{upper:.2f} 中轨:{middle:.2f} 下轨:{lower:.2f}")
            Logger.info(f"📊 位置: {position_pct:.1f}% | ATR: {atr:.2f}点")
            
            # 判断当前位置状态
            if close > upper:
                Logger.info("⚠️ 当前价格突破上轨")
            elif close < lower:
                Logger.info("⚠️ 当前价格突破下轨")
            elif abs(close - middle) / middle < 0.001:
                Logger.info("📍 当前价格接近中轨")
                
        except Exception as e:
            Logger.debug(f"记录市场状态失败: {e}")
    
    def filter_trading_hours(self, df):
        """过滤非交易时间的数据"""
        if df.empty:
            return df
        
        # 菜籽油交易时间
        # 日盘: 09:00-10:15, 10:30-11:30, 13:30-15:00
        # 夜盘: 21:00-23:00
        
        filtered_rows = []
        for idx, row in df.iterrows():
            hour = idx.hour
            minute = idx.minute
            time_val = hour * 100 + minute
            
            # 检查是否在交易时间内
            if ((900 <= time_val <= 1015) or  # 早盘第一节
                (1030 <= time_val <= 1130) or  # 早盘第二节
                (1330 <= time_val <= 1500) or  # 午盘
                (2100 <= time_val <= 2300)):   # 夜盘
                filtered_rows.append(row)
        
        if filtered_rows:
            result_df = pd.DataFrame(filtered_rows)
            result_df.index = [row.name for row in filtered_rows]
            return result_df
        else:
            return pd.DataFrame()
    
    def calculate_indicators(self, df):
        """计算技术指标"""
        if len(df) < max(self.config.BOLL_PERIOD, self.config.ATR_PERIOD):
            Logger.debug(f"数据不足，需要{max(self.config.BOLL_PERIOD, self.config.ATR_PERIOD)}条，当前{len(df)}条")
            return df
        
        # 计算布林线
        df['MA'] = df['close'].rolling(window=self.config.BOLL_PERIOD).mean()
        df['STD'] = df['close'].rolling(window=self.config.BOLL_PERIOD).std()
        df['UPPER'] = df['MA'] + (df['STD'] * self.config.BOLL_STD)
        df['LOWER'] = df['MA'] - (df['STD'] * self.config.BOLL_STD)
        df['MIDDLE'] = df['MA']
        
        # 计算ATR
        df['TR'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['ATR'] = df['TR'].rolling(window=self.config.ATR_PERIOD).mean()
        
        return df
    
    def can_open_position(self, current_time):
        """判断是否允许开仓"""
        # 如果已有持仓，不允许开新仓
        if not self.position.is_empty():
            return False, "已有持仓"
        
        # 检查止损后的保护时间
        if self.last_loss_time:
            time_since_loss = (current_time - self.last_loss_time).total_seconds() / 60
            if time_since_loss < self.config.NO_OPEN_MINUTES_AFTER_LOSS:
                return False, f"止损后保护期，剩余{self.config.NO_OPEN_MINUTES_AFTER_LOSS - time_since_loss:.1f}分钟"
        
        # 检查交易时间
        trading_hours = self.trading_helper.trading_time()
        if not trading_hours:
            return False, "非交易时间"
        
        # 检查开盘后和收盘前的保护时间
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # 菜籽油交易时间段
        # 日盘: 09:00-10:15, 10:30-11:30, 13:30-15:00
        # 夜盘: 21:00-23:00
        
        # 构造时间值用于比较
        time_val = current_hour * 100 + current_minute
        
        # 开盘后保护（可通过配置关闭）
        # 早盘09:00开盘后保护
        if self.config.NO_OPEN_MINUTES_AFTER_MORNING_OPEN > 0:
            if 900 <= time_val < (900 + self.config.NO_OPEN_MINUTES_AFTER_MORNING_OPEN):
                minutes_left = 900 + self.config.NO_OPEN_MINUTES_AFTER_MORNING_OPEN - time_val
                return False, f"早盘开盘后保护期，剩余{minutes_left}分钟"
        
        # 夜盘21:00开盘后保护
        if self.config.NO_OPEN_MINUTES_AFTER_NIGHT_OPEN > 0:
            if 2100 <= time_val < (2100 + self.config.NO_OPEN_MINUTES_AFTER_NIGHT_OPEN):
                minutes_left = 2100 + self.config.NO_OPEN_MINUTES_AFTER_NIGHT_OPEN - time_val
                return False, f"夜盘开盘后保护期，剩余{minutes_left}分钟"
        
        # 收盘前保护（可通过配置关闭）
        # 早盘10:15休市前保护（短时间保护）
        if self.config.NO_OPEN_MINUTES_BEFORE_MORNING_BREAK > 0:
            # 10:15 = 10*60+15 = 615分钟，减去保护时间
            protection_start = datetime(current_time.year, current_time.month, current_time.day, 10, 15) - timedelta(minutes=self.config.NO_OPEN_MINUTES_BEFORE_MORNING_BREAK)
            protection_start_val = protection_start.hour * 100 + protection_start.minute
            if protection_start_val <= time_val <= 1015:
                return False, f"早盘休市前{self.config.NO_OPEN_MINUTES_BEFORE_MORNING_BREAK}分钟保护期"
        
        # 早盘11:30收盘前保护
        if self.config.NO_OPEN_MINUTES_BEFORE_MORNING_CLOSE > 0:
            protection_start = datetime(current_time.year, current_time.month, current_time.day, 11, 30) - timedelta(minutes=self.config.NO_OPEN_MINUTES_BEFORE_MORNING_CLOSE)
            protection_start_val = protection_start.hour * 100 + protection_start.minute
            if protection_start_val <= time_val <= 1130:
                return False, f"早盘收盘前{self.config.NO_OPEN_MINUTES_BEFORE_MORNING_CLOSE}分钟保护期"
        
        # 午盘15:00收盘前保护
        if self.config.NO_OPEN_MINUTES_BEFORE_AFTERNOON_CLOSE > 0:
            protection_start = datetime(current_time.year, current_time.month, current_time.day, 15, 0) - timedelta(minutes=self.config.NO_OPEN_MINUTES_BEFORE_AFTERNOON_CLOSE)
            protection_start_val = protection_start.hour * 100 + protection_start.minute
            if protection_start_val <= time_val <= 1500:
                return False, f"午盘收盘前{self.config.NO_OPEN_MINUTES_BEFORE_AFTERNOON_CLOSE}分钟保护期"
        
        # 夜盘23:00收盘前保护
        if self.config.NO_OPEN_MINUTES_BEFORE_NIGHT_CLOSE > 0:
            protection_start = datetime(current_time.year, current_time.month, current_time.day, 23, 0) - timedelta(minutes=self.config.NO_OPEN_MINUTES_BEFORE_NIGHT_CLOSE)
            protection_start_val = protection_start.hour * 100 + protection_start.minute
            if protection_start_val <= time_val <= 2300:
                return False, f"夜盘收盘前{self.config.NO_OPEN_MINUTES_BEFORE_NIGHT_CLOSE}分钟保护期"
        
        return True, "允许开仓"
    
    def check_open_signal(self, df):
        """检查开仓信号"""
        if len(df) < 2:
            return None, None
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # 突破上轨做多
        if (previous['close'] <= previous['UPPER'] and 
            current['close'] > current['UPPER']):
            return 1, f"突破上轨：{current['UPPER']:.2f}"
        
        # 突破下轨做空
        if (previous['close'] >= previous['LOWER'] and 
            current['close'] < current['LOWER']):
            return -1, f"突破下轨：{current['LOWER']:.2f}"
        
        return None, None
    
    def check_close_signal(self, df):
        """检查平仓信号"""
        if len(df) < 1 or self.position.is_empty():
            return False, None
        
        current = df.iloc[-1]
        
        # 多仓回撤到中轨平仓
        if self.position.is_long() and current['close'] <= current['MIDDLE']:
            return True, f"多仓回撤到中轨：{current['MIDDLE']:.2f}"
        
        # 空仓回撤到中轨平仓
        if self.position.is_short() and current['close'] >= current['MIDDLE']:
            return True, f"空仓回撤到中轨：{current['MIDDLE']:.2f}"
        
        return False, None
    
    def check_stop_loss(self, current_price):
        """检查止损"""
        if self.position.is_empty():
            return False, None
        
        # 先检查浮动止损（保本止损优先）
        if self.position.stop_loss_price > 0:
            if ((self.position.is_long() and current_price <= self.position.stop_loss_price) or
                (self.position.is_short() and current_price >= self.position.stop_loss_price)):
                # 如果是保本止损，不算亏损
                if self.position.breakeven_level > 0:
                    return True, f"保本止损，止损价{self.position.stop_loss_price:.2f}"
                else:
                    return True, f"浮动止损，止损价{self.position.stop_loss_price:.2f}"
        
        # 再检查硬止损（只有在没有推保本的情况下才会硬止损）
        if self.position.breakeven_level == 0 and self.position.profit < 0 and abs(self.position.profit) >= self.config.HARD_STOP_LOSS:
            return True, f"硬止损，亏损{abs(self.position.profit):.2f}元"
        
        return False, None
    
    def update_trailing_stop(self, df):
        """更新浮动止盈"""
        if self.position.is_empty() or len(df) < 1:
            return
        
        current = df.iloc[-1]
        current_atr = current.get('ATR', self.position.atr_at_entry)
        
        if current_atr <= 0:
            current_atr = self.position.atr_at_entry
            
        # ATR以点数计算，转换为金额
        atr_points = current_atr
        atr_money = atr_points * self.config.CONTRACT_MULTIPLIER
        
        # 盈利超过2个ATR后开始推保本
        atr_threshold = self.config.ATR_MULTIPLIER_FOR_PROFIT * atr_money
        
        if self.position.profit > atr_threshold and self.position.breakeven_level == 0:
            # 推保本
            self.position.breakeven_level = 1
            if self.position.is_long():
                self.position.stop_loss_price = self.position.entry_price
            else:
                self.position.stop_loss_price = self.position.entry_price
            
            # 格式化时间，去掉微秒
            time_str = current.name.strftime('%Y-%m-%d %H:%M:%S') if hasattr(current.name, 'strftime') else str(current.name)
            message = f"【布林线策略信号播报】\n品种：{self.config.PRODUCT_NAME}  周期：{self.config.KLINE_PERIOD}  时间：{time_str}\n开仓价格：{self.position.entry_price:.2f}，ATR：{atr_points:.2f}，当前价格：{current['close']:.2f}\n盈利超过 2 个ATR，推保本，恭喜这单不会亏钱了。"
            send_message(message, self.config.WECHAT_GROUP)
            Logger.info(f"✋ 推保本 - 盈利{self.position.profit:.2f}元 > {atr_threshold:.2f}元(2个ATR)")
            
            # 保存到Redis
            self._save_position_to_redis()
        
        # 每盈利2个ATR，止盈推进1个ATR
        elif self.position.profit > atr_threshold * (self.position.breakeven_level + 1):
            self.position.breakeven_level += 1
            
            if self.position.is_long():
                self.position.stop_loss_price = self.position.entry_price + atr_points * (self.position.breakeven_level - 1)
            else:
                self.position.stop_loss_price = self.position.entry_price - atr_points * (self.position.breakeven_level - 1)
            
            Logger.info(f"📈 浮动止盈更新 - 级别: {self.position.breakeven_level}, 止损价: {self.position.stop_loss_price:.2f}, 盈利: {self.position.profit:.2f}元")
            
            # 保存到Redis
            self._save_position_to_redis()
    
    def open_position(self, direction, price, reason, current_time, atr_value, current_data=None):
        """开仓"""
        self.position.direction = direction
        self.position.entry_price = price
        self.position.entry_time = current_time
        self.position.current_price = price
        self.position.atr_at_entry = atr_value
        
        direction_text = "多" if direction == 1 else "空"
        
        # 格式化时间，去掉微秒
        time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 构建播报消息（根据需求文档的格式）
        message_lines = [
            "【布林线策略信号播报】",
            f"品种：{self.config.PRODUCT_TYPE}（{self.config.PRODUCT_NAME}） 周期：{self.config.KLINE_PERIOD} 时间：{time_str}"
        ]
        
        # 添加布林线信息
        if current_data is not None:
            upper = current_data.get('UPPER', 0)
            lower = current_data.get('LOWER', 0)
            if direction == 1:  # 做多
                message_lines.append(f"上轨：{upper:.0f} ，当前价格：{price:.0f}，突破上轨：满足")
            else:  # 做空
                message_lines.append(f"下轨：{lower:.0f} ，当前价格：{price:.0f}，突破下轨：满足")
        else:
            message_lines.append(reason)
        
        message_lines.append(f"满足开仓条件，开仓方向：{direction_text}")
        message_lines.append(f"开仓价格：{price:.1f}")
        
        message = "\n".join(message_lines)
        
        send_message(message, self.config.WECHAT_GROUP)
        Logger.info(f"开仓 - 方向: {direction_text}, 价格: {price:.2f}, 原因: {reason}")
        
        # 保存到Redis
        self._save_position_to_redis()
    
    def close_position(self, price, reason, current_time):
        """平仓"""
        if self.position.is_empty():
            return
        
        self.position.update_current_price(price)
        profit = self.position.profit
        
        # 记录交易
        trade = TradeRecord()
        trade.entry_time = self.position.entry_time
        trade.exit_time = current_time
        trade.entry_price = self.position.entry_price
        trade.exit_price = price
        trade.direction = self.position.direction
        trade.profit = profit
        trade.exit_reason = reason
        self.trade_history.append(trade)
        
        # 保存交易历史到Redis
        self._save_trade_history_to_redis()
        
        direction_text = "多" if self.position.is_long() else "空"
        
        # 如果是止损，记录时间
        if "止损" in reason:
            self.last_loss_time = current_time
        
        # 格式化时间，去掉微秒
        time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 修正盈亏描述
        if profit >= 0:
            profit_desc = f"盈利{abs(profit):.2f}元"
        else:
            profit_desc = f"亏损{abs(profit):.2f}元"
        
        # 构建平仓消息
        if "止损" in reason:
            # 止损播报
            message_lines = [
                "【布林线策略信号播报】",
                f"品种：{self.config.PRODUCT_TYPE}（{self.config.PRODUCT_NAME}）  周期：{self.config.KLINE_PERIOD}  时间：{time_str}",
                f"开仓价格：{self.position.entry_price:.0f}，当前价格：{price:.0f}",
                f"触发{reason}，立刻平仓，本单{profit_desc}"
            ]
        elif "强制平仓" in reason or "收盘" in reason:
            # 强制平仓播报
            message_lines = [
                "【布林线策略信号播报】",
                f"品种：{self.config.PRODUCT_TYPE}（{self.config.PRODUCT_NAME}）  周期：{self.config.KLINE_PERIOD}  时间：{time_str}",
                f"开仓价格：{self.position.entry_price:.0f}，当前价格：{price:.0f}，方向：{direction_text}",
                f"{reason}，本单{profit_desc}。"
            ]
        else:
            # 正常平仓播报
            message_lines = [
                "【布林线策略信号播报】",
                f"品种：{self.config.PRODUCT_TYPE}（{self.config.PRODUCT_NAME}）  周期：{self.config.KLINE_PERIOD}  时间：{time_str}",
                f"开仓价格：{self.position.entry_price:.0f}，当前价格：{price:.0f}，方向：{direction_text}",
                f"{reason}，本单{profit_desc}。"
            ]
        
        message = "\n".join(message_lines)
        
        send_message(message, self.config.WECHAT_GROUP)
        Logger.info(f"平仓 - {direction_text}仓, 价格: {price:.2f}, 盈亏: {profit:.2f}, 原因: {reason}")
        
        # 清空持仓
        self.position.clear()
        
        # 清除Redis缓存
        self._clear_position_from_redis()
    
    def _save_position_to_redis(self):
        """保存持仓到Redis"""
        try:
            position_data = {
                'direction': self.position.direction,
                'entry_price': self.position.entry_price,
                'entry_time': self.position.entry_time.isoformat() if self.position.entry_time else None,
                'current_price': self.position.current_price,
                'stop_loss_price': self.position.stop_loss_price,
                'atr_at_entry': self.position.atr_at_entry,
                'breakeven_level': self.position.breakeven_level,
                'max_profit': self.position.max_profit,
                'main_contract': self.main_contract
            }
            # 保存时间设为24小时，确保隔夜后也能恢复
            self.redis_client.setex('boll_strategy_position', 86400, json.dumps(position_data))
            Logger.debug("持仓信息已保存到Redis")
        except Exception as e:
            Logger.error(f"保存持仓到Redis失败: {e}")
    
    def _load_position_from_redis(self):
        """从Redis加载持仓"""
        try:
            data = self.redis_client.get('boll_strategy_position')
            if data:
                position_data = json.loads(data)
                self.position.direction = position_data.get('direction', 0)
                self.position.entry_price = position_data.get('entry_price', 0.0)
                if position_data.get('entry_time'):
                    self.position.entry_time = datetime.fromisoformat(position_data['entry_time'])
                self.position.current_price = position_data.get('current_price', 0.0)
                self.position.stop_loss_price = position_data.get('stop_loss_price', 0.0)
                self.position.atr_at_entry = position_data.get('atr_at_entry', 0.0)
                self.position.breakeven_level = position_data.get('breakeven_level', 0)
                self.position.max_profit = position_data.get('max_profit', 0.0)
                
                # 恢复主力合约
                if 'main_contract' in position_data:
                    self.main_contract = position_data['main_contract']
                
                # 如果恢复了持仓，输出详细信息
                if self.position.direction != 0:
                    direction_text = "多" if self.position.direction == 1 else "空"
                    Logger.info("="*50)
                    Logger.info("🔄 检测到未平仓持仓，正在恢复...")
                    Logger.info(f"  持仓方向: {direction_text}单")
                    Logger.info(f"  开仓价格: {self.position.entry_price:.0f}")
                    Logger.info(f"  上次价格: {self.position.current_price:.0f}")
                    Logger.info(f"  止损价格: {self.position.stop_loss_price:.0f if self.position.stop_loss_price > 0 else '未设置'}")
                    Logger.info(f"  保本状态: {'[已保本]' if self.position.breakeven_level > 0 else '[未保本]'}")
                    Logger.info(f"  最大盈利: {self.position.max_profit:.0f}元")
                    if self.position.entry_time:
                        Logger.info(f"  开仓时间: {self.position.entry_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    Logger.info("="*50)
                    
                    # 发送恢复通知到微信
                    recovery_msg = (
                        f"【策略恢复通知】\n"
                        f"布林线策略重启成功\n"
                        f"检测到未平仓的{direction_text}单\n"
                        f"开仓价格：{self.position.entry_price:.0f}\n"
                        f"当前止损价：{self.position.stop_loss_price:.0f if self.position.stop_loss_price > 0 else '无'}\n"
                        f"保本状态：{'已保本' if self.position.breakeven_level > 0 else '未保本'}\n"
                        f"最大盈利：{self.position.max_profit:.0f}元\n"
                        f"继续监控中..."
                    )
                    try:
                        send_message(recovery_msg, self.config.WECHAT_GROUP)
                    except Exception as e:
                        Logger.warning(f"发送恢复通知失败: {e}")
                else:
                    Logger.info("从Redis加载配置，无持仓")
        except Exception as e:
            Logger.error(f"从Redis加载持仓失败: {e}")
    
    def _clear_position_from_redis(self):
        """清除Redis中的持仓信息"""
        try:
            self.redis_client.delete('boll_strategy_position')
        except Exception as e:
            Logger.error(f"清除Redis持仓信息失败: {e}")
    
    def _save_trade_history_to_redis(self):
        """保存交易历史到Redis"""
        try:
            # 只保存最近100条交易记录
            recent_trades = self.trade_history[-100:] if len(self.trade_history) > 100 else self.trade_history
            
            trade_data = []
            for trade in recent_trades:
                trade_data.append({
                    'entry_time': trade.entry_time.isoformat() if trade.entry_time else None,
                    'exit_time': trade.exit_time.isoformat() if trade.exit_time else None,
                    'entry_price': trade.entry_price,
                    'exit_price': trade.exit_price,
                    'direction': trade.direction,
                    'profit': trade.profit,
                    'exit_reason': trade.exit_reason
                })
            
            # 保存7天
            self.redis_client.setex('boll_strategy_trade_history', 604800, json.dumps(trade_data))
            Logger.debug(f"交易历史已保存到Redis，共{len(trade_data)}条记录")
        except Exception as e:
            Logger.error(f"保存交易历史到Redis失败: {e}")
    
    def _load_trade_history_from_redis(self):
        """从Redis加载交易历史"""
        try:
            data = self.redis_client.get('boll_strategy_trade_history')
            if data:
                trade_data = json.loads(data)
                self.trade_history = []
                
                for td in trade_data:
                    trade = TradeRecord()
                    if td.get('entry_time'):
                        trade.entry_time = datetime.fromisoformat(td['entry_time'])
                    if td.get('exit_time'):
                        trade.exit_time = datetime.fromisoformat(td['exit_time'])
                    trade.entry_price = td.get('entry_price', 0.0)
                    trade.exit_price = td.get('exit_price', 0.0)
                    trade.direction = td.get('direction', 0)
                    trade.profit = td.get('profit', 0.0)
                    trade.exit_reason = td.get('exit_reason', '')
                    self.trade_history.append(trade)
                
                Logger.info(f"从Redis加载了{len(self.trade_history)}条交易记录")
        except Exception as e:
            Logger.error(f"从Redis加载交易历史失败: {e}")
    
    def generate_daily_report(self, current_time):
        """生成日报"""
        try:
            # 获取今天的交易（包括昨晚21:00到今天15:00）
            today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_night_start = (today_start - timedelta(days=1)).replace(hour=21, minute=0, second=0)
            
            # 筛选时间范围内的交易
            daily_trades = []
            for trade in self.trade_history:
                if trade.exit_time and yesterday_night_start <= trade.exit_time <= current_time:
                    daily_trades.append(trade)
            
            if not daily_trades:
                # 没有交易也要播报
                message_lines = [
                    "【布林线策略每日战绩播报】",
                    f"品种：{self.config.PRODUCT_TYPE}（{self.config.PRODUCT_NAME}） 时间：{current_time.strftime('%Y-%m-%d')}（昨天21:00-今天15:00）",
                    "今日无交易"
                ]
            else:
                # 统计盈亏
                profit_trades = [t for t in daily_trades if t.profit > 0]
                loss_trades = [t for t in daily_trades if t.profit <= 0]
                
                profit_count = len(profit_trades)
                loss_count = len(loss_trades)
                
                max_profit = max([t.profit for t in profit_trades]) if profit_trades else 0
                max_loss = min([t.profit for t in loss_trades]) if loss_trades else 0
                
                total_profit = sum([t.profit for t in daily_trades])
                
                message_lines = [
                    "【布林线策略每日战绩播报】",
                    f"品种：{self.config.PRODUCT_TYPE}（{self.config.PRODUCT_NAME}） 时间：{current_time.strftime('%Y-%m-%d')}（昨天21:00-今天15:00）"
                ]
                
                profit_loss_line = ""
                if profit_count > 0:
                    profit_loss_line += f"盈利 {profit_count} 笔，单笔最大盈利 {max_profit:.0f} 元"
                if loss_count > 0:
                    if profit_count > 0:
                        profit_loss_line += f"；亏损 {loss_count} 笔，单笔最大亏损 {max_loss:.0f} 元"
                    else:
                        profit_loss_line += f"亏损 {loss_count} 笔，单笔最大亏损 {max_loss:.0f} 元"
                
                if profit_loss_line:
                    message_lines.append(profit_loss_line)
                
                if total_profit >= 0:
                    message_lines.append(f"总盈利 {total_profit:.0f} 元")
                else:
                    message_lines.append(f"总亏损 {abs(total_profit):.0f} 元")
            
            message = "\n".join(message_lines)
            send_message(message, self.config.WECHAT_GROUP)
            Logger.info(f"📊 日报已发送 - 交易数: {len(daily_trades)}")
            
            # 记录发送时间
            self.last_daily_report_date = current_time.date()
            
        except Exception as e:
            Logger.error(f"生成日报失败: {e}")
    
    def generate_weekly_report(self, current_time):
        """生成周报"""
        try:
            # 获取本周的交易（包括上周五21:00到本周五15:00）
            # 找到本周一
            days_since_monday = current_time.weekday()
            monday = current_time - timedelta(days=days_since_monday)
            monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # 上周五21:00
            last_friday_night = monday - timedelta(days=3)
            last_friday_night = last_friday_night.replace(hour=21, minute=0, second=0)
            
            # 筛选时间范围内的交易
            weekly_trades = []
            for trade in self.trade_history:
                if trade.exit_time and last_friday_night <= trade.exit_time <= current_time:
                    weekly_trades.append(trade)
            
            if not weekly_trades:
                # 没有交易也要播报
                message_lines = [
                    "【布林线策略每周战绩播报】",
                    f"品种：{self.config.PRODUCT_TYPE}（{self.config.PRODUCT_NAME}） 时间：{last_friday_night.strftime('%Y-%m-%d')} 至 {current_time.strftime('%Y-%m-%d')}",
                    "本周无交易"
                ]
            else:
                # 统计盈亏
                profit_trades = [t for t in weekly_trades if t.profit > 0]
                loss_trades = [t for t in weekly_trades if t.profit <= 0]
                
                profit_count = len(profit_trades)
                loss_count = len(loss_trades)
                
                max_profit = max([t.profit for t in profit_trades]) if profit_trades else 0
                max_loss = min([t.profit for t in loss_trades]) if loss_trades else 0
                
                total_profit = sum([t.profit for t in weekly_trades])
                
                message_lines = [
                    "【布林线策略每周战绩播报】",
                    f"品种：{self.config.PRODUCT_TYPE}（{self.config.PRODUCT_NAME}） 时间：{last_friday_night.strftime('%Y-%m-%d')} 至 {current_time.strftime('%Y-%m-%d')}"
                ]
                
                profit_loss_line = ""
                if profit_count > 0:
                    profit_loss_line += f"盈利 {profit_count} 笔，单笔最大盈利 {max_profit:.0f} 元"
                if loss_count > 0:
                    if profit_count > 0:
                        profit_loss_line += f"；亏损 {loss_count} 笔，单笔最大亏损 {max_loss:.0f} 元"
                    else:
                        profit_loss_line += f"亏损 {loss_count} 笔，单笔最大亏损 {max_loss:.0f} 元"
                
                if profit_loss_line:
                    message_lines.append(profit_loss_line)
                
                if total_profit >= 0:
                    message_lines.append(f"总盈利 {total_profit:.0f} 元")
                else:
                    message_lines.append(f"总亏损 {abs(total_profit):.0f} 元")
            
            message = "\n".join(message_lines)
            send_message(message, self.config.WECHAT_GROUP)
            Logger.info(f"📊 周报已发送 - 交易数: {len(weekly_trades)}")
            
            # 记录发送时间
            self.last_weekly_report_date = current_time.date()
            
        except Exception as e:
            Logger.error(f"生成周报失败: {e}")
    
    def check_performance_report(self, current_time):
        """检查是否需要发送绩效报告"""
        try:
            # 检查日报（根据配置的时间触发）
            daily_hour, daily_min_start, daily_min_end = BollStrategyConfig.DAILY_REPORT_TIME
            if (current_time.hour == daily_hour and daily_min_start <= current_time.minute <= daily_min_end and 
                (self.last_daily_report_date is None or self.last_daily_report_date < current_time.date())):
                Logger.info(f"触发日报生成 - 时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                self.generate_daily_report(current_time)
            
            # 检查周报（根据配置的时间触发）
            weekly_hour, weekly_min_start, weekly_min_end = BollStrategyConfig.WEEKLY_REPORT_TIME
            if (current_time.weekday() == 4 and  # 周五
                current_time.hour == weekly_hour and weekly_min_start <= current_time.minute <= weekly_min_end and
                (self.last_weekly_report_date is None or self.last_weekly_report_date < current_time.date())):
                Logger.info(f"触发周报生成 - 时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                self.generate_weekly_report(current_time)
        
        except Exception as e:
            Logger.error(f"检查绩效报告失败: {e}")

    
    def fetch_kline_data(self, contract_code):
        """获取1分钟K线数据用于信号判断"""
        try:
            # 获取1分钟K线数据
            end_time = datetime.now()
            
            # 根据当前时间判断需要获取多长时间的数据
            current_hour = end_time.hour
            
            # 如果是早盘开始（9点左右），需要获取昨天夜盘的数据
            if 9 <= current_hour <= 10:
                # 获取包括昨天夜盘的数据（约12小时）
                start_time = end_time - timedelta(hours=12)
            # 如果是午后或夜盘，获取当天的数据
            else:
                # 获取近8小时的数据，确保覆盖完整交易时段
                start_time = end_time - timedelta(hours=8)
            
            Logger.debug(f"获取K线数据: {contract_code}, 时间范围: {start_time.strftime('%Y-%m-%d %H:%M:%S')} - {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 使用 get_market_data_ex 获取期货数据（文档推荐）
            data_dict = xtdata.get_market_data_ex(
                stock_list=[contract_code],
                period='1m',
                start_time=start_time.strftime('%Y%m%d%H%M%S'),
                end_time=end_time.strftime('%Y%m%d%H%M%S'),
                dividend_type='none'
            )
            
            if data_dict is None or not data_dict:
                Logger.warning("get_market_data_ex未获取到数据，尝试使用get_market_data")
                
                # 尝试使用get_market_data作为备选方案
                df = xtdata.get_market_data(
                    stock_list=[contract_code],
                    period='1m',
                    start_time=start_time.strftime('%Y%m%d%H%M%S'),
                    end_time=end_time.strftime('%Y%m%d%H%M%S')
                )
                
                if df is not None:
                    # 检查df的类型
                    if isinstance(df, dict):
                        # 如果返回的是字典，尝试提取数据
                        if contract_code in df:
                            df = df[contract_code]
                        else:
                            Logger.warning("get_market_data返回字典但没有找到合约数据")
                            return None
                    
                    # 确保df是DataFrame
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        Logger.info(f"使用get_market_data获取到数据，行数: {len(df)}")
                        
                        # 重命名列以匹配预期格式
                        if 'volume' in df.columns:
                            df = df.rename(columns={'volume': 'vol'})
                        
                        # 计算技术指标
                        df = self.calculate_indicators(df)
                        
                        Logger.debug(f"获取到K线数据，行数: {len(df)}, 最新时间: {df.index[-1] if not df.empty else 'N/A'}")
                        return df
                    else:
                        Logger.warning("get_market_data未返回有效数据")
                        return None
                else:
                    Logger.warning("两种方法都未获取到K线数据")
                    return None
            
            # 从字典中提取数据并转换为DataFrame
            if contract_code in data_dict:
                market_data = data_dict[contract_code]
                
                # 创建DataFrame
                df = pd.DataFrame({
                    'time': market_data.get('time', []),
                    'open': market_data.get('open', []),
                    'high': market_data.get('high', []),
                    'low': market_data.get('low', []),
                    'close': market_data.get('close', []),
                    'volume': market_data.get('volume', []),
                    'amount': market_data.get('amount', [])
                })
                
                if df.empty:
                    Logger.warning("K线数据为空，尝试使用get_market_data")
                    
                    # 尝试使用get_market_data作为备选方案
                    df = xtdata.get_market_data(
                        stock_list=[contract_code],
                        period='1m',
                        start_time=start_time.strftime('%Y%m%d%H%M%S'),
                        end_time=end_time.strftime('%Y%m%d%H%M%S')
                    )
                    
                    if df is not None:
                        # 检查df的类型
                        if isinstance(df, dict):
                            # 如果返回的是字典，尝试提取数据
                            if contract_code in df:
                                df = df[contract_code]
                            else:
                                Logger.warning("get_market_data返回字典但没有找到合约数据")
                                return None
                        
                        # 确保df是DataFrame
                        if isinstance(df, pd.DataFrame) and not df.empty:
                            Logger.info(f"使用get_market_data获取到数据，行数: {len(df)}")
                            
                            # 重命名列以匹配预期格式
                            if 'volume' in df.columns:
                                df = df.rename(columns={'volume': 'vol'})
                        
                            # 计算技术指标
                            df = self.calculate_indicators(df)
                            return df
                        else:
                            return None
                
                # 设置时间索引
                # 处理时间戳，迅投返回的是毫秒时间戳
                # 注意：迅投返回的时间戳是UTC时间，需要转换为北京时间（UTC+8）
                df['time'] = pd.to_datetime(df['time'], unit='ms')
                
                # 简单方法：直接加8小时转换为北京时间
                df['time'] = df['time'] + pd.Timedelta(hours=8)
                
                df.set_index('time', inplace=True)
                
                # 过滤掉非交易时间的数据
                df = self.filter_trading_hours(df)
                
                # 重命名列
                df = df.rename(columns={'volume': 'vol'})
                
                
                # 计算技术指标
                df = self.calculate_indicators(df)
                
                if not df.empty:
                    latest = df.iloc[-1]
                    Logger.debug(f"获取到K线数据，行数: {len(df)}, 最新时间: {df.index[-1].strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # 输出最新K线和布林线信息
                    if 'UPPER' in df.columns and 'LOWER' in df.columns and 'MIDDLE' in df.columns:
                        self._log_market_status(latest)
                else:
                    Logger.warning("获取到的K线数据为空")
                
                return df
            else:
                Logger.warning(f"数据中未找到合约 {contract_code}，尝试使用get_market_data")
                
                # 尝试使用get_market_data作为备选方案
                df = xtdata.get_market_data(
                    stock_list=[contract_code],
                    period='1m',
                    start_time=start_time.strftime('%Y%m%d%H%M%S'),
                    end_time=end_time.strftime('%Y%m%d%H%M%S')
                )
                
                if df is not None:
                    # 检查df的类型
                    if isinstance(df, dict):
                        # 如果返回的是字典，尝试提取数据
                        if contract_code in df:
                            df = df[contract_code]
                        else:
                            Logger.warning("get_market_data返回字典但没有找到合约数据")
                            return None
                    
                    # 确保df是DataFrame
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        Logger.info(f"使用get_market_data获取到数据，行数: {len(df)}")
                        
                        # 重命名列以匹配预期格式
                        if 'volume' in df.columns:
                            df = df.rename(columns={'volume': 'vol'})
                        
                            # 计算技术指标
                            df = self.calculate_indicators(df)
                            return df
                        else:
                            return None
                else:
                    return None
            
        except Exception as e:
            Logger.error(f"获取K线数据失败: {e}")
            import traceback
            Logger.error(f"错误堆栈: {traceback.format_exc()}")
            return None
    
    def get_current_price(self, contract_code):
        """获取当前实时价格用于止损监控"""
        try:
            # 获取实时tick数据
            tick_data = xtdata.get_full_tick([contract_code])
            if tick_data and contract_code in tick_data:
                current_price = tick_data[contract_code].get('lastPrice', 0)
                if current_price > 0:
                    return current_price
            
            # 如果tick数据获取失败，尝试获取最新的分钟线收盘价
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=5)
            
            df = xtdata.get_market_data(
                stock_list=[contract_code],
                period='1m',
                start_time=start_time.strftime('%Y%m%d%H%M%S'),
                end_time=end_time.strftime('%Y%m%d%H%M%S')
            )
            
            if df is not None:
                # 检查df的类型
                if isinstance(df, dict):
                    # 如果返回的是字典，尝试提取数据
                    if contract_code in df:
                        df = df[contract_code]
                    else:
                        return None
                
                # 确保df是DataFrame
                if isinstance(df, pd.DataFrame) and not df.empty:
                    return df['close'].iloc[-1]
                else:
                    return None
            
            return None
            
        except Exception as e:
            Logger.error(f"获取当前价格失败: {e}")
            return None
    
    def check_force_close(self, current_time):
        """检查是否需要强制平仓（收盘前）"""
        if self.position.is_empty():
            return False, None
        
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # 检查是否到了强制平仓时间
        for force_hour, force_minute in self.config.FORCE_CLOSE_TIMES:
            if current_hour == force_hour and current_minute == force_minute:
                return True, "快收盘啦！强制平仓了"
        
        return False, None
    
    def check_stop_loss_with_realtime_price(self, contract_code):
        """使用实时价格检查止损"""
        if self.position.is_empty():
            return False, None
        
        # 获取实时价格
        current_price = self.get_current_price(contract_code)
        if current_price is None:
            Logger.warning("无法获取实时价格，跳过止损检查")
            return False, None
        
        # 更新持仓当前价格和盈亏
        self.position.update_current_price(current_price)
        
        # 先检查浮动止损（保本止损优先）
        if self.position.stop_loss_price > 0:
            if ((self.position.is_long() and current_price <= self.position.stop_loss_price) or
                (self.position.is_short() and current_price >= self.position.stop_loss_price)):
                # 如果是保本止损，不算亏损
                if self.position.breakeven_level > 0:
                    return True, f"保本止损，止损价{self.position.stop_loss_price:.2f}"
                else:
                    return True, f"浮动止损，止损价{self.position.stop_loss_price:.2f}"
        
        # 再检查硬止损（只有在没有推保本的情况下才会硬止损）
        if self.position.breakeven_level == 0 and self.position.profit < 0 and abs(self.position.profit) >= self.config.HARD_STOP_LOSS:
            return True, f"硬止损，亏损{abs(self.position.profit):.2f}元"
        
        return False, None
    
    def check_signals_with_kline(self, contract_code):
        """使用K线数据检查开仓和平仓信号"""
        # 获取1分钟K线数据
        df = self.fetch_kline_data(contract_code)
        
        if df is None:
            Logger.debug("未获取到K线数据，跳过信号检查")
            return None
        
        if df.empty:
            Logger.debug("K线数据为空，跳过信号检查")
            return None
            
        # 检查数据是否足够计算指标
        min_required = max(self.config.BOLL_PERIOD, self.config.ATR_PERIOD)
        if len(df) < min_required:
            Logger.debug(f"K线数据不足（当前{len(df)}条，需要至少{min_required}条），跳过信号检查")
            return None
        
        # 数据完整性检查
        if 'MIDDLE' not in df.columns or df['MIDDLE'].isna().all():
            Logger.warning("布林线中轨计算失败，数据可能异常")
            return None
        
        current_time = datetime.now()
        current_data = df.iloc[-1]
        current_price = current_data['close']
        current_atr = current_data.get('ATR', 0)
        
        # 如果有持仓，检查平仓信号
        if not self.position.is_empty():
            # 更新浮动止盈
            self.update_trailing_stop(df)
            
            # 检查平仓信号
            close_signal, close_reason = self.check_close_signal(df)
            if close_signal:
                self.close_position(current_price, close_reason, current_time)
                return "close"
        
        # 检查开仓信号
        if self.position.is_empty():
            can_open, open_reason = self.can_open_position(current_time)
            if can_open:
                direction, signal_reason = self.check_open_signal(df)
                if direction is not None:
                    self.open_position(direction, current_price, signal_reason, current_time, current_atr, current_data)
                    return "open"
            else:
                Logger.debug(f"不允许开仓: {open_reason}")
        
        return None
    
    def get_next_trading_time(self, current_time):
        """获取下一个交易时间段的开始时间"""
        # 菜籽油交易时间：
        # 周一至周五：
        # 日盘: 09:00-10:15, 10:30-11:30, 13:30-15:00
        # 夜盘: 21:00-23:00 （包括周五晚上）
        
        # 周末不交易
        weekday = current_time.weekday()
        if weekday == 5:  # 周六
            # 跳到下周一早盘
            next_monday = current_time + timedelta(days=2)
            return next_monday.replace(hour=8, minute=55, second=0, microsecond=0)
        elif weekday == 6:  # 周日  
            # 跳到周一早盘
            next_monday = current_time + timedelta(days=1)
            return next_monday.replace(hour=8, minute=55, second=0, microsecond=0)
        
        hour = current_time.hour
        minute = current_time.minute
        time_val = hour * 100 + minute
        
        # 如果在交易时间内，返回None
        if ((900 <= time_val < 1015) or
            (1030 <= time_val < 1130) or
            (1330 <= time_val < 1500) or
            (2100 <= time_val < 2300)):
            return None
            
        # 计算下一个交易时间段
        if time_val < 900:
            # 早上9点前，等待早盘
            next_time = current_time.replace(hour=8, minute=55, second=0, microsecond=0)
            if next_time < current_time:
                next_time += timedelta(days=1)
            return next_time
        elif 1015 <= time_val < 1030:
            # 早盘休息，等待10:30
            return current_time.replace(hour=10, minute=25, second=0, microsecond=0)
        elif 1130 <= time_val < 1330:
            # 午休，等待午盘
            return current_time.replace(hour=13, minute=25, second=0, microsecond=0)
        elif 1500 <= time_val < 2100:
            # 下午收盘后，等待夜盘（周一至周五都有夜盘）
            return current_time.replace(hour=20, minute=55, second=0, microsecond=0)
        else:
            # 23:00之后，等待下一个交易日早盘
            # 如果是周五晚上23:00后，跳到周一
            if weekday == 4:  # 周五
                next_monday = current_time + timedelta(days=3)
                return next_monday.replace(hour=8, minute=55, second=0, microsecond=0)
            else:
                # 其他时间，等待明天早盘
                next_day = current_time + timedelta(days=1)
                return next_day.replace(hour=8, minute=55, second=0, microsecond=0)
    
    def run_strategy_cycle(self, contract_code):
        """运行一个策略周期"""
        try:
            current_time = datetime.now()
            
            # 先检查绩效报告（即使在非交易时间也要检查，确保15:00后的报告能发送）
            self.check_performance_report(current_time)
            
            # 检查是否在交易时间
            next_trading_time = self.get_next_trading_time(current_time)
            if next_trading_time:
                # 非交易时间，计算休眠时间
                sleep_seconds = (next_trading_time - current_time).total_seconds()
                if sleep_seconds > 0:
                    # 只在首次进入休眠时输出日志
                    if not hasattr(self, '_sleeping') or not self._sleeping:
                        self._sleeping = True
                        Logger.info("="*50)
                        Logger.info(f"😴 非交易时间，策略进入休眠")
                        Logger.info(f"当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        Logger.info(f"下次启动: {next_trading_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        Logger.info(f"休眠时长: {sleep_seconds/3600:.1f}小时")
                        Logger.info("="*50)
                    
                    # 智能判断是否需要短间隔轮询
                    # 自动根据配置的报告时间计算轮询策略
                    need_short_poll = False
                    current_minutes = current_time.hour * 60 + current_time.minute
                    
                    # 检查日报时间窗口
                    daily_hour, daily_min_start, daily_min_end = BollStrategyConfig.DAILY_REPORT_TIME
                    daily_start = daily_hour * 60 + daily_min_start - BollStrategyConfig.REPORT_PREPARE_MINUTES
                    daily_end = daily_hour * 60 + daily_min_end + BollStrategyConfig.REPORT_CLEANUP_MINUTES
                    
                    if daily_start <= current_minutes <= daily_end:
                        need_short_poll = True
                    
                    # 检查周报时间窗口（仅周五）
                    if current_time.weekday() == 4:  # 周五
                        weekly_hour, weekly_min_start, weekly_min_end = BollStrategyConfig.WEEKLY_REPORT_TIME
                        weekly_start = weekly_hour * 60 + weekly_min_start - BollStrategyConfig.REPORT_PREPARE_MINUTES
                        weekly_end = weekly_hour * 60 + weekly_min_end + BollStrategyConfig.REPORT_CLEANUP_MINUTES
                        
                        if weekly_start <= current_minutes <= weekly_end:
                            need_short_poll = True
                    
                    # 根据是否需要短间隔轮询来决定休眠时间
                    if need_short_poll:
                        # 在报告时间窗口内，使用短间隔轮询
                        time.sleep(BollStrategyConfig.SHORT_POLL_INTERVAL)
                    elif sleep_seconds > BollStrategyConfig.LONG_POLL_INTERVAL:
                        # 休眠时间较长时，使用长间隔轮询
                        time.sleep(BollStrategyConfig.LONG_POLL_INTERVAL)
                    else:
                        # 其他情况，正常休眠
                        time.sleep(max(60, sleep_seconds))  # 至少睡眠1分钟
                    return
            else:
                # 在交易时间内，如果之前在休眠，输出唤醒日志
                if hasattr(self, '_sleeping') and self._sleeping:
                    self._sleeping = False
                    Logger.info("="*50)
                    Logger.info(f"🌟 交易时间开始，策略唤醒")
                    Logger.info(f"当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    Logger.info("="*50)
            
            # 1. 首先检查是否需要强制平仓（收盘前）
            if not self.position.is_empty():
                force_close, force_reason = self.check_force_close(current_time)
                if force_close:
                    current_price = self.get_current_price(contract_code)
                    if current_price:
                        self.close_position(current_price, force_reason, current_time)
                    return
            
            # 2. 检查止损（每次都检查，使用实时价格）
            if not self.position.is_empty():
                stop_loss_triggered, stop_reason = self.check_stop_loss_with_realtime_price(contract_code)
                if stop_loss_triggered:
                    current_price = self.get_current_price(contract_code)
                    if current_price:
                        Logger.info(f"⚠️ 触发止损条件: {stop_reason}")
                        self.close_position(current_price, stop_reason, current_time)
                    return
                else:
                    # 每60秒输出一次持仓状态
                    if not hasattr(self, '_last_position_log_time'):
                        self._last_position_log_time = current_time
                    
                    if (current_time - self._last_position_log_time).total_seconds() >= 60:
                        self._last_position_log_time = current_time
                        direction_text = "多" if self.position.is_long() else "空"
                        Logger.info(f"📊 持仓状态 - 方向: {direction_text}, 开仓价: {self.position.entry_price:.2f}, "
                                   f"当前价: {self.position.current_price:.2f}, 盈亏: {self.position.profit:.2f}元")
                        
                        # 定期更新Redis中的持仓信息
                        self._save_position_to_redis()
            
            # 3. 每分钟检查一次开平仓信号（基于K线收盘价）
            # 只在新的分钟开始时检查信号，避免频繁检查
            if not hasattr(self, '_last_signal_check_minute'):
                self._last_signal_check_minute = current_time.minute
                self._last_signal_check_time = current_time
            
            if current_time.minute != self._last_signal_check_minute:
                self._last_signal_check_minute = current_time.minute
                self._last_signal_check_time = current_time
                
                Logger.debug(f"🔍 执行信号检查 - 时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                signal_result = self.check_signals_with_kline(contract_code)
                
                if signal_result == "open":
                    Logger.info(f"📢 开仓信号触发，已执行开仓")
                elif signal_result == "close":
                    Logger.info(f"📤 平仓信号触发，已执行平仓")
                else:
                    Logger.debug(f"无有效交易信号")
            
        except Exception as e:
            Logger.error(f"策略执行异常: {e}")
            import traceback
            Logger.error(f"异常堆栈: {traceback.format_exc()}")
    
    def download_history_data(self, contract_code):
        """下载历史数据"""
        try:
            Logger.info(f"📁 开始下载历史数据: {contract_code}")
            
            # 获取最近的交易日
            current_time = datetime.now()
            
            # 如果是周末，往前推到周五
            while current_time.weekday() >= 5:  # 5是周六，6是周日
                current_time = current_time - timedelta(days=1)
            
            # 设置结束时间为当前交易日
            end_date = current_time.strftime('%Y%m%d')
            
            # 设置开始时间为30个交易日前
            start_date = (current_time - timedelta(days=45)).strftime('%Y%m%d')  # 45天确保包含30个交易日
            
            Logger.info(f"下载历史数据时间范围: {start_date} - {end_date}")
            
            # 下载1分钟K线历史数据
            result = xtdata.download_history_data(
                stock_code=contract_code,
                period='1m',
                start_time=start_date,
                end_time=end_date
            )
            
            Logger.info(f"1分钟K线数据下载完成: {contract_code}")
            
            # 下载tick数据（当天）
            tick_result = xtdata.download_history_data(
                stock_code=contract_code,
                period='tick',
                start_time=end_date,
                end_time=''
            )
            Logger.info(f"Tick数据下载完成: {contract_code}")
            
            return True
            
        except Exception as e:
            Logger.error(f"下载历史数据失败: {e}")
            import traceback
            Logger.error(f"错误堆栈: {traceback.format_exc()}")
            return False
    
    def subscribe_contract(self, contract_code):
        """订阅合约行情"""
        try:
            # 先下载历史数据
            if not self.download_history_data(contract_code):
                Logger.warning(f"历史数据下载失败，但继续订阅: {contract_code}")
            
            # 等待数据下载完成
            time.sleep(2)
            
            # 订阅tick数据
            xtdata.subscribe_quote(contract_code, period='tick', count=-1)
            Logger.info(f"已订阅tick数据: {contract_code}")
            
            # 订阅1分钟K线数据
            xtdata.subscribe_quote(contract_code, period='1m', count=-1)
            Logger.info(f"已订阅1分钟K线数据: {contract_code}")
            
            # 测试数据是否可用
            test_data = self.fetch_kline_data(contract_code)
            if test_data is not None and not test_data.empty:
                Logger.info(f"✅ 数据订阅成功，获取到 {len(test_data)} 条K线数据")
            else:
                Logger.warning(f"⚠️ 数据订阅后暂时无法获取数据，可能需要等待")
            
            return True
        except Exception as e:
            Logger.error(f"订阅合约{contract_code}失败: {e}")
            import traceback
            Logger.error(f"错误堆栈: {traceback.format_exc()}")
            return False
    
    def start(self):
        """启动策略"""
        self.is_running = True
        
        # 策略启动通知
        Logger.info("="*50)
        Logger.info("🚀 布林线策略正在启动...")
        Logger.info(f"策略版本: V2.5")
        Logger.info(f"交易品种: {self.config.PRODUCT_NAME}({self.config.PRODUCT_TYPE})")
        Logger.info(f"布林线参数: {self.config.BOLL_PERIOD}周期, {self.config.BOLL_STD}倍标准差")
        Logger.info(f"风控参数: 硬止损{self.config.HARD_STOP_LOSS}元, ATR倍数{self.config.ATR_MULTIPLIER_FOR_PROFIT}")
        
        # 输出保护期配置
        Logger.info("保护期设置:")
        Logger.info(f"  - 早盘开盘后: {self.config.NO_OPEN_MINUTES_AFTER_MORNING_OPEN}分钟")
        Logger.info(f"  - 夜盘开盘后: {self.config.NO_OPEN_MINUTES_AFTER_NIGHT_OPEN}分钟")
        Logger.info(f"  - 早盘休市前: {self.config.NO_OPEN_MINUTES_BEFORE_MORNING_BREAK}分钟")
        Logger.info(f"  - 早盘收盘前: {self.config.NO_OPEN_MINUTES_BEFORE_MORNING_CLOSE}分钟")
        Logger.info(f"  - 午盘收盘前: {self.config.NO_OPEN_MINUTES_BEFORE_AFTERNOON_CLOSE}分钟")
        Logger.info(f"  - 夜盘收盘前: {self.config.NO_OPEN_MINUTES_BEFORE_NIGHT_CLOSE}分钟")
        Logger.info(f"  - 止损后: {self.config.NO_OPEN_MINUTES_AFTER_LOSS}分钟")
        Logger.info("（提示：将任意保护时间设为0可关闭对应保护）")
        Logger.info("="*50)
        
        # 发送启动通知到"老公老婆"群
        startup_msg = f"【策略启动通知】\n布林线策略已启动\n品种: {self.config.PRODUCT_NAME}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        try:
            send_message(startup_msg, "老公老婆")
        except Exception as e:
            Logger.warning(f"发送启动通知失败: {e}")
        
        # 从Redis恢复持仓信息和交易历史
        self._load_position_from_redis()
        self._load_trade_history_from_redis()
        
        # 获取主力合约
        contract_code = self.get_main_contract()
        if not contract_code:
            Logger.error("无法获取主力合约，策略退出")
            return
        
        # 订阅合约行情
        if not self.subscribe_contract(contract_code):
            Logger.error("订阅合约行情失败，策略退出")
            return
        
        # 等待数据推送稳定
        Logger.info("等待数据推送稳定...")
        time.sleep(3)
        
        Logger.info(f"✅ 布林线策略启动成功 - 合约: {contract_code}")
        
        # 检查当前是否交易时间
        current_time = datetime.now()
        next_trading_time = self.get_next_trading_time(current_time)
        if next_trading_time:
            Logger.info(f"⚠️ 当前为非交易时间，将在{next_trading_time.strftime('%H:%M')}唤醒")
        else:
            Logger.info("✅ 当前为交易时间，开始监控")
        
        Logger.info("="*50)
        
        try:
            while self.is_running:
                self.run_strategy_cycle(contract_code)
                # 如果在休眠状态，不需要频繁循环
                if hasattr(self, '_sleeping') and self._sleeping:
                    continue
                time.sleep(self.config.DATA_INTERVAL)
                
        except KeyboardInterrupt:
            Logger.info("接收到中断信号，策略停止")
            # 发送中断通知
            interrupt_msg = f"【策略中断】\n布林线策略被手动中断\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            try:
                send_message(interrupt_msg, "老公老婆")
            except:
                pass
        except Exception as e:
            Logger.error(f"策略运行异常: {e}")
            # 发送异常通知
            error_msg = f"【策略异常】\n布林线策略出现异常\n错误: {str(e)[:100]}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            try:
                send_message(error_msg, "老公老婆")
            except:
                pass
        finally:
            self.stop()
    
    def stop(self):
        """停止策略"""
        self.is_running = False
        Logger.info("="*50)
        Logger.info("🚫 布林线策略已停止")
        Logger.info("="*50)
        
        # 发送停止通知
        stop_msg = f"【策略停止通知】\n布林线策略已停止\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        try:
            send_message(stop_msg, "老公老婆")
        except Exception as e:
            Logger.warning(f"发送停止通知失败: {e}")


def main():
    """主函数"""
    sleep(random.randint(1,20))
    strategy = BollStrategy()
    
    try:
        strategy.start()
    except Exception as e:
        Logger.error(f"策略启动失败: {e}")
    finally:
        strategy.stop()


if __name__ == "__main__":
    main()