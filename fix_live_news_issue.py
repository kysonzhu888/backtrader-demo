#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Live News 发送问题修复脚本
专门解决 live_news 任务中微信发送失败的问题
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
    reset_wechat_instance,
    send_message
)
from utils.logger_utils import Logger


def test_live_news_send():
    """测试 live_news 消息发送功能"""
    print("=== 测试 Live News 消息发送 ===")
    
    # 模拟 live_news 的消息格式
    test_message = """不定期新闻播报来了: 
1. 测试新闻标题1
2. 测试新闻标题2
3. 测试新闻标题3
4. 测试新闻标题4
5. 测试新闻标题5

(共获取到5条新闻，显示前5条)"""
    
    # live_news 任务的目标群组
    target_groups = [
        "算法学习二群",
        "算法学习三群", 
        "kyson的亿万俱乐部二群",
        "kyson的亿万俱乐部三群",
        "投资策略VIP群"
    ]
    
    print(f"测试消息长度: {len(test_message)} 字符")
    print(f"目标群组数量: {len(target_groups)}")
    
    # 测试发送到每个群组
    success_count = 0
    for i, group in enumerate(target_groups, 1):
        print(f"\n{i}. 测试发送到: {group}")
        try:
            send_message(test_message, group)
            print(f"  ✅ 消息已加入队列")
            success_count += 1
        except Exception as e:
            print(f"  ❌ 发送失败: {e}")
    
    print(f"\n发送测试结果: {success_count}/{len(target_groups)} 成功")
    
    # 等待消息处理
    print("\n等待消息处理...")
    time.sleep(10)
    
    # 检查处理结果
    try:
        stats = get_send_stats()
        print(f"队列大小: {stats['queue_size']}")
        print(f"已发送消息数: {stats['sent_messages_count']}")
    except Exception as e:
        print(f"获取统计信息失败: {e}")
    
    return success_count == len(target_groups)


def fix_wechat_for_live_news():
    """为 live_news 任务修复微信客户端"""
    print("\n=== 修复微信客户端 ===")
    
    # 1. 检查当前状态
    print("1. 检查当前微信客户端状态...")
    health_status = check_wechat_health()
    print(f"当前状态: {'✅ 正常' if health_status else '❌ 异常'}")
    
    # 2. 如果异常，尝试重新初始化
    if not health_status:
        print("2. 微信客户端异常，尝试重新初始化...")
        reinit_success = force_reinitialize()
        print(f"重新初始化结果: {'✅ 成功' if reinit_success else '❌ 失败'}")
        
        if not reinit_success:
            print("3. 重新初始化失败，尝试完全重置...")
            try:
                reset_wechat_instance()
                time.sleep(3)
                wechat = get_wechat_instance()
                print("✅ 完全重置成功")
            except Exception as e:
                print(f"❌ 完全重置失败: {e}")
                return False
    
    # 3. 再次检查状态
    print("4. 检查修复后状态...")
    health_status = check_wechat_health()
    print(f"修复后状态: {'✅ 正常' if health_status else '❌ 异常'}")
    
    return health_status


def optimize_for_live_news():
    """为 live_news 任务优化微信客户端"""
    print("\n=== 优化微信客户端配置 ===")
    
    wechat = get_wechat_instance()
    
    # 1. 清理已发送消息记录
    print("1. 清理已发送消息记录...")
    try:
        wechat.clear_sent_messages()
        print("✅ 已清理发送记录")
    except Exception as e:
        print(f"❌ 清理失败: {e}")
    
    # 2. 检查队列状态
    print("2. 检查消息队列状态...")
    try:
        queue_size = wechat.get_queue_size()
        print(f"当前队列大小: {queue_size}")
        
        if queue_size > 0:
            print("⚠️  队列中有未处理消息，等待处理...")
            time.sleep(5)
            queue_size = wechat.get_queue_size()
            print(f"处理后队列大小: {queue_size}")
    except Exception as e:
        print(f"❌ 检查队列失败: {e}")
    
    # 3. 获取统计信息
    print("3. 获取发送统计信息...")
    try:
        stats = get_send_stats()
        print(f"发送统计: {stats}")
    except Exception as e:
        print(f"❌ 获取统计失败: {e}")


def main():
    """主函数"""
    print("Live News 发送问题修复工具")
    print("=" * 50)
    
    # 1. 修复微信客户端
    fix_success = fix_wechat_for_live_news()
    
    if not fix_success:
        print("\n❌ 微信客户端修复失败！")
        print("建议操作:")
        print("1. 重启微信客户端")
        print("2. 检查微信版本是否兼容")
        print("3. 确认微信窗口处于正常状态")
        return
    
    # 2. 优化配置
    optimize_for_live_news()
    
    # 3. 测试发送功能
    print("\n" + "=" * 50)
    test_success = test_live_news_send()
    
    if test_success:
        print("\n✅ 修复完成！Live News 任务现在应该可以正常发送消息了")
        print("\n建议:")
        print("1. 重新运行 live_news 任务")
        print("2. 监控发送日志")
        print("3. 如果仍有问题，运行 diagnose_wechat_issue.py 进行详细诊断")
    else:
        print("\n⚠️  部分测试失败，建议:")
        print("1. 检查群聊名称是否正确")
        print("2. 确认微信窗口处于活跃状态")
        print("3. 运行 diagnose_wechat_issue.py 进行详细诊断")
    
    print("\n修复完成！")


if __name__ == "__main__":
    main() 