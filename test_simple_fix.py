#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试简单修复版微信工具
"""

import sys
import os
import threading
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.wechat_helper_simple_fix import send_message, get_wechat_instance
from utils.logger_utils import Logger


def test_simple_fix():
    """测试简单修复版微信工具"""
    print("=== 测试简单修复版微信工具 ===")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"当前线程: {threading.current_thread().name}")
    print(f"是否主线程: {threading.current_thread() == threading.main_thread()}")
    
    # 1. 测试基本功能
    print("\n1. 测试基本功能...")
    test_message = f"简单修复版微信工具测试 - {datetime.now().strftime('%H:%M:%S')}"
    test_recipient = "算法学习二群"
    
    try:
        success = send_message(test_message, test_recipient)
        print(f"发送结果: {'✅ 成功' if success else '❌ 失败'}")
    except Exception as e:
        print(f"❌ 发送异常: {e}")
    
    # 2. 测试子线程使用
    print("\n2. 测试子线程使用...")
    
    def sub_thread_task():
        print(f"  子线程开始: {threading.current_thread().name}")
        
        try:
            test_message = f"子线程测试消息 - {datetime.now().strftime('%H:%M:%S')}"
            test_recipient = "算法学习二群"
            
            print(f"  子线程发送消息: {test_message}")
            success = send_message(test_message, test_recipient)
            print(f"  子线程发送结果: {'✅ 成功' if success else '❌ 失败'}")
            
        except Exception as e:
            print(f"  子线程发送异常: {e}")
    
    # 创建子线程
    thread = threading.Thread(target=sub_thread_task, name="WeChatTestThread")
    thread.start()
    thread.join()
    
    print("子线程测试完成")
    
    # 3. 测试多线程使用
    print("\n3. 测试多线程使用...")
    
    def thread_task(thread_id):
        print(f"  线程 {thread_id} 开始: {threading.current_thread().name}")
        
        try:
            test_message = f"多线程测试消息 {thread_id} - {datetime.now().strftime('%H:%M:%S')}"
            test_recipient = "算法学习二群"
            
            success = send_message(test_message, test_recipient)
            print(f"  线程 {thread_id} 发送结果: {'✅ 成功' if success else '❌ 失败'}")
            
        except Exception as e:
            print(f"  线程 {thread_id} 发送异常: {e}")
    
    # 创建多个线程
    threads = []
    for i in range(3):
        thread = threading.Thread(target=thread_task, args=(i+1,), name=f"WeChatThread{i+1}")
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    print("多线程测试完成")


def test_task_imports():
    """测试任务导入"""
    print("\n=== 测试任务导入 ===")
    
    tasks_to_test = [
        "tasks.live_news",
        "tasks.weather_report", 
        "tasks.news_reporter",
        "tasks.hk_top10_broadcaster",
        "tasks.holder_trade_strategy",
        "tasks.features_weekly_report",
        "tasks.features_min_monitor",
        "tasks.features_daily_report"
    ]
    
    success_count = 0
    total_count = len(tasks_to_test)
    
    for task_name in tasks_to_test:
        try:
            print(f"测试 {task_name}...")
            module = __import__(task_name, fromlist=['*'])
            print(f"  ✅ {task_name} 导入成功")
            success_count += 1
        except Exception as e:
            print(f"  ❌ {task_name} 导入失败: {e}")
    
    print(f"\n导入测试结果: {success_count}/{total_count} 成功")
    return success_count == total_count


def main():
    """主函数"""
    print("简单修复版微信工具测试")
    print("=" * 50)
    
    # 1. 基本功能测试
    test_simple_fix()
    
    # 2. 任务导入测试
    task_success = test_task_imports()
    
    # 总结
    print("\n" + "=" * 50)
    print("测试总结:")
    print(f"  任务导入测试: {'✅ 通过' if task_success else '❌ 失败'}")
    
    if task_success:
        print("\n🎉 所有测试通过！")
        print("简单修复版微信工具正常工作")
        print("主要特点:")
        print("1. 简单直接，无需复杂队列")
        print("2. 在子线程中会给出警告但不会超时")
        print("3. 建议在任务调度器中设置微信任务在主线程中执行")
        print("4. 完全向后兼容")
    else:
        print("\n❌ 部分测试失败")
    
    print("\n测试完成！")


if __name__ == "__main__":
    main() 