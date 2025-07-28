#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试改进后的WeChatHelper错误处理功能
"""

import time
import os
from utils.wechat_helper import WeChatHelper
from utils.logger_utils import Logger


def test_wechat_helper():
    """测试WeChatHelper的各种功能"""
    print("=== 测试WeChatHelper错误处理功能 ===")
    
    # 创建WeChatHelper实例
    wechat = WeChatHelper()
    
    # 1. 测试健康检查
    print("\n1. 测试微信客户端健康检查...")
    health_status = wechat.check_wechat_health()
    print(f"微信客户端健康状态: {'正常' if health_status else '异常'}")
    
    # 2. 测试消息发送（使用测试群聊）
    test_recipient = "老公老婆"  # 根据实际情况修改
    test_message = f"测试消息 - {time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    print(f"\n2. 测试消息发送到: {test_recipient}")
    print(f"测试消息: {test_message}")
    
    try:
        wechat.send_message(test_message, test_recipient)
        print("消息已加入发送队列")
        
        # 等待消息处理
        time.sleep(3)
        
        # 检查队列状态
        queue_size = wechat.get_queue_size()
        print(f"当前队列大小: {queue_size}")
        
    except Exception as e:
        print(f"发送消息时出错: {e}")
    
    # 3. 测试强制重新初始化
    print("\n3. 测试强制重新初始化...")
    try:
        reinit_success = wechat.force_reinitialize()
        print(f"重新初始化结果: {'成功' if reinit_success else '失败'}")
    except Exception as e:
        print(f"重新初始化时出错: {e}")
    
    # 4. 测试发送统计
    print("\n4. 获取发送统计信息...")
    try:
        stats = wechat.get_send_stats()
        print(f"发送统计: {stats}")
    except Exception as e:
        print(f"获取统计信息时出错: {e}")
    
    # 5. 测试错误处理（模拟COM错误）
    print("\n5. 测试错误处理机制...")
    try:
        # 尝试发送到不存在的联系人（可能触发错误）
        wechat.send_message("测试错误处理", "不存在的联系人")
        print("错误处理测试完成")
    except Exception as e:
        print(f"错误处理测试时出错: {e}")
    
    print("\n=== 测试完成 ===")


def test_debug_mode():
    """测试调试模式"""
    print("\n=== 测试调试模式 ===")
    
    # 设置调试模式
    os.environ['DEBUG_MODE'] = '1'
    
    # 创建WeChatHelper实例（调试模式）
    wechat = WeChatHelper()
    
    # 测试消息发送（调试模式下应该模拟发送）
    test_message = f"调试模式测试消息 - {time.strftime('%Y-%m-%d %H:%M:%S')}"
    wechat.send_message(test_message, "测试群聊")
    
    print("调试模式测试完成")
    
    # 清除调试模式
    os.environ.pop('DEBUG_MODE', None)


if __name__ == "__main__":
    # 测试正常模式
    test_wechat_helper()
    
    # 测试调试模式
    test_debug_mode() 