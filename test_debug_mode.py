#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试任务调度器的调试模式
"""

import os
from task_scheduler import get_all_task_status, get_task_scheduler

def test_debug_mode():
    """测试调试模式"""
    print("=== 测试任务调度器调试模式 ===")
    
    # 设置调试模式
    os.environ['DEBUG_MODE'] = '1'
    
    # 重新初始化调度器（确保调试模式生效）
    scheduler = get_task_scheduler()
    
    # 获取任务状态
    status_list = get_all_task_status()
    
    print(f"总任务数: {len(status_list)}")
    print("\n调试模式下的任务状态:")
    
    for status in status_list[:5]:  # 显示前5个任务
        print(f"  {status['name']}: {status['delay_seconds']:.1f}秒后执行")
        print(f"    描述: {status['description']}")
        print(f"    启用: {status['enabled']}")
        print()
    
    # 检查是否所有任务都使用3秒延迟
    all_3_seconds = all(s['delay_seconds'] == 3.0 for s in status_list if s['enabled'])
    
    if all_3_seconds:
        print("✅ 调试模式工作正常 - 所有任务都将在3秒后执行")
    else:
        print("❌ 调试模式有问题 - 部分任务延迟时间不是3秒")
    
    return all_3_seconds

def test_normal_mode():
    """测试正常模式"""
    print("\n=== 测试正常模式 ===")
    
    # 清除调试模式
    if 'DEBUG_MODE' in os.environ:
        del os.environ['DEBUG_MODE']
    
    # 重新初始化调度器
    scheduler = get_task_scheduler()
    
    # 获取任务状态
    status_list = get_all_task_status()
    
    print("正常模式下的任务状态（前3个）:")
    for status in status_list[:3]:
        print(f"  {status['name']}: {status['delay_seconds']:.1f}秒后执行")
        print(f"    下次执行时间: {status['next_run']}")
        print()

if __name__ == "__main__":
    # 测试调试模式
    debug_ok = test_debug_mode()
    
    # 测试正常模式
    test_normal_mode()
    
    print("=== 测试总结 ===")
    if debug_ok:
        print("✅ 调试模式功能正常")
        print("✅ 可以通过设置 DEBUG_MODE=1 环境变量启用调试模式")
        print("✅ 调试模式下所有任务将在3秒后执行")
    else:
        print("❌ 调试模式有问题，需要检查") 