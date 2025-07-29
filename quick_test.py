#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
快速测试简单修复版微信工具
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.wechat_helper_simple_fix import send_message


def main():
    """主函数"""
    print("快速测试简单修复版微信工具")
    print("=" * 50)
    
    # 测试基本功能
    print("测试基本功能...")
    test_message = f"快速测试消息 - {datetime.now().strftime('%H:%M:%S')}"
    test_recipient = "算法学习二群"
    
    try:
        success = send_message(test_message, test_recipient)
        print(f"发送结果: {'✅ 成功' if success else '❌ 失败'}")
        
        if success:
            print("🎉 测试通过！简单修复版微信工具正常工作")
        else:
            print("❌ 测试失败")
            
    except Exception as e:
        print(f"❌ 发送异常: {e}")
    
    print("测试完成！")


if __name__ == "__main__":
    main() 