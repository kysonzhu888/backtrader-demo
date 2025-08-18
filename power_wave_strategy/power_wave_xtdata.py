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
    
    # 强制平仓时间
    FORCE_CLOSE_TIMES = [
        (14, 58),  # 白天收盘前2分钟
        (22, 58),  # 晚上收盘前2分钟（沪金夜盘到02:30，这里设置22:58是为了避免隔夜）
    ]
    
    # 微信播报
    WECHAT_GROUP = "动力波策略群"
    
    # 绩效报告配置
    DAILY_REPORT_TIME = (15, 0, 1)  # 日报时间
    WEEKLY_REPORT_TIME = (15, 5, 6)  # 周报时间
    SHORT_POLL_INTERVAL = 60  # 短间隔：60秒
    LONG_POLL_INTERVAL = 1800  # 长间隔：30分钟
    
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
    
    def get_signal(self, data_window):
        """获取交易信号"""
        if len(data_window) < self.config.WARMUP_PERIOD:
            return 0
            
        # 检查颜色变化
        current_color = self.get_color(-1)
        prev_color = self.get_color(-2)
        
        if prev_color is None or current_color is None:
            return 0
        
        # 绿变红 - 做多信号
        if prev_color == 'green' and current_color == 'red':
            return 1
        
        # 红变绿 - 做空信号  
        if prev_color == 'red' and current_color == 'green':
            return -1
            
        return 0


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
                db=environment.REDIS_DB,  # 修正属性名
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
        self.trade_history = []
        self.last_loss_time = None
        
        # 数据缓存
        self.main_contract = None
        self.data_window = pd.DataFrame()
        self.last_update_time = None
        
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
            for code in codes:
                # 去掉交易所后缀后判断
                code_without_exchange = code.split('.')[0] if '.' in code else code
                # 判断是否为目标品种（沪金的代码是au，不是AU）
                if code_without_exchange.lower().startswith(self.config.PRODUCT_TYPE.lower()):
                    # 排除期权合约
                    if not self._is_option_contract(code):
                        futures.append(code)
            
            Logger.info(f"{self.config.PRODUCT_NAME}期货合约数: {len(futures)}个")
            
            if not futures:
                Logger.error(f"未找到{self.config.PRODUCT_NAME}期货合约")
                return None
            
            # 获取实时行情判断主力
            field_list = ['volume', 'amount']
            data = xtdata.get_full_tick(futures)
            
            # 找出成交量最大的合约
            max_volume = 0
            main_contract = None
            
            for code in futures:
                if code in data:
                    volume = data[code].get('volume', 0)
                    if volume > max_volume:
                        max_volume = volume
                        main_contract = code
            
            if main_contract:
                Logger.info(f"选定主力合约: {main_contract}, 成交量: {max_volume}")
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
    
    def download_history_data(self, contract_code):
        """下载历史数据"""
        try:
            # 计算时间范围
            end_time = datetime.now()
            start_time = end_time - timedelta(days=1)  # 获取1天的数据
            
            # 下载历史数据
            xtdata.download_history_data(
                stock_code=contract_code,
                period='1m',
                start_time=start_time.strftime('%Y%m%d%H%M%S'),
                end_time=end_time.strftime('%Y%m%d%H%M%S')
            )
            
            Logger.info(f"历史数据下载完成: {contract_code}")
            return True
            
        except Exception as e:
            Logger.error(f"下载历史数据失败: {e}")
            return False
    
    def get_latest_klines(self, contract_code, count=50):
        """获取最新K线数据"""
        try:
            # 获取1分钟K线数据
            data = xtdata.get_market_data_ex(
                stock_list=[contract_code],
                period='1m',
                count=count
            )
            
            if not data or contract_code not in data:
                return None
            
            df = data[contract_code]
            
            # 转换为标准格式
            df_formatted = pd.DataFrame({
                'time': df.index,
                'open': df['open'],
                'high': df['high'],
                'low': df['low'],
                'close': df['close'],
                'volume': df['volume']
            })
            
            df_formatted.set_index('time', inplace=True)
            return df_formatted
            
        except Exception as e:
            Logger.error(f"获取K线数据失败: {e}")
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
        time_val = current_hour * 100 + current_minute
        
        # 开盘后保护
        if self.config.NO_OPEN_MINUTES_AFTER_MORNING_OPEN > 0:
            if 900 <= time_val < (900 + self.config.NO_OPEN_MINUTES_AFTER_MORNING_OPEN):
                minutes_left = 900 + self.config.NO_OPEN_MINUTES_AFTER_MORNING_OPEN - time_val
                return False, f"早盘开盘后保护期，剩余{minutes_left}分钟"
        
        # 夜盘开盘后保护
        if self.config.NO_OPEN_MINUTES_AFTER_NIGHT_OPEN > 0:
            if 2100 <= time_val < (2100 + self.config.NO_OPEN_MINUTES_AFTER_NIGHT_OPEN):
                minutes_left = 2100 + self.config.NO_OPEN_MINUTES_AFTER_NIGHT_OPEN - time_val
                return False, f"夜盘开盘后保护期，剩余{minutes_left}分钟"
        
        # 止损后保护
        if self.last_loss_time:
            time_since_loss = (current_time - self.last_loss_time).total_seconds() / 60
            if time_since_loss < self.config.NO_OPEN_MINUTES_AFTER_LOSS:
                minutes_left = self.config.NO_OPEN_MINUTES_AFTER_LOSS - time_since_loss
                return False, f"止损后保护期，剩余{minutes_left:.0f}分钟"
        
        return True, "允许开仓"
    
    def check_force_close(self, current_time):
        """检查是否需要强制平仓"""
        if self.position.is_empty():
            return False, None
            
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        for close_hour, close_minute in self.config.FORCE_CLOSE_TIMES:
            # 检查是否到强制平仓时间
            if current_hour == close_hour and current_minute >= close_minute:
                return True, "收盘前强制平仓"
                
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
                    self.position.stop_price = max(self.position.stop_price, new_stop)
                else:
                    self.position.stop_price = min(self.position.stop_price, new_stop)
                
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
                    return
                elif self.position.is_short() and current_price >= self.position.stop_price:
                    self.close_position(current_price, current_time, "移动止损")
                    return
                
                # 更新移动止损
                self.update_trailing_stop(current_price)
            
            # 3. 检查平仓信号（颜色变化）
            if not self.position.is_empty():
                current_color = self.indicator.get_color(-1)
                
                if self.position.is_long() and current_color == 'green':
                    self.close_position(current_price, current_time, "颜色变绿平多")
                    return
                elif self.position.is_short() and current_color == 'red':
                    self.close_position(current_price, current_time, "颜色变红平空")
                    return
            
            # 4. 检查开仓信号
            if self.position.is_empty():
                can_open, reason = self.check_open_conditions(current_time)
                if can_open:
                    signal = self.indicator.get_signal(self.data_window)
                    
                    if signal == 1:  # 做多信号
                        stop_price = current_price - self.config.HARD_STOP_LOSS_POINTS
                        self.open_position(1, current_price, current_time, stop_price)
                    elif signal == -1:  # 做空信号
                        stop_price = current_price + self.config.HARD_STOP_LOSS_POINTS
                        self.open_position(-1, current_price, current_time, stop_price)
                        
        except Exception as e:
            Logger.error(f"处理行情数据异常: {e}")
    
    def open_position(self, direction, price, time, stop_price):
        """开仓"""
        self.position.open_position(direction, price, time, stop_price)
        
        direction_text = "多" if direction == 1 else "空"
        
        # 构建播报消息
        current_color = self.indicator.get_color(-1)
        prev_color = self.indicator.get_color(-2)
        
        message_lines = [
            "【动力波信号播报】",
            f"品种：{self.config.PRODUCT_TYPE}  周期：{self.config.KLINE_PERIOD}  时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"上一根颜色：{prev_color}，当前颜色：{current_color}",
            f"满足开仓条件，开仓方向：{direction_text}",
            f"开仓价格：{price:.2f}"
        ]
        
        message = "\n".join(message_lines)
        send_message(message, self.config.WECHAT_GROUP)
        Logger.info(f"开{direction_text}仓 - 价格: {price:.2f}, 止损: {stop_price:.2f}")
    
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
        
        # 构建播报消息
        direction_text = "多" if self.position.is_long() else "空"
        profit_text = f"盈利{profit:.0f}元" if profit > 0 else f"亏损{profit:.0f}元"
        
        message_lines = [
            "【动力波信号播报】",
            f"品种：{self.config.PRODUCT_TYPE}  周期：{self.config.KLINE_PERIOD}  时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"开仓价格：{self.position.entry_price:.2f}，当前价格：{price:.2f}",
            f"{reason}，本单{profit_text}"
        ]
        
        message = "\n".join(message_lines)
        send_message(message, self.config.WECHAT_GROUP)
        Logger.info(f"平{direction_text}仓 - 价格: {price:.2f}, 原因: {reason}, 盈亏: {profit:.0f}")
        
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
        
        while self.running:
            try:
                current_time = datetime.now()
                
                # 检查是否为交易时间
                if self.trading_helper.is_trading_time(current_time):
                    # 更新主力合约（每天更新一次）
                    if self.main_contract is None or current_time.hour == 9 and current_time.minute == 0:
                        self.get_main_contract()
                        if self.main_contract:
                            self.download_history_data(self.main_contract)
                    
                    # 处理行情
                    self.process_tick()
                    
                    # 短间隔休眠
                    sleep(self.config.DATA_INTERVAL)
                else:
                    # 非交易时间，检查是否需要发送报告
                    self.check_performance_report(current_time)
                    
                    # 长间隔休眠
                    sleep(self.config.LONG_POLL_INTERVAL)
                    
            except Exception as e:
                Logger.error(f"策略运行异常: {e}")
                sleep(10)
    
    def check_performance_report(self, current_time):
        """检查是否需要发送绩效报告"""
        # TODO: 实现日报和周报功能
        pass
    
    def start(self):
        """启动策略"""
        if self.running:
            Logger.warning("策略已在运行中")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self.run_loop)
        self.thread.daemon = True
        self.thread.start()
        Logger.info("策略启动成功")
    
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