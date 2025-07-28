#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
微信发送问题诊断和修复脚本
用于诊断和解决 live_news 任务中微信发送失败的问题
"""

import time
import os
import sys
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.global_wechat import (
    get_wechat_instance, 
    check_wechat_health, 
    force_reinitialize,
    get_send_stats,
    reset_wechat_instance
)
from utils.logger_utils import Logger


def diagnose_wechat_issue():
    """诊断微信发送问题"""
    print("=== 微信发送问题诊断 ===")
    print(f"诊断时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 检查微信客户端健康状态
    print("\n1. 检查微信客户端健康状态...")
    health_status = check_wechat_health()
    print(f"微信客户端状态: {'✅ 正常' if health_status else '❌ 异常'}")
    
    if not health_status:
        print("⚠️  微信客户端状态异常，尝试重新初始化...")
        reinit_success = force_reinitialize()
        print(f"重新初始化结果: {'✅ 成功' if reinit_success else '❌ 失败'}")
        
        # 重新检查健康状态
        health_status = check_wechat_health()
        print(f"重新初始化后状态: {'✅ 正常' if health_status else '❌ 异常'}")
    
    # 2. 获取发送统计信息
    print("\n2. 获取发送统计信息...")
    try:
        stats = get_send_stats()
        print(f"队列大小: {stats['queue_size']}")
        print(f"已发送消息数: {stats['sent_messages_count']}")
        print(f"接收者数量: {stats['recipients_count']}")
        
        if stats['last_send_times']:
            print("最后发送时间:")
            for recipient, last_time in stats['last_send_times'].items():
                print(f"  {recipient}: {last_time}")
    except Exception as e:
        print(f"获取统计信息失败: {e}")
    
    # 3. 测试消息发送
    print("\n3. 测试消息发送功能...")
    test_recipients = ["算法学习二群", "算法学习三群", "kyson的亿万俱乐部二群"]
    test_message = f"微信发送功能测试 - {datetime.now().strftime('%H:%M:%S')}"
    
    wechat = get_wechat_instance()
    
    for recipient in test_recipients:
        print(f"测试发送到: {recipient}")
        try:
            wechat.send_message(test_message, recipient)
            print(f"  ✅ 消息已加入队列")
        except Exception as e:
            print(f"  ❌ 发送失败: {e}")
    
    # 4. 等待消息处理
    print("\n4. 等待消息处理...")
    time.sleep(5)
    
    # 5. 再次检查统计信息
    print("\n5. 检查处理后的统计信息...")
    try:
        stats = get_send_stats()
        print(f"队列大小: {stats['queue_size']}")
        print(f"已发送消息数: {stats['sent_messages_count']}")
    except Exception as e:
        print(f"获取统计信息失败: {e}")
    
    # 6. 检查微信窗口状态
    print("\n6. 检查微信窗口状态...")
    try:
        wx_client = wechat.get_client()
        if wx_client:
            # 兼容不同版本的 wxauto
            if hasattr(wx_client, 'GetWeChatWindow'):
                window_info = wx_client.GetWeChatWindow()
            elif hasattr(wx_client, 'get_wechat_window'):
                window_info = wx_client.get_wechat_window()
            else:
                # 尝试获取当前聊天窗口名称
                try:
                    current_chat = wx_client.GetCurrentWindowName()
                    if current_chat:
                        print("✅ 微信窗口正常")
                        window_info = True
                    else:
                        print("❌ 无法获取当前聊天窗口")
                        window_info = None
                except:
                    print("⚠️  无法验证微信窗口状态，但客户端已初始化")
                    window_info = True
            
            if window_info:
                print("✅ 微信窗口正常")
            else:
                print("❌ 无法获取微信窗口")
        else:
            print("⚠️  微信客户端未初始化")
    except Exception as e:
        print(f"❌ 检查微信窗口失败: {e}")
    
    return health_status


def fix_wechat_issue():
    """修复微信发送问题"""
    print("\n=== 微信发送问题修复 ===")
    
    # 1. 重置微信实例
    print("1. 重置微信实例...")
    try:
        reset_wechat_instance()
        print("✅ 微信实例重置成功")
    except Exception as e:
        print(f"❌ 重置失败: {e}")
        return False
    
    # 2. 等待一段时间
    print("2. 等待系统稳定...")
    time.sleep(3)
    
    # 3. 重新初始化
    print("3. 重新初始化微信客户端...")
    try:
        wechat = get_wechat_instance()
        print("✅ 微信客户端重新初始化成功")
    except Exception as e:
        print(f"❌ 重新初始化失败: {e}")
        return False
    
    # 4. 检查健康状态
    print("4. 检查健康状态...")
    health_status = check_wechat_health()
    print(f"健康状态: {'✅ 正常' if health_status else '❌ 异常'}")
    
    # 5. 测试发送功能
    print("5. 测试发送功能...")
    test_message = f"修复后测试消息 - {datetime.now().strftime('%H:%M:%S')}"
    test_recipient = "算法学习二群"
    
    try:
        wechat.send_message(test_message, test_recipient)
        print("✅ 测试消息已发送")
        
        # 等待处理
        time.sleep(3)
        
        # 检查队列
        stats = get_send_stats()
        print(f"队列大小: {stats['queue_size']}")
        
    except Exception as e:
        print(f"❌ 测试发送失败: {e}")
        return False
    
    return health_status


def main():
    """主函数"""
    print("微信发送问题诊断和修复工具")
    print("=" * 50)
    
    # 诊断问题
    health_status = diagnose_wechat_issue()
    
    # 如果诊断发现问题，尝试修复
    if not health_status:
        print("\n" + "=" * 50)
        print("检测到问题，开始修复...")
        
        fix_success = fix_wechat_issue()
        
        if fix_success:
            print("\n✅ 修复完成！建议重新运行 live_news 任务")
        else:
            print("\n❌ 修复失败！请检查微信客户端状态")
            print("建议操作:")
            print("1. 重启微信客户端")
            print("2. 检查微信版本是否兼容")
            print("3. 确认微信窗口处于正常状态")
    else:
        print("\n✅ 微信客户端状态正常")
        print("如果仍有发送问题，可能是其他原因导致的")
    
    print("\n诊断完成！")


if __name__ == "__main__":
    main() 