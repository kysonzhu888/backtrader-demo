#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
最简化版全局微信工具
每次都创建新的WeChatHelperMinimal实例，只保留最基本功能
"""

from utils.wechat_helper_minimal import WeChatHelperMinimal
from utils.logger_utils import Logger


def send_message(message, recipient):
    """发送消息的便捷方法"""
    wechat = WeChatHelperMinimal()
    return wechat.send_message(message, recipient)


def send_message_to_multiple_recipients(message, recipients):
    """发送消息给多个接收者的便捷方法"""
    success_count = 0
    
    if not isinstance(recipients, list):
        recipients = [recipients]
    
    for recipient in recipients:
        if recipient and recipient.strip():
            wechat = WeChatHelperMinimal()
            if wechat.send_message(message, recipient):
                success_count += 1
    
    Logger.info(f"已向 {success_count}/{len(recipients)} 个接收者发送消息")
    return success_count


def send_file(file_path, recipient=None):
    """发送文件的便捷方法"""
    wechat = WeChatHelperMinimal()
    return wechat.send_file(file_path, recipient)


def get_client():
    """获取微信客户端实例"""
    wechat = WeChatHelperMinimal()
    return wechat.get_client()


# 兼容性方法（简化版）
def get_wechat_instance():
    """获取微信实例（兼容性方法）"""
    return WeChatHelperMinimal()


def check_wechat_health():
    """检查微信客户端健康状态（兼容性方法，总是返回True）"""
    return True


def force_reinitialize():
    """强制重新初始化微信客户端（兼容性方法，总是返回True）"""
    return True


def get_send_stats():
    """获取发送统计信息（兼容性方法，无统计）"""
    return {
        'note': '最简化版微信工具无统计功能'
    }


def clear_sent_messages():
    """清理已发送消息记录（兼容性方法，无记录）"""
    Logger.info("最简化版微信工具无消息记录需要清理")


def reset_wechat_instance():
    """重置微信实例（兼容性方法，不需要）"""
    Logger.info("最简化版微信工具不需要重置实例") 