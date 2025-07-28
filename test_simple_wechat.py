#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试简化版微信发送功能
"""

import time
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.global_wechat_simple import (
    send_message, 
    check_wechat_health, 
    force_reinitialize,
    get_client
)
from utils.logger_utils import Logger


def test_simple_wechat():
    """测试简化版微信发送功能"""
    print("=== 测试简化版微信发送功能 ===")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 检查微信客户端健康状态
    print("\n1. 检查微信客户端健康状态...")
    health_status = check_wechat_health()
    print(f"微信客户端状态: {'✅ 正常' if health_status else '❌ 异常'}")
    
    if not health_status:
        print("⚠️  微信客户端状态异常，尝试重新初始化...")
        reinit_success = force_reinitialize()
        print(f"重新初始化结果: {'✅ 成功' if reinit_success else '❌ 失败'}")
        
        if not reinit_success:
            print("❌ 重新初始化失败，无法继续测试")
            return False
    
    # 2. 测试短消息发送
    print("\n2. 测试短消息发送...")
    test_message = f"简化版微信测试消息 - {datetime.now().strftime('%H:%M:%S')}"
    test_recipient = "算法学习二群"
    
    print(f"发送消息: {test_message}")
    print(f"发送到: {test_recipient}")
    
    try:
        success = send_message(test_message, test_recipient)
        print(f"发送结果: {'✅ 成功' if success else '❌ 失败'}")
    except Exception as e:
        print(f"❌ 发送异常: {e}")
        return False
    
    # 3. 测试长消息发送
    print("\n3. 测试长消息发送...")
    long_message = f"""不定期新闻播报来了: 
1. 测试新闻标题1 - 这是一个很长的新闻标题，用来测试长消息发送功能
2. 测试新闻标题2 - 这是另一个很长的新闻标题，用来测试长消息分割功能
3. 测试新闻标题3 - 这是第三个很长的新闻标题，用来测试消息处理能力
4. 测试新闻标题4 - 这是第四个很长的新闻标题，用来测试发送稳定性
5. 测试新闻标题5 - 这是第五个很长的新闻标题，用来测试完整功能

(共获取到5条新闻，显示前5条)"""
    
    print(f"长消息长度: {len(long_message)} 字符")
    print(f"发送到: {test_recipient}")
    
    try:
        success = send_message(long_message, test_recipient)
        print(f"发送结果: {'✅ 成功' if success else '❌ 失败'}")
    except Exception as e:
        print(f"❌ 发送异常: {e}")
        return False
    
    # 4. 测试多个接收者
    print("\n4. 测试多个接收者...")
    test_recipients = ["算法学习三群", "kyson的亿万俱乐部二群"]
    multi_message = f"多接收者测试消息 - {datetime.now().strftime('%H:%M:%S')}"
    
    for recipient in test_recipients:
        print(f"发送到: {recipient}")
        try:
            success = send_message(multi_message, recipient)
            print(f"  结果: {'✅ 成功' if success else '❌ 失败'}")
        except Exception as e:
            print(f"  ❌ 异常: {e}")
    
    # 5. 检查微信客户端状态
    print("\n5. 检查微信客户端状态...")
    try:
        wx_client = get_client()
        if wx_client:
            print("✅ 微信客户端实例正常")
        else:
            print("❌ 微信客户端实例为空")
    except Exception as e:
        print(f"❌ 检查客户端失败: {e}")
    
    print("\n=== 测试完成 ===")
    return True


def test_live_news_format():
    """测试 live_news 格式的消息"""
    print("\n=== 测试 Live News 格式消息 ===")
    
    # 模拟 live_news 的消息格式
    live_news_message = """不定期新闻播报来了: 
1. 央行：继续实施稳健的货币政策，保持流动性合理充裕
2. 证监会：进一步优化资本市场生态，提升服务实体经济能力
3. 银保监会：持续深化金融改革开放，防范化解金融风险
4. 发改委：加快推进重大项目建设，扩大有效投资
5. 财政部：实施积极的财政政策，支持经济高质量发展

(共获取到5条新闻，显示前5条)"""
    
    test_recipient = "算法学习二群"
    
    print(f"消息长度: {len(live_news_message)} 字符")
    print(f"发送到: {test_recipient}")
    
    try:
        success = send_message(live_news_message, test_recipient)
        print(f"发送结果: {'✅ 成功' if success else '❌ 失败'}")
        return success
    except Exception as e:
        print(f"❌ 发送异常: {e}")
        return False


def main():
    """主函数"""
    print("简化版微信发送功能测试")
    print("=" * 50)
    
    # 基本功能测试
    basic_success = test_simple_wechat()
    
    if basic_success:
        # Live News 格式测试
        live_news_success = test_live_news_format()
        
        if live_news_success:
            print("\n✅ 所有测试通过！简化版微信发送功能正常工作")
            print("\n建议:")
            print("1. 现在可以重新运行 live_news 任务")
            print("2. 监控发送日志确认功能正常")
            print("3. 如果仍有问题，检查微信客户端状态")
        else:
            print("\n⚠️  Live News 格式测试失败")
    else:
        print("\n❌ 基本功能测试失败")
    
    print("\n测试完成！")


if __name__ == "__main__":
    main() 