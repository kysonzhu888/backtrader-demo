#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
动力波策略（基于xtdata数据源）
策略逻辑：
- 使用动力波指标判断趋势
- 颜色变化确认开仓信号
- 硬止损：666元（可配置）
- 浮动止盈：阶梯式止盈策略
- 开仓保护：开盘后15分钟、收盘前15分钟不开仓
"""

import os
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

# 微信发送功能
def send_message_safe(msg, group):
    """安全的微信发送函数"""
    try:
        from utils.wechat import send_message
        send_message(msg, group)
    except Exception as e:
        Logger.info(f"[模拟发送] {group}: {msg}")
        Logger.debug(f"微信发送失败: {e}")

# 使用安全的发送函数
send_message = send_message_safe
from utils.trading_time_helper import TradingTimeHelper
from utils.date_utils import DateUtils
from xtquant import xtdata


class PowerWaveConfig:
    """动力波策略配置"""
    
    # 品种配置（默认沪金，可配置其他品种）
    PRODUCT_TYPE = 'au'  # 沪金（注意：xtdata中沪金代码是小写au）
    PRODUCT_NAME = '沪金'
    CONTRACT_MULTIPLIER = 1000  # 沪金一个点1000元
    EXCHANGE = 'SF'  # 上期所
    
    # 开仓条件配置（可设置False禁用某个条件）
    USE_PERCENTILE_CONDITION = True  # 是否使用百分位条件
    USE_MACD_CONDITION = True        # 是否使用MACD条件
    USE_BOLL_CONDITION = True        # 是否使用布林线条件
    
    # 布林线参数（与boll_strategy保持一致）
    BOLL_PERIOD = 26  # 布林线周期
    BOLL_STD = 2.0    # 标准差倍数
    
    # 数据配置
    DATA_INTERVAL = 6  # 数据拉取间隔（秒）
    KLINE_PERIOD = '1min'  # 关注的K线周期
    WARMUP_PERIOD = 34  # 预热期（需要至少34根K线计算指标）
    
    # 动力波参数
    POWER_WAVE_HL_PERIOD = 34  # 高低点周期
    POWER_WAVE_EMA1_PERIOD = 13  # 第一个EMA周期
    POWER_WAVE_EMA2_PERIOD = 2  # 第二个EMA周期
    
    # 风控参数
    HARD_STOP_LOSS = 666  # 硬止损金额（元）
    HARD_STOP_LOSS_POINTS = HARD_STOP_LOSS / CONTRACT_MULTIPLIER  # 转换为点数
    
    # 保本止损相关参数（阶梯式止盈）
    BREAKEVEN_THRESHOLDS = [3000, 2000, 1200, 666]  # 浮盈阈值，降序排列
    BREAKEVEN_PROFITS = [1800, 1000, 500, 0]  # 对应的保本金额
    BREAKEVEN_POINT_OFFSET = 0.25  # 最低保本点数
    
    # 开仓保护时间
    NO_OPEN_MINUTES_AFTER_MORNING_OPEN = 15  # 早盘09:00开盘后不开仓时间（分钟）
    NO_OPEN_MINUTES_AFTER_NIGHT_OPEN = 15  # 夜盘21:00开盘后不开仓时间（分钟）
    NO_OPEN_MINUTES_BEFORE_CLOSE = 15  # 收盘前不开仓时间（分钟）
    NO_OPEN_MINUTES_AFTER_LOSS = 30  # 止损后不开仓时间（分钟）
    
    # 强制平仓时间（收盘前分钟数）
    FORCE_CLOSE_MINUTES_BEFORE_END = 5  # 收盘前5分钟强制平仓
    
    # 微信播报
    WECHAT_GROUP = "动力波策略群"
    
    # 绩效报告配置
    DAILY_REPORT_TIME = (15, 0, 1)  # 日报时间
    WEEKLY_REPORT_TIME = (15, 5, 6)  # 周报时间
    SHORT_POLL_INTERVAL = 60  # 短间隔：60秒
    LONG_POLL_INTERVAL = 1800  # 长间隔：30分钟
    REPORT_PREPARE_MINUTES = 5  # 报告前准备时间
    REPORT_CLEANUP_MINUTES = 5  # 报告后清理时间
    
    # Redis配置
    REDIS_KEY_PREFIX = 'power_wave'
    
    @classmethod
    def update_product(cls, product_type, product_name, multiplier, exchange):
        """更新品种配置"""
        cls.PRODUCT_TYPE = product_type
        cls.PRODUCT_NAME = product_name
        cls.CONTRACT_MULTIPLIER = multiplier
        cls.EXCHANGE = exchange
        cls.HARD_STOP_LOSS_POINTS = cls.HARD_STOP_LOSS / cls.CONTRACT_MULTIPLIER


class PowerWaveIndicator:
    """动力波指标计算"""
    
    def __init__(self, config=None):
        self.config = config or PowerWaveConfig()
        self.close = None
        self.high = None
        self.low = None
        self.vara = None
        self.vard = None
        self.vare = None
        self.bar_height = None
        
        # MACD相关
        self.macd = None
        self.macd_signal = None
        self.macd_hist = None
        
        # 布林线相关
        self.boll_upper = None
        self.boll_middle = None
        self.boll_lower = None
        
        # 百分位相关
        self.percentile = None
        
    def update(self, data_window):
        """更新指标"""
        if len(data_window) < self.config.POWER_WAVE_HL_PERIOD:
            return
            
        self.close = data_window['close']
        self.high = data_window['high']
        self.low = data_window['low']
        
        # 计算动力波指标
        self.vara = (2 * self.close + self.high + self.low) / 4
        
        # 计算高低点
        varc = self.high.rolling(window=self.config.POWER_WAVE_HL_PERIOD).max()
        varb = self.low.rolling(window=self.config.POWER_WAVE_HL_PERIOD).min()
        
        # 计算比率
        numerator = self.vara - varb
        denominator = varc - varb
        # 避免除零
        denominator = denominator.replace(0, 1)
        ratio = (numerator / denominator) * 100
        
        # 计算VARD（第一个EMA）
        self.vard = ratio.ewm(span=self.config.POWER_WAVE_EMA1_PERIOD, adjust=False).mean()
        
        # 计算VARE（第二个EMA）
        ref_vard = self.vard.shift(1)
        vare_input = 0.667 * ref_vard + 0.333 * self.vard
        self.vare = vare_input.ewm(span=self.config.POWER_WAVE_EMA2_PERIOD, adjust=False).mean()
        
        # 计算柱高
        self.bar_height = abs(self.vard - self.vare)
        
        # 计算MACD指标
        self._calculate_macd()
        
        # 计算布林线指标
        self._calculate_bollinger()
        
        # 计算百分位
        self._calculate_percentile()
    
    def _calculate_macd(self):
        """计算MACD指标"""
        if self.close is None or len(self.close) < 26:
            return
        
        # 计算EMA12和EMA26
        ema12 = self.close.ewm(span=12, adjust=False).mean()
        ema26 = self.close.ewm(span=26, adjust=False).mean()
        
        # 计算MACD线
        self.macd = ema12 - ema26
        
        # 计算信号线（9周期EMA）
        self.macd_signal = self.macd.ewm(span=9, adjust=False).mean()
        
        # 计算MACD柱
        self.macd_hist = self.macd - self.macd_signal
    
    def _calculate_bollinger(self):
        """计算布林线指标"""
        if self.close is None or len(self.close) < self.config.BOLL_PERIOD:
            return
        
        # 计算布林线中轨（使用配置的周期）
        self.boll_middle = self.close.rolling(window=self.config.BOLL_PERIOD).mean()
        
        # 计算标准差
        std = self.close.rolling(window=self.config.BOLL_PERIOD).std()
        
        # 计算上下轨（使用配置的标准差倍数）
        self.boll_upper = self.boll_middle + self.config.BOLL_STD * std
        self.boll_lower = self.boll_middle - self.config.BOLL_STD * std
    
    def _calculate_percentile(self):
        """计算百分位指标（实际上是vard或vare的值）"""
        if self.vard is None or self.vare is None:
            self.percentile = 50  # 默认值
            return
        
        if len(self.vard) == 0 or len(self.vare) == 0:
            self.percentile = 50
            return
        
        # 根据当前颜色取对应的值作为"百分位"
        # 这里的百分位实际上是动力波指标的值，范围大约在0-100之间
        current_color = self.get_color(-1)
        if current_color == 'red':
            # 红色时取vare的值
            self.percentile = self.vare.iloc[-1]
        else:
            # 绿色时取vard的值
            self.percentile = self.vard.iloc[-1]
        
    def get_color(self, index=-1):
        """获取K线颜色（红涨绿跌）"""
        if self.vard is None or self.vare is None:
            return None
        
        if len(self.vard) == 0 or len(self.vare) == 0:
            return None
            
        try:
            if self.vard.iloc[index] > self.vare.iloc[index]:
                return 'red'  # 红色表示上涨
            else:
                return 'green'  # 绿色表示下跌
        except:
            return None
    
    def check_color_change(self):
        """检查颜色变化，返回方向(1:绿变红做多, -1:红变绿做空, 0:无变化)"""
        current_color = self.get_color(-1)
        prev_color = self.get_color(-2)
        
        if prev_color is None or current_color is None:
            return 0
        
        # 判断颜色变化
        if prev_color == 'green' and current_color == 'red':
            return 1  # 绿变红 - 做多信号
        elif prev_color == 'red' and current_color == 'green':
            return -1  # 红变绿 - 做空信号
        
        return 0
    
    def check_opening_conditions(self, direction):
        """检查所有开仓条件"""
        conditions = {}
        all_satisfied = True
        
        # 1. 百分位条件（如果启用）
        if self.config.USE_PERCENTILE_CONDITION:
            percentile_ok = self._check_percentile_condition(direction)
            conditions['百分位'] = percentile_ok
            all_satisfied = all_satisfied and percentile_ok
        else:
            conditions['百分位'] = '已禁用'
        
        # 2. MACD条件（如果启用）
        if self.config.USE_MACD_CONDITION:
            macd_ok = self._check_macd_condition(direction)
            conditions['MACD'] = macd_ok
            all_satisfied = all_satisfied and macd_ok
        else:
            conditions['MACD'] = '已禁用'
        
        # 3. 布林线条件（如果启用）
        if self.config.USE_BOLL_CONDITION:
            boll_ok = self._check_boll_condition(direction)
            conditions['布林线'] = boll_ok
            all_satisfied = all_satisfied and boll_ok
        else:
            conditions['布林线'] = '已禁用'
        
        # 输出调试信息
        Logger.debug(f"开仓条件检查 - 百分位:{conditions['百分位']}, MACD:{conditions['MACD']}, 布林:{conditions['布林线']}")
        
        return all_satisfied, conditions
    
    def _check_macd_condition(self, signal_direction):
        """检查MACD条件"""
        if self.macd is None or self.macd_signal is None:
            return False
        
        try:
            current_macd = self.macd.iloc[-1]
            current_signal = self.macd_signal.iloc[-1]
            
            if signal_direction == 1:  # 做多
                # MACD金叉：MACD线在信号线上方
                return current_macd > current_signal
            elif signal_direction == -1:  # 做空
                # MACD死叉：MACD线在信号线下方
                return current_macd < current_signal
        except:
            return False
        
        return False
    
    def _check_boll_condition(self, signal_direction):
        """检查布林线条件"""
        if self.boll_middle is None or self.close is None:
            return False
        
        try:
            current_close = self.close.iloc[-1]
            current_middle = self.boll_middle.iloc[-1]
            
            if signal_direction == 1:  # 做多
                # 收盘价在中轨上方
                return current_close >= current_middle
            elif signal_direction == -1:  # 做空
                # 收盘价在中轨下方
                return current_close < current_middle
        except:
            return False
        
        return False
    
    def _check_percentile_condition(self, signal_direction):
        """检查百分位条件"""
        if self.percentile is None:
            return False
        
        try:
            if signal_direction == 1:  # 做多
                # 百分位小于25
                return self.percentile < 25
            elif signal_direction == -1:  # 做空
                # 百分位大于75
                return self.percentile > 75
        except:
            return False
        
        return False


class Position:
    """持仓信息"""
    
    def __init__(self):
        self.direction = 0  # 0:空仓, 1:多仓, -1:空仓
        self.entry_price = 0.0
        self.entry_time = None
        self.stop_price = 0.0
        self.profit = 0.0
        self.max_profit = 0.0
        
    def is_empty(self):
        return self.direction == 0
        
    def is_long(self):
        return self.direction == 1
        
    def is_short(self):
        return self.direction == -1
        
    def open_position(self, direction, price, time, stop_price):
        """开仓"""
        self.direction = direction
        self.entry_price = price
        self.entry_time = time
        self.stop_price = stop_price
        self.profit = 0.0
        self.max_profit = 0.0
        
    def close_position(self):
        """平仓"""
        self.direction = 0
        self.entry_price = 0.0
        self.entry_time = None
        self.stop_price = 0.0
        self.profit = 0.0
        self.max_profit = 0.0
        
    def update_profit(self, current_price, multiplier):
        """更新盈亏"""
        if self.is_long():
            self.profit = (current_price - self.entry_price) * multiplier
        elif self.is_short():
            self.profit = (self.entry_price - current_price) * multiplier
        
        self.max_profit = max(self.max_profit, self.profit)


class TradeRecord:
    """交易记录"""
    
    def __init__(self):
        self.entry_time = None
        self.exit_time = None
        self.entry_price = 0.0
        self.exit_price = 0.0
        self.direction = 0  # 1:多, -1:空
        self.profit = 0.0
        self.exit_reason = ''


class PendingSignal:
    """待开仓信号管理"""
    
    def __init__(self):
        self.active = False  # 是否有待开仓信号
        self.direction = 0   # 1:做多, -1:做空
        self.start_time = None  # 信号开始时间
        self.color_from = None  # 变化前的颜色
        self.color_to = None    # 变化后的颜色
        self.percentile_at_signal = None  # 信号时的百分位
        self.bar_count = 0  # 信号后的K线数
        self.max_wait_bars = 10  # 最多等待10根K线
    
    def set_signal(self, direction, color_from, color_to, percentile, time):
        """设置待开仓信号"""
        self.active = True
        self.direction = direction
        self.color_from = color_from
        self.color_to = color_to
        self.percentile_at_signal = percentile
        self.start_time = time
        self.bar_count = 0
    
    def clear(self):
        """清除信号"""
        self.active = False
        self.direction = 0
        self.start_time = None
        self.color_from = None
        self.color_to = None
        self.percentile_at_signal = None
        self.bar_count = 0
    
    def increment_bar_count(self):
        """增加K线计数"""
        self.bar_count += 1
        # 超过最大等待K线数，自动清除信号
        if self.bar_count > self.max_wait_bars:
            Logger.info(f"待开仓信号超时({self.max_wait_bars}根K线)，清除信号")
            self.clear()
            return False
        return True


class PowerWaveStrategy:
    """动力波策略主类"""
    
    def __init__(self, config=None):
        """初始化策略"""
        self.config = config or PowerWaveConfig()
        self.running = False
        self.thread = None
        
        # 初始化Redis连接
        try:
            self.redis_client = redis.Redis(
                host=environment.REDIS_HOST,
                port=environment.REDIS_PORT,
                password=environment.REDIS_PASSWORD,
                db=environment.REDIS_DB,
                decode_responses=True
            )
            self.redis_client.ping()
            Logger.info("Redis连接成功")
        except Exception as e:
            Logger.error(f"Redis连接失败: {e}")
            self.redis_client = None
        
        # xtdata登录
        try:
            xtdata.connect()
            Logger.info("xtdata连接成功")
        except Exception as e:
            Logger.warning(f"xtdata连接警告: {e}，将在运行时尝试重新连接")
        
        # 策略组件
        self.indicator = PowerWaveIndicator(self.config)
        self.position = Position()
        self.pending_signal = PendingSignal()  # 待开仓信号管理
        self.trade_history = []
        self.last_loss_time = None
        self.last_check_time = None  # 上次检查时间
        
        # 从Redis加载历史交易记录
        self._load_trade_history_from_redis()
        
        # 数据缓存
        self.main_contract = None
        self.data_window = pd.DataFrame()
        self.last_update_time = None
        self.tick_count = 0  # tick计数器
        
        # 报告时间记录
        self.last_daily_report_date = None
        self.last_weekly_report_date = None
        
        # 交易时间助手（注意：TradingTimeHelper需要大写的产品代码）
        self.trading_helper = TradingTimeHelper(self.config.PRODUCT_TYPE.upper())
        
        Logger.info(f"动力波策略初始化完成 - 品种: {self.config.PRODUCT_NAME}({self.config.PRODUCT_TYPE})")
    
    def ensure_xtdata_connected(self):
        """确保xtdata已连接"""
        try:
            # 尝试一个简单的操作来检查连接
            test = xtdata.get_stock_list_in_sector('SF')
            if test is None:
                Logger.info("xtdata未连接，尝试重新连接...")
                xtdata.connect()
                Logger.info("xtdata重新连接成功")
        except Exception as e:
            Logger.warning(f"xtdata连接检查失败: {e}，尝试重新连接...")
            try:
                xtdata.connect()
                Logger.info("xtdata重新连接成功")
            except Exception as e2:
                Logger.error(f"xtdata重新连接失败: {e2}")
    
    def get_main_contract(self):
        """获取主力合约"""
        try:
            Logger.info("="*50)
            Logger.info("📋 开始获取主力合约...")
            Logger.info(f"品种: {self.config.PRODUCT_NAME}({self.config.PRODUCT_TYPE})")
            
            # 确保xtdata已连接
            self.ensure_xtdata_connected()
            
            # 获取交易所所有合约
            codes = xtdata.get_stock_list_in_sector(self.config.EXCHANGE)
            
            # 检查是否成功获取合约列表
            if codes is None:
                Logger.error(f"无法获取{self.config.EXCHANGE}交易所合约列表，可能xtdata未连接或交易所代码错误")
                return None
            
            Logger.info(f"获取到{self.config.EXCHANGE}合约总数: {len(codes)}个")
            
            # 过滤出对应品种的期货合约
            futures = []
            options = []
            seen_contracts = set()
            
            for code in codes:
                # 去掉交易所后缀后判断
                code_without_exchange = code.split('.')[0] if '.' in code else code
                # 判断是否为目标品种（沪金的代码是au，不是AU）
                if code_without_exchange.lower().startswith(self.config.PRODUCT_TYPE.lower()):
                    # 排除期权合约
                    if self._is_option_contract(code):
                        options.append(code)
                    else:
                        if code not in seen_contracts:
                            futures.append(code)
                            seen_contracts.add(code)
                            Logger.debug(f"保留期货合约: {code}")
            
            Logger.info(f"{self.config.PRODUCT_NAME}期货合约数: {len(futures)}个, 期权合约数: {len(options)}个")
            
            # 输出期货合约列表
            if futures:
                Logger.info(f"期货合约代码: {', '.join(sorted(futures)[:5])}...")  # 显示前5个
            
            if not futures:
                Logger.error(f"未找到{self.config.PRODUCT_NAME}期货合约")
                return None
            
            # 获取实时行情判断主力
            Logger.info("开始分析各合约成交量...")
            field_list = ['volume', 'amount']
            data = xtdata.get_full_tick(futures)
            
            # 找出成交量最大的合约
            max_volume = 0
            main_contract = None
            contract_volumes = {}
            
            for code in futures:
                if code in data:
                    volume = data[code].get('volume', 0)
                    contract_volumes[code] = volume
                    Logger.debug(f"合约 {code} 成交量: {volume}")
                    
                    if volume > max_volume:
                        max_volume = volume
                        main_contract = code
            
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
                Logger.error("未能确定主力合约")
                return None
                
        except Exception as e:
            Logger.error(f"获取主力合约失败: {e}")
            return None
    
    def _is_option_contract(self, code):
        """判断是否为期权合约"""
        code_without_exchange = code.split('.')[0] if '.' in code else code
        
        # 期权代码通常更长，且包含C或P
        if len(code_without_exchange) > 5:
            if 'C' in code_without_exchange[4:] or 'P' in code_without_exchange[4:]:
                for i, char in enumerate(code_without_exchange):
                    if char in ['C', 'P'] and i > 3:
                        if i + 1 < len(code_without_exchange) and code_without_exchange[i + 1].isdigit():
                            return True
        return False
    
    def download_and_subscribe_data(self, contract_code):
        """下载历史数据并订阅实时数据"""
        try:
            # 计算时间范围
            end_time = datetime.now()
            start_time = end_time - timedelta(days=1)  # 获取1天的数据
            
            Logger.info(f"开始下载1分钟K线数据: {contract_code}")
            
            # 下载历史K线数据
            xtdata.download_history_data(
                stock_code=contract_code,
                period='1m',
                start_time=start_time.strftime('%Y%m%d%H%M%S'),
                end_time=end_time.strftime('%Y%m%d%H%M%S')
            )
            
            Logger.info(f"1分钟K线数据下载完成: {contract_code}")
            
            # 下载tick数据
            Logger.info(f"开始下载Tick数据: {contract_code}")
            xtdata.download_history_data(
                stock_code=contract_code,
                period='tick',
                start_time=start_time.strftime('%Y%m%d%H%M%S'),
                end_time=end_time.strftime('%Y%m%d%H%M%S')
            )
            
            Logger.info(f"Tick数据下载完成: {contract_code}")
            
            # 订阅实时tick数据
            xtdata.subscribe_quote(contract_code, period='tick')
            Logger.info(f"已订阅tick数据: {contract_code}")
            
            # 订阅实时K线数据
            xtdata.subscribe_quote(contract_code, period='1m')
            Logger.info(f"已订阅1分钟K线数据: {contract_code}")
            
            return True
            
        except Exception as e:
            Logger.error(f"下载或订阅数据失败: {e}")
            return False
    
    def get_latest_klines(self, contract_code, count=50):
        """获取最新K线数据"""
        try:
            current_time = datetime.now()
            
            # 计算时间范围
            end_time = current_time
            start_time = end_time - timedelta(hours=8)  # 获取8小时的数据
            
            Logger.debug(f"获取K线数据: {contract_code}, 时间范围: {start_time.strftime('%Y-%m-%d %H:%M:%S')} - {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 获取1分钟K线数据
            data = xtdata.get_market_data_ex(
                stock_list=[contract_code],
                period='1m',
                count=count
            )
            
            if not data or contract_code not in data:
                Logger.warning(f"未获取到K线数据: {contract_code}")
                return None
            
            df = data[contract_code]
            
            if len(df) == 0:
                Logger.warning(f"K线数据为空: {contract_code}")
                return None
            
            # 转换为标准格式
            df_formatted = pd.DataFrame({
                'open': df['open'],
                'high': df['high'],
                'low': df['low'],
                'close': df['close'],
                'volume': df['volume']
            }, index=df.index)
            
            # 保留原始索引格式（可能是字符串或datetime）
            
            Logger.debug(f"获取到K线数据，行数: {len(df_formatted)}, 最新时间: {df_formatted.index[-1]}")
            
            return df_formatted
            
        except Exception as e:
            Logger.error(f"获取K线数据失败: {e}")
            import traceback
            Logger.debug(traceback.format_exc())
            return None
    
    def check_open_conditions(self, current_time):
        """检查开仓条件"""
        if not self.position.is_empty():
            return False, "已有持仓"
        
        # 检查是否在交易时间
        if not self.trading_helper.is_trading_time(current_time):
            return False, "非交易时间"
        
        # 检查开盘后和收盘前的保护时间
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # 获取当前品种的交易时段
        trade_hours = self.trading_helper.trading_time()
        
        for start_str, end_str in trade_hours:
            start_hour, start_min = map(int, start_str.split(':'))
            end_hour, end_min = map(int, end_str.split(':'))
            
            # 判断是否在当前交易时段内
            is_in_current_session = False
            
            if start_hour < end_hour:
                # 正常时段（不跨天）
                if (start_hour < current_hour < end_hour) or \
                   (start_hour == current_hour and current_minute >= start_min) or \
                   (end_hour == current_hour and current_minute <= end_min):
                    is_in_current_session = True
            else:
                # 跨天时段（如21:00-02:30）
                if (current_hour >= start_hour) or (current_hour <= end_hour):
                    if (current_hour == start_hour and current_minute >= start_min) or \
                       (current_hour > start_hour) or \
                       (current_hour < end_hour) or \
                       (current_hour == end_hour and current_minute <= end_min):
                        is_in_current_session = True
            
            if not is_in_current_session:
                continue
                
            # 检查开盘后保护时间
            if start_hour == 9 and start_min == 0:  # 早盘
                if self.config.NO_OPEN_MINUTES_AFTER_MORNING_OPEN > 0:
                    protection_end_min = start_min + self.config.NO_OPEN_MINUTES_AFTER_MORNING_OPEN
                    if current_hour == start_hour and current_minute < protection_end_min:
                        minutes_left = protection_end_min - current_minute
                        return False, f"早盘开盘后保护期，剩余{minutes_left}分钟"
            
            elif start_hour == 21 and start_min == 0:  # 夜盘
                if self.config.NO_OPEN_MINUTES_AFTER_NIGHT_OPEN > 0:
                    protection_end_min = start_min + self.config.NO_OPEN_MINUTES_AFTER_NIGHT_OPEN
                    if current_hour == start_hour and current_minute < protection_end_min:
                        minutes_left = protection_end_min - current_minute
                        return False, f"夜盘开盘后保护期，剩余{minutes_left}分钟"
            
            # 检查收盘前保护时间
            if self.config.NO_OPEN_MINUTES_BEFORE_CLOSE > 0:
                # 计算收盘前保护期开始时间
                protection_start_min = end_min - self.config.NO_OPEN_MINUTES_BEFORE_CLOSE
                
                if start_hour < end_hour:
                    # 正常时段
                    if (current_hour == end_hour and current_minute >= protection_start_min) or \
                       (protection_start_min < 0 and current_hour == end_hour - 1 and current_minute >= 60 + protection_start_min):
                        if protection_start_min < 0:
                            minutes_left = (60 + protection_start_min) + (60 - current_minute) if current_hour == end_hour - 1 else end_min - current_minute
                        else:
                            minutes_left = end_min - current_minute
                        return False, f"收盘前保护期，剩余{minutes_left}分钟"
                else:
                    # 跨天时段（如21:00-02:30）
                    if current_hour <= end_hour:
                        # 次日时段（如00:00-02:30）
                        if (current_hour == end_hour and current_minute >= protection_start_min) or \
                           (protection_start_min < 0 and current_hour == end_hour - 1 and current_minute >= 60 + protection_start_min):
                            if protection_start_min < 0:
                                minutes_left = (60 + protection_start_min) + (60 - current_minute) if current_hour == end_hour - 1 else end_min - current_minute
                            else:
                                minutes_left = end_min - current_minute
                            return False, f"夜盘收盘前保护期，剩余{minutes_left}分钟"
        
        # 止损后保护
        if self.last_loss_time:
            time_since_loss = (current_time - self.last_loss_time).total_seconds() / 60
            if time_since_loss < self.config.NO_OPEN_MINUTES_AFTER_LOSS:
                minutes_left = self.config.NO_OPEN_MINUTES_AFTER_LOSS - time_since_loss
                return False, f"止损后保护期，剩余{minutes_left:.0f}分钟"
        
        return True, "允许开仓"
    
    def check_close_conditions(self, current_time):
        """检查平仓条件（排除强制平仓）"""
        if self.position.is_empty():
            return False, "无持仓"
        
        # 检查是否在交易时间
        if not self.trading_helper.is_trading_time(current_time):
            return False, "非交易时间"
        
        # 检查开盘后和收盘前的保护时间（与开仓条件相同的逻辑）
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # 获取当前品种的交易时段
        trade_hours = self.trading_helper.trading_time()
        
        for start_str, end_str in trade_hours:
            start_hour, start_min = map(int, start_str.split(':'))
            end_hour, end_min = map(int, end_str.split(':'))
            
            # 判断是否在当前交易时段内
            is_in_current_session = False
            
            if start_hour < end_hour:
                # 正常时段（不跨天）
                if (start_hour < current_hour < end_hour) or \
                   (start_hour == current_hour and current_minute >= start_min) or \
                   (end_hour == current_hour and current_minute <= end_min):
                    is_in_current_session = True
            else:
                # 跨天时段（如21:00-02:30）
                if (current_hour >= start_hour) or (current_hour <= end_hour):
                    if (current_hour == start_hour and current_minute >= start_min) or \
                       (current_hour > start_hour) or \
                       (current_hour < end_hour) or \
                       (current_hour == end_hour and current_minute <= end_min):
                        is_in_current_session = True
            
            if not is_in_current_session:
                continue
                
            # 检查开盘后保护时间
            if start_hour == 9 and start_min == 0:  # 早盘
                if self.config.NO_OPEN_MINUTES_AFTER_MORNING_OPEN > 0:
                    protection_end_min = start_min + self.config.NO_OPEN_MINUTES_AFTER_MORNING_OPEN
                    if current_hour == start_hour and current_minute < protection_end_min:
                        minutes_left = protection_end_min - current_minute
                        return False, f"早盘开盘后保护期，剩余{minutes_left}分钟"
            
            elif start_hour == 21 and start_min == 0:  # 夜盘
                if self.config.NO_OPEN_MINUTES_AFTER_NIGHT_OPEN > 0:
                    protection_end_min = start_min + self.config.NO_OPEN_MINUTES_AFTER_NIGHT_OPEN
                    if current_hour == start_hour and current_minute < protection_end_min:
                        minutes_left = protection_end_min - current_minute
                        return False, f"夜盘开盘后保护期，剩余{minutes_left}分钟"
            
            # 检查收盘前保护时间
            if self.config.NO_OPEN_MINUTES_BEFORE_CLOSE > 0:
                # 计算收盘前保护期开始时间
                protection_start_min = end_min - self.config.NO_OPEN_MINUTES_BEFORE_CLOSE
                
                if start_hour < end_hour:
                    # 正常时段
                    if (current_hour == end_hour and current_minute >= protection_start_min) or \
                       (protection_start_min < 0 and current_hour == end_hour - 1 and current_minute >= 60 + protection_start_min):
                        if protection_start_min < 0:
                            minutes_left = (60 + protection_start_min) + (60 - current_minute) if current_hour == end_hour - 1 else end_min - current_minute
                        else:
                            minutes_left = end_min - current_minute
                        return False, f"收盘前保护期，剩余{minutes_left}分钟"
                else:
                    # 跨天时段（如21:00-02:30）
                    if current_hour <= end_hour:
                        # 次日时段（如00:00-02:30）
                        if (current_hour == end_hour and current_minute >= protection_start_min) or \
                           (protection_start_min < 0 and current_hour == end_hour - 1 and current_minute >= 60 + protection_start_min):
                            if protection_start_min < 0:
                                minutes_left = (60 + protection_start_min) + (60 - current_minute) if current_hour == end_hour - 1 else end_min - current_minute
                            else:
                                minutes_left = end_min - current_minute
                            return False, f"夜盘收盘前保护期，剩余{minutes_left}分钟"
        
        return True, "允许平仓"
    
    def check_force_close(self, current_time):
        """检查是否需要强制平仓"""
        if self.position.is_empty():
            return False, None
            
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # 获取当前品种的交易时段并检查是否需要强制平仓
        trade_hours = self.trading_helper.trading_time()
        
        for start_str, end_str in trade_hours:
            start_hour, start_min = map(int, start_str.split(':'))
            end_hour, end_min = map(int, end_str.split(':'))
            
            # 判断是否在当前交易时段内
            is_in_current_session = False
            
            if start_hour < end_hour:
                # 正常时段（不跨天）
                if (start_hour < current_hour < end_hour) or \
                   (start_hour == current_hour and current_minute >= start_min) or \
                   (end_hour == current_hour and current_minute <= end_min):
                    is_in_current_session = True
            else:
                # 跨天时段（如21:00-02:30）
                if (current_hour >= start_hour) or (current_hour <= end_hour):
                    if (current_hour == start_hour and current_minute >= start_min) or \
                       (current_hour > start_hour) or \
                       (current_hour < end_hour) or \
                       (current_hour == end_hour and current_minute <= end_min):
                        is_in_current_session = True
            
            if not is_in_current_session:
                continue
                
            # 在当前交易时段内，检查是否到了强制平仓时间
            force_close_min = end_min - self.config.FORCE_CLOSE_MINUTES_BEFORE_END
            
            if start_hour < end_hour:
                # 正常时段
                if (current_hour == end_hour and current_minute >= force_close_min) or \
                   (force_close_min < 0 and current_hour == end_hour - 1 and current_minute >= 60 + force_close_min):
                    return True, f"收盘前{self.config.FORCE_CLOSE_MINUTES_BEFORE_END}分钟强制平仓"
            else:
                # 跨天时段（如21:00-02:30）
                if current_hour <= end_hour:
                    # 次日时段（如00:00-02:30）
                    if (current_hour == end_hour and current_minute >= force_close_min) or \
                       (force_close_min < 0 and current_hour == end_hour - 1 and current_minute >= 60 + force_close_min):
                        return True, f"夜盘收盘前{self.config.FORCE_CLOSE_MINUTES_BEFORE_END}分钟强制平仓"
                
        return False, None
    
    def update_trailing_stop(self, current_price):
        """更新移动止损"""
        if self.position.is_empty():
            return
        
        # 计算当前浮盈
        self.position.update_profit(current_price, self.config.CONTRACT_MULTIPLIER)
        floating_profit = self.position.profit
        
        # 阶梯式止盈策略
        for i, threshold in enumerate(self.config.BREAKEVEN_THRESHOLDS):
            if floating_profit >= threshold:
                profit_to_keep = self.config.BREAKEVEN_PROFITS[i]
                
                if profit_to_keep == 0:
                    # 保本（加0.25个点）
                    if self.position.is_long():
                        new_stop = self.position.entry_price + self.config.BREAKEVEN_POINT_OFFSET
                    else:
                        new_stop = self.position.entry_price - self.config.BREAKEVEN_POINT_OFFSET
                else:
                    # 保留部分利润
                    if self.position.is_long():
                        new_stop = self.position.entry_price + profit_to_keep / self.config.CONTRACT_MULTIPLIER
                    else:
                        new_stop = self.position.entry_price - profit_to_keep / self.config.CONTRACT_MULTIPLIER
                
                # 更新止损价（只能向有利方向移动）
                if self.position.is_long():
                    if new_stop > self.position.stop_price:
                        old_stop = self.position.stop_price
                        self.position.stop_price = new_stop
                        Logger.info(f"📈 移动止损更新: {old_stop:.2f} -> {new_stop:.2f} (浮盈{floating_profit:.0f}元，保留{profit_to_keep}元)")
                else:
                    if new_stop < self.position.stop_price:
                        old_stop = self.position.stop_price
                        self.position.stop_price = new_stop
                        Logger.info(f"📉 移动止损更新: {old_stop:.2f} -> {new_stop:.2f} (浮盈{floating_profit:.0f}元，保留{profit_to_keep}元)")
                
                break
    
    def process_tick(self):
        """处理行情数据"""
        try:
            # 获取最新K线
            if not self.main_contract:
                return
                
            klines = self.get_latest_klines(self.main_contract, count=50)
            if klines is None or len(klines) < self.config.WARMUP_PERIOD:
                return
            
            self.data_window = klines
            current_time = datetime.now()
            
            # 更新指标
            self.indicator.update(self.data_window)
            
            # 获取最新价格
            latest = self.data_window.iloc[-1]
            current_price = latest['close']
            
            # 每分钟输出一次K线信息
            if self.last_check_time is None or (current_time - self.last_check_time).total_seconds() >= 60:
                self.last_check_time = current_time
                
                # 获取K线信息
                k_open = latest['open']
                k_high = latest['high']
                k_low = latest['low']
                k_close = latest['close']
                k_color = "红" if k_close >= k_open else "绿"
                
                # 获取动力波指标值
                if self.indicator.vard is not None and self.indicator.vare is not None:
                    vard_val = self.indicator.vard.iloc[-1]
                    vare_val = self.indicator.vare.iloc[-1]
                    bar_height = self.indicator.bar_height.iloc[-1] if self.indicator.bar_height is not None else 0
                    
                    current_color = self.indicator.get_color(-1)
                    color_text = "🔴" if current_color == 'red' else "🟢"
                    
                    # 处理时间格式
                    time_str = self.data_window.index[-1]
                    if isinstance(time_str, str):
                        # 如果是字符串格式，如 '20250819090600'
                        if len(time_str) == 14:
                            time_formatted = f"{time_str[8:10]}:{time_str[10:12]}:{time_str[12:14]}"
                        else:
                            time_formatted = time_str
                    else:
                        # 如果是datetime对象
                        time_formatted = time_str.strftime('%H:%M:%S')
                    
                    Logger.info(f"📈 [{time_formatted}] K线 - 开:{k_open:.2f} 高:{k_high:.2f} 低:{k_low:.2f} 收:{k_close:.2f} ({k_color})")
                    Logger.info(f"📍 动力波 - VARD:{vard_val:.2f} VARE:{vare_val:.2f} 柱高:{bar_height:.2f} {color_text}")
                    
                    # 输出MACD和布林线信息
                    if self.indicator.macd is not None and self.indicator.macd_signal is not None:
                        macd_val = self.indicator.macd.iloc[-1]
                        signal_val = self.indicator.macd_signal.iloc[-1]
                        macd_status = "金叉" if macd_val > signal_val else "死叉"
                        Logger.info(f"📊 MACD - DIF:{macd_val:.3f} DEA:{signal_val:.3f} 状态:{macd_status}")
                    
                    if self.indicator.boll_middle is not None:
                        boll_upper = self.indicator.boll_upper.iloc[-1]
                        boll_middle = self.indicator.boll_middle.iloc[-1]
                        boll_lower = self.indicator.boll_lower.iloc[-1]
                        boll_position = "上轨" if k_close > boll_upper else "中轨上" if k_close > boll_middle else "中轨下" if k_close > boll_lower else "下轨"
                        Logger.info(f"📉 布林线 - 上:{boll_upper:.2f} 中:{boll_middle:.2f} 下:{boll_lower:.2f} 位置:{boll_position}")
                    
                    if self.indicator.percentile is not None:
                        Logger.info(f"📊 百分位: {self.indicator.percentile:.1f}%")
                    
                    # 如果有持仓，输出持仓状态
                    if not self.position.is_empty():
                        self.position.update_profit(current_price, self.config.CONTRACT_MULTIPLIER)
                        direction_text = "多" if self.position.is_long() else "空"
                        Logger.info(f"📊 持仓状态 - 方向: {direction_text}, 开仓价: {self.position.entry_price:.2f}, 当前价: {current_price:.2f}, 盈亏: {self.position.profit:.2f}元")
            
            # 执行信号检查（仍然每个DATA_INTERVAL执行）
            Logger.info(f"执行信号检查 - 时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 1. 检查是否需要强制平仓
            if not self.position.is_empty():
                force_close, force_reason = self.check_force_close(current_time)
                if force_close:
                    self.close_position(current_price, current_time, force_reason)
                    return
            
            # 2. 检查止损条件
            if not self.position.is_empty():
                # 更新盈亏
                self.position.update_profit(current_price, self.config.CONTRACT_MULTIPLIER)
                
                # 检查硬止损
                if self.position.profit <= -self.config.HARD_STOP_LOSS:
                    self.close_position(current_price, current_time, "硬止损")
                    self.last_loss_time = current_time
                    return
                
                # 检查移动止损
                if self.position.is_long() and current_price <= self.position.stop_price:
                    self.close_position(current_price, current_time, "移动止损")
                    self.pending_signal.clear()  # 清除待开仓信号
                    return
                elif self.position.is_short() and current_price >= self.position.stop_price:
                    self.close_position(current_price, current_time, "移动止损")
                    self.pending_signal.clear()  # 清除待开仓信号
                    return
                
                # 更新移动止损
                self.update_trailing_stop(current_price)
            
            # 3. 检查平仓信号（颜色变化）
            if not self.position.is_empty():
                current_color = self.indicator.get_color(-1)
                
                # 检查是否有平仓信号
                should_close = False
                close_reason = ""
                
                if self.position.is_long() and current_color == 'green':
                    should_close = True
                    close_reason = "颜色变绿平多"
                elif self.position.is_short() and current_color == 'red':
                    should_close = True
                    close_reason = "颜色变红平空"
                
                # 如果有平仓信号，先检查是否允许平仓
                if should_close:
                    can_close, reason = self.check_close_conditions(current_time)
                    if can_close:
                        self.close_position(current_price, current_time, close_reason)
                        self.pending_signal.clear()  # 清除待开仓信号
                        return
                    else:
                        Logger.info(f"🔔 检测到平仓信号({close_reason})，但不满足平仓条件: {reason}")
                        # 不平仓，继续持仓
            
            # 4. 检查开仓信号
            if self.position.is_empty():
                can_open, reason = self.check_open_conditions(current_time)
                
                if not can_open:
                    Logger.debug(f"不满足开仓条件: {reason}")
                    # 如果有待开仓信号但在保护期，保留信号
                    if self.pending_signal.active:
                        Logger.debug(f"保留待开仓信号（{'做多' if self.pending_signal.direction == 1 else '做空'}）")
                else:
                    # 检查颜色变化
                    color_change = self.indicator.check_color_change()
                    
                    # 如果有颜色变化，记录待开仓信号
                    if color_change != 0:
                        prev_color = self.indicator.get_color(-2)
                        current_color = self.indicator.get_color(-1)
                        percentile = self.indicator.percentile
                        
                        # 设置待开仓信号（先不检查百分位）
                        self.pending_signal.set_signal(
                            direction=color_change,
                            color_from=prev_color,
                            color_to=current_color,
                            percentile=percentile,
                            time=current_time
                        )
                        
                        Logger.info(f"🔔 检测到颜色变化：{prev_color} -> {current_color}")
                        Logger.info(f"  - 方向: {'做多' if color_change == 1 else '做空'}")
                        Logger.info(f"  - 当前百分位: {percentile:.1f}")
                        Logger.info(f"  等待所有条件满足...")
                    
                    # 如果有待开仓信号，检查是否满足其他条件
                    if self.pending_signal.active:
                        # 增加K线计数
                        if self.pending_signal.increment_bar_count():
                            # 检查颜色是否反转
                            current_color = self.indicator.get_color(-1)
                            if (self.pending_signal.direction == 1 and current_color == 'green') or \
                               (self.pending_signal.direction == -1 and current_color == 'red'):
                                Logger.info(f"颜色反转，清除待开仓信号")
                                self.pending_signal.clear()
                            else:
                                # 检查所有条件
                                all_ok, conditions = self.indicator.check_opening_conditions(self.pending_signal.direction)
                                
                                if all_ok:
                                    # 满足所有条件，执行开仓
                                    direction = self.pending_signal.direction
                                    Logger.info("✅ 所有条件满足，执行开仓")
                                    Logger.info(f"  - 方向: {'做多' if direction == 1 else '做空'}")
                                    Logger.info(f"  - 颜色: {self.pending_signal.color_from} -> {self.pending_signal.color_to} (第{self.pending_signal.bar_count}根K线后)")
                                    
                                    # 输出各条件状态
                                    for cond_name, cond_status in conditions.items():
                                        if cond_status == '已禁用':
                                            Logger.info(f"  - {cond_name}: 已禁用")
                                        elif cond_status:
                                            Logger.info(f"  - {cond_name}: ✓ 满足")
                                        else:
                                            Logger.info(f"  - {cond_name}: × 不满足")
                                    
                                    # 输出具体数值
                                    if self.indicator.percentile is not None:
                                        Logger.info(f"  - 当前百分位值: {self.indicator.percentile:.1f}")
                                    if self.indicator.macd is not None and self.indicator.macd_signal is not None:
                                        Logger.info(f"  - MACD: DIF={self.indicator.macd.iloc[-1]:.3f}, DEA={self.indicator.macd_signal.iloc[-1]:.3f}")
                                    if self.indicator.boll_middle is not None:
                                        Logger.info(f"  - 布林中轨: {self.indicator.boll_middle.iloc[-1]:.2f}, 当前价: {current_price:.2f}")
                                    
                                    if direction == 1:
                                        stop_price = current_price - self.config.HARD_STOP_LOSS_POINTS
                                        self.open_position(1, current_price, current_time, stop_price)
                                    else:
                                        stop_price = current_price + self.config.HARD_STOP_LOSS_POINTS
                                        self.open_position(-1, current_price, current_time, stop_price)
                                    
                                    # 清除待开仓信号
                                    self.pending_signal.clear()
                                else:
                                    # 显示哪些条件未满足
                                    not_satisfied = []
                                    for cond_name, cond_status in conditions.items():
                                        if cond_status != '已禁用' and not cond_status:
                                            not_satisfied.append(cond_name)
                                    
                                    if not_satisfied:
                                        Logger.debug(f"待开仓信号({'做多' if self.pending_signal.direction == 1 else '做空'})等待中，第{self.pending_signal.bar_count}根K线，未满足: {', '.join(not_satisfied)}")
                                    else:
                                        Logger.debug(f"待开仓信号({'做多' if self.pending_signal.direction == 1 else '做空'})等待中，第{self.pending_signal.bar_count}根K线")
                    else:
                        Logger.debug("无有效交易信号")
                        
        except Exception as e:
            Logger.error(f"处理行情数据异常: {e}")
            import traceback
            Logger.debug(traceback.format_exc())
    
    def open_position(self, direction, price, time, stop_price):
        """开仓"""
        self.position.open_position(direction, price, time, stop_price)
        
        # 清除待开仓信号（如果有）
        if self.pending_signal.active:
            self.pending_signal.clear()
        
        direction_text = "多" if direction == 1 else "空"
        
        # 构建播报消息
        current_color = self.indicator.get_color(-1)
        prev_color = self.indicator.get_color(-2)
        
        message_lines = [
            "【动力波信号播报】",
            f"品种：{self.config.PRODUCT_TYPE}  周期：{self.config.KLINE_PERIOD}  时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"上一根颜色：{prev_color}，当前颜色：{current_color}",
            f"满足开仓条件，开仓方向：{direction_text}",
            f"开仓价格：{price:.2f}",
            f"止损价格：{stop_price:.2f}"
        ]
        
        message = "\n".join(message_lines)
        send_message(message, self.config.WECHAT_GROUP)
        Logger.info(f"✅ 开{direction_text}仓成功 - 价格: {price:.2f}, 止损: {stop_price:.2f}")
    
    def close_position(self, price, time, reason):
        """平仓"""
        if self.position.is_empty():
            return
        
        # 计算盈亏
        self.position.update_profit(price, self.config.CONTRACT_MULTIPLIER)
        profit = self.position.profit
        
        # 记录交易
        trade = TradeRecord()
        trade.entry_time = self.position.entry_time
        trade.exit_time = time
        trade.entry_price = self.position.entry_price
        trade.exit_price = price
        trade.direction = self.position.direction
        trade.profit = profit
        trade.exit_reason = reason
        self.trade_history.append(trade)
        
        # 保存到Redis
        self._save_trade_history_to_redis()
        Logger.info(f"交易记录已保存 - 累计交易: {len(self.trade_history)}笔")
        
        # 构建播报消息
        direction_text = "多" if self.position.is_long() else "空"
        profit_text = f"盈利{profit:.0f}元" if profit > 0 else f"亏损{abs(profit):.0f}元"
        
        message_lines = [
            "【动力波信号播报】",
            f"品种：{self.config.PRODUCT_TYPE}  周期：{self.config.KLINE_PERIOD}  时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"开仓价格：{self.position.entry_price:.2f}，当前价格：{price:.2f}",
            f"{reason}，本单{profit_text}"
        ]
        
        message = "\n".join(message_lines)
        send_message(message, self.config.WECHAT_GROUP)
        Logger.info(f"❌ 平{direction_text}仓 - 价格: {price:.2f}, 原因: {reason}, 盈亏: {profit:.0f}元")
        
        # 清空持仓
        self.position.close_position()
    
    def run_loop(self):
        """策略主循环"""
        Logger.info("动力波策略开始运行...")
        
        # 发送启动通知
        try:
            startup_message = f"【动力波策略启动】\n品种：{self.config.PRODUCT_NAME}({self.config.PRODUCT_TYPE})\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            send_message(startup_message, "老公老婆")
        except Exception as e:
            Logger.warning(f"发送启动通知失败: {e}")
        
        # 初始化数据订阅状态
        data_subscribed = False
        wait_stable = False
        stable_start_time = None
        
        while self.running:
            try:
                current_time = datetime.now()
                
                # 检查是否为交易时间
                if self.trading_helper.is_trading_time(current_time):
                    # 首次进入交易时间或每天9点更新主力合约
                    if self.main_contract is None or (current_time.hour == 9 and current_time.minute == 0):
                        self.get_main_contract()
                        data_subscribed = False  # 重置订阅状态
                    
                    # 确保已订阅数据
                    if self.main_contract and not data_subscribed:
                        if self.download_and_subscribe_data(self.main_contract):
                            data_subscribed = True
                            wait_stable = True
                            stable_start_time = current_time
                            
                            # 获取初始K线数据
                            initial_klines = self.get_latest_klines(self.main_contract, count=120)
                            if initial_klines is not None and len(initial_klines) > 0:
                                self.data_window = initial_klines
                                self.indicator.update(self.data_window)
                                
                                # 输出初始状态
                                latest = self.data_window.iloc[-1]
                                k_open = latest['open']
                                k_high = latest['high']
                                k_low = latest['low']
                                k_close = latest['close']
                                k_color = "红" if k_close >= k_open else "绿"
                                
                                # 处理时间格式
                                time_str = self.data_window.index[-1]
                                if isinstance(time_str, str):
                                    # 如果是字符串格式，如 '20250819090600'
                                    if len(time_str) == 14:
                                        time_formatted = f"{time_str[8:10]}:{time_str[10:12]}:{time_str[12:14]}"
                                    else:
                                        time_formatted = time_str
                                else:
                                    # 如果是datetime对象
                                    time_formatted = time_str.strftime('%H:%M:%S')
                                
                                Logger.info(f"📈 [{time_formatted}] K线 - 开:{k_open:.2f} 高:{k_high:.2f} 低:{k_low:.2f} 收:{k_close:.2f} ({k_color})")
                                
                                if self.indicator.vard is not None and self.indicator.vare is not None:
                                    vard_val = self.indicator.vard.iloc[-1]
                                    vare_val = self.indicator.vare.iloc[-1]
                                    bar_height = self.indicator.bar_height.iloc[-1] if self.indicator.bar_height is not None else 0
                                    current_color = self.indicator.get_color(-1)
                                    color_text = "🔴" if current_color == 'red' else "🟢"
                                    
                                    Logger.info(f"📍 动力波 - VARD:{vard_val:.2f} VARE:{vare_val:.2f} 柱高:{bar_height:.2f} {color_text}")
                                    
                                    # 初始化时也输出其他指标
                                    if self.indicator.percentile is not None:
                                        Logger.info(f"📊 百分位: {self.indicator.percentile:.1f}%")
                                
                                Logger.info(f"✅ 数据订阅成功，获取到 {len(initial_klines)} 条K线数据")
                            
                            Logger.info("等待数据推送稳定...")
                    
                    # 等待数据稳定（3秒）
                    if wait_stable and stable_start_time:
                        if (current_time - stable_start_time).total_seconds() >= 3:
                            wait_stable = False
                            Logger.info("✅ 动力波策略启动成功 - 合约: " + self.main_contract)
                            Logger.info("✅ 当前为交易时间，开始监控")
                    
                    # 只有在数据稳定后才处理行情
                    if data_subscribed and not wait_stable:
                        self.process_tick()
                    
                    # 短间隔休眠
                    sleep(self.config.DATA_INTERVAL)
                else:
                    # 非交易时间
                    if data_subscribed:
                        Logger.info("当前为非交易时间，暂停数据监控")
                        data_subscribed = False
                    
                    # 检查是否需要发送报告
                    self.check_performance_report(current_time)
                    
                    # 非交易时间提示
                    Logger.info(f"当前为非交易时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # 长间隔休眠
                    sleep(self.config.LONG_POLL_INTERVAL)
                    
            except Exception as e:
                Logger.error(f"策略运行异常: {e}")
                import traceback
                Logger.error(traceback.format_exc())
                sleep(10)
    
    def check_performance_report(self, current_time):
        """检查是否需要发送绩效报告"""
        try:
            # 日报
            report_hour, report_minute_start, report_minute_end = self.config.DAILY_REPORT_TIME
            if (current_time.hour == report_hour and 
                report_minute_start <= current_time.minute <= report_minute_end):
                
                if self.last_daily_report_date != current_time.date():
                    self.send_daily_report(current_time)
                    self.last_daily_report_date = current_time.date()
            
            # 周报（周五）
            if current_time.weekday() == 4:  # 周五
                report_hour, report_minute_start, report_minute_end = self.config.WEEKLY_REPORT_TIME
                if (current_time.hour == report_hour and 
                    report_minute_start <= current_time.minute <= report_minute_end):
                    
                    week_number = current_time.isocalendar()[1]
                    if self.last_weekly_report_date != (current_time.year, week_number):
                        self.send_weekly_report(current_time)
                        self.last_weekly_report_date = (current_time.year, week_number)
                        
        except Exception as e:
            Logger.error(f"检查绩效报告异常: {e}")
    
    def _save_trade_history_to_redis(self):
        """保存交易历史到Redis"""
        try:
            if not self.redis_client:
                return
                
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
            self.redis_client.setex('power_wave_trade_history', 604800, json.dumps(trade_data))
            Logger.debug(f"交易历史已保存到Redis，共{len(trade_data)}条记录")
        except Exception as e:
            Logger.error(f"保存交易历史到Redis失败: {e}")
    
    def _load_trade_history_from_redis(self):
        """从Redis加载交易历史"""
        try:
            if not self.redis_client:
                return
                
            data = self.redis_client.get('power_wave_trade_history')
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
    
    def send_daily_report(self, current_time):
        """发送日报"""
        try:
            # 获取今天的交易（包括昨晚21:00到今天15:00）
            today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_night_start = (today_start - timedelta(days=1)).replace(hour=21, minute=0, second=0)
            
            # 筛选时间范围内的交易
            daily_trades = []
            for trade in self.trade_history:
                if trade.exit_time and yesterday_night_start <= trade.exit_time <= current_time:
                    daily_trades.append(trade)
            
            # 统计交易信息
            if not daily_trades:
                # 没有交易也要播报
                message_lines = [
                    "【动力波策略每日战绩播报】",
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
                    "【动力波策略每日战绩播报】",
                    f"品种：{self.config.PRODUCT_TYPE}（{self.config.PRODUCT_NAME}） 时间：{current_time.strftime('%Y-%m-%d')}（昨天21:00-今天15:00）"
                ]
                
                profit_loss_line = ""
                if profit_count > 0:
                    profit_loss_line += f"盈利 {profit_count} 笔，单笔最大盈利 {max_profit:.0f} 元"
                if loss_count > 0:
                    if profit_count > 0:
                        profit_loss_line += f"；亏损 {loss_count} 笔，单笔最大亏损 {abs(max_loss):.0f} 元"
                    else:
                        profit_loss_line += f"亏损 {loss_count} 笔，单笔最大亏损 {abs(max_loss):.0f} 元"
                
                if profit_loss_line:
                    message_lines.append(profit_loss_line)
                
                if total_profit >= 0:
                    message_lines.append(f"总盈利 {total_profit:.0f} 元")
                else:
                    message_lines.append(f"总亏损 {total_profit:.0f} 元")
            
            # 添加当前持仓信息
            if not self.position.is_empty():
                direction_text = "多" if self.position.is_long() else "空"
                message_lines.extend([
                    f"",
                    f"📍 当前持仓:",
                    f"方向: {direction_text}",
                    f"开仓价: {self.position.entry_price:.2f}",
                    f"浮动盈亏: {self.position.profit:.0f}元"
                ])
            
            message = "\n".join(message_lines)
            send_message(message, self.config.WECHAT_GROUP)
            Logger.info("日报已发送")
            
        except Exception as e:
            Logger.error(f"发送日报失败: {e}")
    
    def send_weekly_report(self, current_time):
        """发送周报"""
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
                    "【动力波策略每周战绩播报】",
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
                    "【动力波策略每周战绩播报】",
                    f"品种：{self.config.PRODUCT_TYPE}（{self.config.PRODUCT_NAME}） 时间：{last_friday_night.strftime('%Y-%m-%d')} 至 {current_time.strftime('%Y-%m-%d')}"
                ]
                
                profit_loss_line = ""
                if profit_count > 0:
                    profit_loss_line += f"盈利 {profit_count} 笔，单笔最大盈利 {max_profit:.0f} 元"
                if loss_count > 0:
                    if profit_count > 0:
                        profit_loss_line += f"；亏损 {loss_count} 笔，单笔最大亏损 {abs(max_loss):.0f} 元"
                    else:
                        profit_loss_line += f"亏损 {loss_count} 笔，单笔最大亏损 {abs(max_loss):.0f} 元"
                
                if profit_loss_line:
                    message_lines.append(profit_loss_line)
                
                if total_profit >= 0:
                    message_lines.append(f"总盈利 {total_profit:.0f} 元")
                else:
                    message_lines.append(f"总亏损 {total_profit:.0f} 元")
            
            message = "\n".join(message_lines)
            send_message(message, self.config.WECHAT_GROUP)
            Logger.info(f"📊 周报已发送 - 交易数: {len(weekly_trades)}")
            
        except Exception as e:
            Logger.error(f"发送周报失败: {e}")
    
    def start(self):
        """启动策略"""
        if self.running:
            Logger.warning("策略已在运行中")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self.run_loop)
        self.thread.daemon = True
        self.thread.start()
        Logger.info("策略线程启动成功")
    
    def stop(self):
        """停止策略"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        
        # 强制平仓
        if not self.position.is_empty():
            current_time = datetime.now()
            if self.data_window is not None and len(self.data_window) > 0:
                current_price = self.data_window.iloc[-1]['close']
                self.close_position(current_price, current_time, "策略停止强制平仓")
        
        Logger.info("策略已停止")


def main():
    """主函数"""
    # 创建策略实例
    strategy = PowerWaveStrategy()
    
    # 启动策略
    strategy.start()
    
    # 保持程序运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        Logger.info("收到停止信号")
        strategy.stop()


if __name__ == "__main__":
    main()