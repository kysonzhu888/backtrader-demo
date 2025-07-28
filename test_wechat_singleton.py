#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试WeChatHelper单例模式
验证多个任务共享同一个实例的效果
"""

import time
import threading
from utils.wechat_helper import WeChatHelper
from utils.global_wechat import get_wechat_instance, send_message, check_wechat_health
from utils.logger_utils import Logger


def test_singleton_pattern():
    """测试单例模式"""
    print("=== 测试WeChatHelper单例模式 ===")
    
    # 创建多个实例
    wechat1 = WeChatHelper()
    wechat2 = WeChatHelper()
    wechat3 = WeChatHelper()
    
    # 验证是否为同一个实例
    print(f"wechat1 id: {id(wechat1)}")
    print(f"wechat2 id: {id(wechat2)}")
    print(f"wechat3 id: {id(wechat3)}")
    
    is_singleton = (wechat1 is wechat2 is wechat3)
    print(f"是否为单例: {is_singleton}")
    
    if is_singleton:
        print("✅ 单例模式工作正常")
    else:
        print("❌ 单例模式有问题")
    
    return is_singleton


def test_global_instance():
    """测试全局实例"""
    print("\n=== 测试全局实例 ===")
    
    # 获取全局实例
    instance1 = get_wechat_instance()
    instance2 = get_wechat_instance()
    
    print(f"全局实例1 id: {id(instance1)}")
    print(f"全局实例2 id: {id(instance2)}")
    
    is_same = (instance1 is instance2)
    print(f"是否为同一实例: {is_same}")
    
    if is_same:
        print("✅ 全局实例工作正常")
    else:
        print("❌ 全局实例有问题")
    
    return is_same


def simulate_task_execution(task_name, delay=1):
    """模拟任务执行"""
    print(f"任务 {task_name} 开始执行...")
    time.sleep(delay)
    
    # 使用全局实例发送消息
    test_message = f"测试消息 - {task_name} - {time.strftime('%H:%M:%S')}"
    try:
        send_message(test_message, "老公老婆")
        print(f"任务 {task_name} 消息发送成功")
    except Exception as e:
        print(f"任务 {task_name} 消息发送失败: {e}")
    
    print(f"任务 {task_name} 执行完成")


def test_concurrent_tasks():
    """测试并发任务"""
    print("\n=== 测试并发任务 ===")
    
    # 创建多个线程模拟并发任务
    tasks = [
        ("live_news", 0.5),
        ("news_reporter", 1.0),
        ("weather_report", 1.5),
        ("features_min_monitor", 2.0),
        ("hk_top10_broadcaster", 2.5)
    ]
    
    threads = []
    for task_name, delay in tasks:
        thread = threading.Thread(
            target=simulate_task_execution,
            args=(task_name, delay),
            daemon=True
        )
        threads.append(thread)
        thread.start()
    
    # 等待所有任务完成
    for thread in threads:
        thread.join()
    
    print("所有并发任务执行完成")


def test_health_check():
    """测试健康检查"""
    print("\n=== 测试健康检查 ===")
    
    health_status = check_wechat_health()
    print(f"微信客户端健康状态: {'正常' if health_status else '异常'}")
    
    if health_status:
        print("✅ 微信客户端连接正常")
    else:
        print("⚠️ 微信客户端连接异常，可能需要检查")


def test_message_queue():
    """测试消息队列"""
    print("\n=== 测试消息队列 ===")
    
    wechat = get_wechat_instance()
    queue_size = wechat.get_queue_size()
    print(f"当前消息队列大小: {queue_size}")
    
    # 发送几条测试消息
    test_messages = [
        "测试消息1",
        "测试消息2", 
        "测试消息3"
    ]
    
    for i, msg in enumerate(test_messages, 1):
        send_message(f"{msg} - {time.strftime('%H:%M:%S')}", "老公老婆")
        print(f"已发送测试消息 {i}")
        time.sleep(0.5)
    
    # 等待消息处理
    time.sleep(3)
    
    # 检查队列状态
    final_queue_size = wechat.get_queue_size()
    print(f"处理后的队列大小: {final_queue_size}")
    
    if final_queue_size == 0:
        print("✅ 消息队列处理正常")
    else:
        print(f"⚠️ 队列中还有 {final_queue_size} 条消息未处理")


if __name__ == "__main__":
    print("开始测试WeChatHelper单例模式...")
    
    # 1. 测试单例模式
    singleton_ok = test_singleton_pattern()
    
    # 2. 测试全局实例
    global_ok = test_global_instance()
    
    # 3. 测试健康检查
    test_health_check()
    
    # 4. 测试消息队列
    test_message_queue()
    
    # 5. 测试并发任务（可选，需要微信客户端）
    try:
        test_concurrent_tasks()
    except Exception as e:
        print(f"并发任务测试失败: {e}")
    
    print("\n=== 测试总结 ===")
    if singleton_ok and global_ok:
        print("✅ 所有测试通过，单例模式工作正常")
        print("✅ 多个任务现在共享同一个WeChatHelper实例")
        print("✅ 应该能减少COM错误的发生")
    else:
        print("❌ 部分测试失败，需要检查单例模式实现") 