#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
动力波策略主入口
版本: V3.0
数据源: xtdata
"""

import os
import sys
import time
import signal
import threading
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger_utils import Logger
from power_wave_strategy import PowerWaveStrategy, PowerWaveConfig


# 全局变量用于优雅退出
strategy_instance = None
shutdown_event = threading.Event()

def signal_handler(signum, frame):
    """信号处理函数"""
    global strategy_instance, shutdown_event
    Logger.info(f"\n收到信号 {signum}，正在安全退出...")
    shutdown_event.set()
    if strategy_instance:
        try:
            strategy_instance.stop()
        except Exception as e:
            Logger.error(f"停止策略时出错: {e}")
    sys.exit(0)

def main():
    """主函数"""
    global strategy_instance, shutdown_event
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, signal_handler)  # Windows
    
    try:
        # 打印启动横幅
        print("="*60)
        print("🚀 动力波策略正在启动...")
        print("="*60)
        
        # 输出策略版本信息
        Logger.info("策略版本: V3.0")
        
        # 创建配置（默认使用沪金，可通过参数修改）
        config = PowerWaveConfig()
        
        # 如果需要使用其他品种，可以这样配置：
        # config.update_product(
        #     product_type='rb',  # 螺纹钢
        #     product_name='螺纹钢',
        #     multiplier=10,
        #     exchange='SF'
        # )
        
        # 如果需要修改开仓条件，可以这样配置：
        # config.USE_PERCENTILE_CONDITION = True   # 启用百分位条件
        # config.USE_MACD_CONDITION = False        # 禁用MACD条件
        # config.USE_BOLL_CONDITION = True         # 启用布林线条件
        
        # 输出配置信息
        Logger.info(f"交易品种: {config.PRODUCT_NAME}({config.PRODUCT_TYPE.upper()})")
        Logger.info(f"动力波参数: {config.POWER_WAVE_HL_PERIOD}周期高低点, EMA({config.POWER_WAVE_EMA1_PERIOD},{config.POWER_WAVE_EMA2_PERIOD})")
        Logger.info(f"布林线参数: {config.BOLL_PERIOD}周期, {config.BOLL_STD}倍标准差")
        Logger.info(f"风控参数: 硬止损{config.HARD_STOP_LOSS}元")
        Logger.info(f"阶梯止盈阈值: {config.BREAKEVEN_THRESHOLDS}")
        Logger.info(f"阶梯止盈保留: {config.BREAKEVEN_PROFITS}")
        Logger.info("开仓条件配置:")
        Logger.info("  1. 动力波颜色变化（必须）")
        Logger.info(f"  2. 百分位条件（<25%做多，>75%做空）: {'启用' if config.USE_PERCENTILE_CONDITION else '禁用'}")
        Logger.info(f"  3. MACD条件（金叉/死叉）: {'启用' if config.USE_MACD_CONDITION else '禁用'}")
        Logger.info(f"  4. 布林线条件（中轨位置）: {'启用' if config.USE_BOLL_CONDITION else '禁用'}")
        Logger.info("保护期设置:")
        Logger.info(f"  - 早盘开盘后: {config.NO_OPEN_MINUTES_AFTER_MORNING_OPEN}分钟")
        Logger.info(f"  - 夜盘开盘后: {config.NO_OPEN_MINUTES_AFTER_NIGHT_OPEN}分钟")
        Logger.info(f"  - 收盘前: {config.NO_OPEN_MINUTES_BEFORE_CLOSE}分钟")
        Logger.info(f"  - 止损后: {config.NO_OPEN_MINUTES_AFTER_LOSS}分钟")
        Logger.info("（提示：将任意保护时间设为0可关闭对应保护）")
        print("="*60)
        
        # 创建策略实例
        strategy_instance = PowerWaveStrategy(config)
        
        # 启动策略
        strategy_instance.start()
        
        # 保持程序运行
        Logger.info("✅ 动力波策略启动成功，等待交易信号...")
        
        # 使用Event等待，而不是无限循环
        while not shutdown_event.is_set():
            time.sleep(1)
            # 检查策略是否还在运行
            if strategy_instance and hasattr(strategy_instance, 'running'):
                if not strategy_instance.running:
                    Logger.warning("策略已停止运行，准备退出...")
                    break
            
    except KeyboardInterrupt:
        Logger.info("\n收到停止信号，正在安全退出...")
        shutdown_event.set()
        if strategy_instance:
            strategy_instance.stop()
        Logger.info("策略已安全停止")
        
    except Exception as e:
        Logger.error(f"策略运行异常: {e}")
        import traceback
        Logger.error(traceback.format_exc())
        if strategy_instance:
            try:
                strategy_instance.stop()
            except:
                pass
        # 返回非零退出码，让daemon知道进程异常退出
        sys.exit(1)
    
    finally:
        Logger.info("动力波策略进程退出")
        # 确保正常退出
        sys.exit(0)


if __name__ == "__main__":
    main()
