#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
微信锁紧急清理工具
当出现锁超时问题时，使用此脚本强制清理僵尸锁
"""

import sys
sys.path.append('.')
from utils.wechat import (
    get_wechat_lock_info, 
    cleanup_wechat_zombie_lock,
    get_wechat_lock_stats,
    is_wechat_locked
)

def emergency_cleanup():
    """紧急清理函数"""
    print("🚨 微信锁紧急清理工具")
    print("="*50)
    
    # 显示当前状态
    print("📊 当前锁状态:")
    print(f"  锁是否被占用: {'是' if is_wechat_locked() else '否'}")
    print(f"  锁详细信息: {get_wechat_lock_info()}")
    
    # 显示统计信息

    stats = get_wechat_lock_stats()
    print(f"\n📈 统计信息:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 执行清理
    print(f"\n🧹 执行清理...")
    result = cleanup_wechat_zombie_lock()
    
    if result:
        print("✅ 清理完成")
    else:
        print("❌ 清理失败或无需清理")
    
    # 显示清理后状态
    print(f"\n📊 清理后状态:")
    print(f"  锁是否被占用: {'是' if is_wechat_locked() else '否'}")
    print(f"  锁详细信息: {get_wechat_lock_info()}")
    
    print("\n💡 如果问题仍然存在，请检查:")
    print("  1. 是否有进程长时间占用微信窗口")
    print("  2. 微信程序是否响应正常")
    print("  3. 系统资源是否充足")

if __name__ == "__main__":
    emergency_cleanup()