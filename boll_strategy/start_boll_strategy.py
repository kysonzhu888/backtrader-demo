#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
布林线策略启动脚本
可以作为独立进程运行，也可以被daemon.py管理
"""

import os
import sys
import time
import signal
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from boll_strategy import BollStrategy
from utils.logger_utils import Logger

def signal_handler(signum, frame):
    """信号处理器"""
    Logger.info("接收到终止信号，正在关闭布林线策略...")
    global strategy
    if strategy:
        strategy.stop()
    sys.exit(0)

def main():
    """主函数"""
    global strategy
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    Logger.info("=" * 50)
    Logger.info("布林线策略启动中...")
    Logger.info(f"启动时间: {datetime.now()}")
    Logger.info("=" * 50)
    
    try:
        # 创建并启动策略
        strategy = BollStrategy()
        strategy.start()
        
    except Exception as e:
        Logger.error(f"布林线策略运行异常: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)