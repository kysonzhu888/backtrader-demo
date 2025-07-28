#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试港股TOP10播报功能
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tasks.hk_top10_broadcaster import run_hk_top10_broadcast
from utils.global_wechat_simple import check_wechat_health


def test_hk_top10_broadcaster():
    """测试港股TOP10播报功能"""
    print("=== 测试港股TOP10播报功能 ===")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 检查微信客户端健康状态
    print("\n1. 检查微信客户端健康状态...")
    health_status = check_wechat_health()
    print(f"微信客户端状态: {'✅ 正常' if health_status else '❌ 异常'}")
    
    if not health_status:
        print("❌ 微信客户端状态异常，无法继续测试")
        return False
    
    # 2. 运行港股TOP10播报任务
    print("\n2. 运行港股TOP10播报任务...")
    try:
        run_hk_top10_broadcast()
        print("✅ 港股TOP10播报任务执行完成")
        return True
    except Exception as e:
        print(f"❌ 港股TOP10播报任务执行失败: {e}")
        return False


def main():
    """主函数"""
    print("港股TOP10播报功能测试")
    print("=" * 50)
    
    success = test_hk_top10_broadcaster()
    
    if success:
        print("\n✅ 港股TOP10播报功能测试成功！")
        print("\n建议:")
        print("1. 检查微信中是否收到港股TOP10播报消息")
        print("2. 确认消息内容是否正确")
        print("3. 如果正常，可以安排定时任务")
    else:
        print("\n❌ 港股TOP10播报功能测试失败")
        print("\n建议:")
        print("1. 检查微信客户端状态")
        print("2. 检查网络连接")
        print("3. 检查Tushare API配置是否正确")
        print("4. 检查是否有港股通数据")
    
    print("\n测试完成！")


if __name__ == "__main__":
    main() 