#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单的调试模式测试
"""

import os
from task_scheduler import get_all_task_status

def test_debug_mode():
    """测试调试模式"""
    print("=== 测试调试模式 ===")
    
    # 设置调试模式
    os.environ['DEBUG_MODE'] = '1'
    
    # 获取任务状态
    status_list = get_all_task_status()
    
    print(f"总任务数: {len(status_list)}")
    print("\n前3个任务的延迟时间:")
    
    for i, status in enumerate(status_list[:3], 1):
        print(f"{i}. {status['name']}: {status['delay_seconds']:.1f}秒")
    
    # 检查是否所有任务都是3秒
    all_3_seconds = all(s['delay_seconds'] == 3.0 for s in status_list if s['enabled'])
    
    if all_3_seconds:
        print("\n✅ 调试模式工作正常")
    else:
        print("\n❌ 调试模式有问题")
    
    return all_3_seconds

if __name__ == "__main__":
    test_debug_mode() 