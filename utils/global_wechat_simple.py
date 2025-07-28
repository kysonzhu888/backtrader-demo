#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简化版全局WeChatHelper实例
所有任务共享同一个WeChatHelperSimple实例，直接发送消息
"""

from utils.wechat_helper_simple import WeChatHelperSimple
from utils.logger_utils import Logger

# 全局WeChatHelperSimple实例
_wechat_instance = None

def get_wechat_instance():
    """获取全局WeChatHelperSimple实例"""
    global _wechat_instance
    if _wechat_instance is None:
        Logger.info("创建全局WeChatHelperSimple实例...")
        _wechat_instance = WeChatHelperSimple.get_instance()
    return _wechat_instance

def reset_wechat_instance():
    """重置全局WeChatHelperSimple实例"""
    global _wechat_instance
    if _wechat_instance:
        Logger.info("重置全局WeChatHelperSimple实例...")
        WeChatHelperSimple.reset_instance()
        _wechat_instance = None

def send_message(message, recipient):
    """发送消息的便捷方法"""
    wechat = get_wechat_instance()
    return wechat.send_message(message, recipient)

def send_message_to_multiple_recipients(message, recipients):
    """发送消息给多个接收者的便捷方法"""
    wechat = get_wechat_instance()
    success_count = 0
    
    if not isinstance(recipients, list):
        recipients = [recipients]
    
    for recipient in recipients:
        if recipient and recipient.strip():
            if wechat.send_message(message, recipient):
                success_count += 1
    
    Logger.info(f"已向 {success_count}/{len(recipients)} 个接收者发送消息")
    return success_count

def send_file(file_path, recipient=None):
    """发送文件的便捷方法"""
    wechat = get_wechat_instance()
    return wechat.send_file(file_path, recipient)

def check_wechat_health():
    """检查微信客户端健康状态"""
    wechat = get_wechat_instance()
    return wechat.check_wechat_health()

def force_reinitialize():
    """强制重新初始化微信客户端"""
    wechat = get_wechat_instance()
    return wechat.force_reinitialize()

def get_client():
    """获取微信客户端实例"""
    wechat = get_wechat_instance()
    return wechat.get_client() 