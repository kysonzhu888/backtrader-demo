#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
微信队列监控工具
用于查看和调试微信窗口队列状态
"""

import time
from utils.wechat_queue_manager import (
    get_wechat_queue_status, 
    get_wechat_queue_stats,
    reset_wechat_queue_stats
)
from utils.logger_utils import Logger


def print_queue_status():
    """打印当前队列状态"""
    status = get_wechat_queue_status()
    stats = get_wechat_queue_stats()
    
    print("\n" + "="*60)
    print("微信队列管理器状态")
    print("="*60)
    
    # 基本状态
    print(f"可用许可数: {status['available_permits']}")
    print(f"队列大小: {status['queue_size']}")
    
    # 当前操作
    current_op = status['current_operation']
    if current_op['thread_name']:
        print(f"\n当前操作:")
        print(f"  线程: {current_op['thread_name']}")
        print(f"  操作类型: {current_op['operation_type']}")
        print(f"  接收者: {current_op['recipient']}")
        if current_op['start_time']:
            duration = time.time() - current_op['start_time']
            print(f"  已执行时长: {duration:.2f}秒")
    else:
        print(f"\n当前操作: 无")
    
    # 统计信息
    print(f"\n统计信息:")
    print(f"  总操作数: {stats['total_operations']}")
    print(f"  成功率: {stats['success_rate']}")
    print(f"  平均等待时间: {stats['average_wait_time']}")
    print(f"  最大等待时间: {stats['max_wait_time']}")
    
    # 最近操作
    recent_ops = status['recent_operations']
    if recent_ops:
        print(f"\n最近操作 (最新{len(recent_ops)}条):")
        for i, op in enumerate(reversed(recent_ops), 1):
            timestamp = time.strftime("%H:%M:%S", time.localtime(op['timestamp']))
            status_icon = "✓" if op['success'] else "✗"
            print(f"  {i}. [{timestamp}] {status_icon} {op['thread_name']} - {op['operation_type']} - {op['recipient']} (等待:{op['wait_time']:.2f}s)")
    
    print("="*60)


def monitor_queue(interval=5, duration=300):
    """
    持续监控队列状态
    
    Args:
        interval: 监控间隔（秒）
        duration: 监控持续时间（秒）
    """
    Logger.info(f"开始监控微信队列状态，间隔{interval}秒，持续{duration}秒...")
    
    start_time = time.time()
    
    try:
        while True:
            current_time = time.time()
            if current_time - start_time > duration:
                break
                
            print_queue_status()
            time.sleep(interval)
            
    except KeyboardInterrupt:
        Logger.info("监控被用户中断")
    
    Logger.info("队列监控结束")


def reset_stats():
    """重置统计信息"""
    reset_wechat_queue_stats()
    Logger.info("微信队列统计信息已重置")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "status":
            print_queue_status()
        elif command == "monitor":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            duration = int(sys.argv[3]) if len(sys.argv) > 3 else 300
            monitor_queue(interval, duration)
        elif command == "reset":
            reset_stats()
        else:
            print("用法:")
            print("  python wechat_queue_monitor.py status     # 查看当前状态")
            print("  python wechat_queue_monitor.py monitor [间隔] [持续时间]  # 持续监控")
            print("  python wechat_queue_monitor.py reset      # 重置统计")
    else:
        print_queue_status()