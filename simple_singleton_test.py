#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单的WeChatHelper单例模式测试
"""

import os
os.environ['DEBUG_MODE'] = '1'

from utils.wechat_helper import WeChatHelper

def test_singleton():
    print("=== 测试WeChatHelper单例模式 ===")
    
    # 创建多个实例
    w1 = WeChatHelper()
    w2 = WeChatHelper()
    w3 = WeChatHelper()
    
    print(f"w1 id: {id(w1)}")
    print(f"w2 id: {id(w2)}")
    print(f"w3 id: {id(w3)}")
    
    # 验证是否为同一个实例
    is_singleton = (w1 is w2 is w3)
    print(f"是否为单例: {is_singleton}")
    
    if is_singleton:
        print("✅ 单例模式工作正常")
    else:
        print("❌ 单例模式有问题")
    
    return is_singleton

if __name__ == "__main__":
    test_singleton() 