#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
微信进程锁监控工具
用于查看和调试微信进程锁状态
"""

import time
import os
from utils.wechat_process_lock import (
    get_wechat_lock_stats,
    reset_wechat_lock_stats,
    is_wechat_locked,
    get_wechat_lock_info,
    acquire_wechat_process_lock
)
from utils.logger_utils import Logger


def print_lock_status():
    """打印当前锁状态"""
    stats = get_wechat_lock_stats()
    is_locked = is_wechat_locked()
    lock_info = get_wechat_lock_info()
    
    print("\n" + "="*60)
    print("微信进程锁状态")
    print("="*60)
    
    # 基本状态
    print(f"当前状态: {'🔒 被占用' if is_locked else '🔓 可用'}")
    print(f"锁文件: {stats['lock_file']}")
    
    if is_locked:
        print(f"锁信息: {lock_info}")
    
    # 统计信息
    print(f"\n📊 统计信息:")
    print(f"  总尝试次数: {stats['total_attempts']}")
    print(f"  成功获取锁: {stats['successful_locks']}")
    print(f"  超时失败: {stats['timeout_failures']}")
    print(f"  成功率: {stats['success_rate']}")
    print(f"  平均等待时间: {stats['average_wait_time']}")
    print(f"  最大等待时间: {stats['max_wait_time']}")
    
    print("="*60)


def monitor_lock(interval=3, duration=300):
    """
    持续监控锁状态
    
    Args:
        interval: 监控间隔（秒）
        duration: 监控持续时间（秒）
    """
    Logger.info(f"开始监控微信进程锁状态，间隔{interval}秒，持续{duration}秒...")
    
    start_time = time.time()
    
    try:
        while True:
            current_time = time.time()
            if current_time - start_time > duration:
                break
                
            print_lock_status()
            time.sleep(interval)
            
    except KeyboardInterrupt:
        Logger.info("监控被用户中断")
    
    Logger.info("锁监控结束")


def test_lock_mechanism(test_duration=10, process_count=3):
    """
    测试锁机制 - 启动多个子进程测试
    
    Args:
        test_duration: 测试持续时间（秒）
        process_count: 子进程数量
    """
    import subprocess
    import sys
    
    Logger.info(f"启动锁机制测试，{process_count}个进程，持续{test_duration}秒...")
    
    processes = []
    
    try:
        # 启动子进程
        for i in range(process_count):
            cmd = [
                sys.executable, __file__, "test_worker", str(i), str(test_duration)
            ]
            process = subprocess.Popen(cmd)
            processes.append(process)
            Logger.info(f"启动测试进程 {i}: PID {process.pid}")
        
        # 等待所有进程结束
        for i, process in enumerate(processes):
            process.wait()
            Logger.info(f"测试进程 {i} 已结束")
    
    except KeyboardInterrupt:
        Logger.info("测试被中断，正在终止子进程...")
        for process in processes:
            process.terminate()
    
    Logger.info("锁机制测试完成")
    print_lock_status()


def test_worker(worker_id, duration):
    """测试工作进程"""
    Logger.info(f"测试工作进程 {worker_id} 开始 (PID: {os.getpid()})")
    
    end_time = time.time() + int(duration)
    operation_count = 0
    
    while time.time() < end_time:
        try:
            # 模拟微信发送操作
            with acquire_wechat_process_lock('test_send', f'测试接收者{worker_id}', timeout=30):
                operation_count += 1
                Logger.info(f"[Worker{worker_id}] 执行第{operation_count}次操作")
                
                # 模拟微信操作耗时
                time.sleep(1 + (worker_id * 0.5))  # 不同进程有不同的操作耗时
                
        except TimeoutError as e:
            Logger.error(f"[Worker{worker_id}] 操作超时: {e}")
        except Exception as e:
            Logger.error(f"[Worker{worker_id}] 操作异常: {e}")
        
        # 等待一段时间再进行下一次操作
        time.sleep(2)
    
    Logger.info(f"测试工作进程 {worker_id} 结束，共执行 {operation_count} 次操作")


def reset_stats():
    """重置统计信息"""
    reset_wechat_lock_stats()
    Logger.info("微信进程锁统计信息已重置")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "status":
            print_lock_status()
            
        elif command == "monitor":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 3
            duration = int(sys.argv[3]) if len(sys.argv) > 3 else 300
            monitor_lock(interval, duration)
            
        elif command == "test":
            duration = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            processes = int(sys.argv[3]) if len(sys.argv) > 3 else 3
            test_lock_mechanism(duration, processes)
            
        elif command == "test_worker":
            # 内部使用，不对外暴露
            worker_id = sys.argv[2]
            duration = sys.argv[3]
            test_worker(worker_id, duration)
            
        elif command == "reset":
            reset_stats()
            
        else:
            print("用法:")
            print("  python wechat_lock_monitor.py status                    # 查看当前状态")
            print("  python wechat_lock_monitor.py monitor [间隔] [持续时间]   # 持续监控")
            print("  python wechat_lock_monitor.py test [持续时间] [进程数]     # 测试锁机制")
            print("  python wechat_lock_monitor.py reset                     # 重置统计")
    else:
        print_lock_status()