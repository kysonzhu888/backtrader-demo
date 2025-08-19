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
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger_utils import Logger
from power_wave_strategy.power_wave_strategy import PowerWaveStrategy, PowerWaveConfig


def main():
    """主函数"""
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
        
        # 输出配置信息
        Logger.info(f"交易品种: {config.PRODUCT_NAME}({config.PRODUCT_TYPE.upper()})")
        Logger.info(f"动力波参数: {config.POWER_WAVE_HL_PERIOD}周期高低点, EMA({config.POWER_WAVE_EMA1_PERIOD},{config.POWER_WAVE_EMA2_PERIOD})")
        Logger.info(f"风控参数: 硬止损{config.HARD_STOP_LOSS}元")
        Logger.info(f"阶梯止盈阈值: {config.BREAKEVEN_THRESHOLDS}")
        Logger.info(f"阶梯止盈保留: {config.BREAKEVEN_PROFITS}")
        Logger.info("开仓条件:")
        Logger.info("  1. 动力波颜色变化（红绿切换）")
        Logger.info("  2. MACD金叉/死叉确认")
        Logger.info("  3. 价格与布林线中轨关系")
        Logger.info("  4. 百分位条件（<25%做多，>75%做空）")
        Logger.info("保护期设置:")
        Logger.info(f"  - 早盘开盘后: {config.NO_OPEN_MINUTES_AFTER_MORNING_OPEN}分钟")
        Logger.info(f"  - 夜盘开盘后: {config.NO_OPEN_MINUTES_AFTER_NIGHT_OPEN}分钟")
        Logger.info(f"  - 收盘前: {config.NO_OPEN_MINUTES_BEFORE_CLOSE}分钟")
        Logger.info(f"  - 止损后: {config.NO_OPEN_MINUTES_AFTER_LOSS}分钟")
        Logger.info("（提示：将任意保护时间设为0可关闭对应保护）")
        print("="*60)
        
        # 创建策略实例
        strategy = PowerWaveStrategy(config)
        
        # 启动策略
        strategy.start()
        
        # 保持程序运行
        Logger.info("✅ 动力波策略启动成功，等待交易信号...")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        Logger.info("\n收到停止信号，正在安全退出...")
        if 'strategy' in locals():
            strategy.stop()
        Logger.info("策略已安全停止")
        
    except Exception as e:
        Logger.error(f"策略运行异常: {e}")
        import traceback
        Logger.error(traceback.format_exc())
        if 'strategy' in locals():
            strategy.stop()


if __name__ == "__main__":
    main()
