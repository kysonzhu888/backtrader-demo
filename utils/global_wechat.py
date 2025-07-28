#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
全局WeChatHelper实例
所有任务共享同一个WeChatHelper实例，避免重复创建导致的COM错误
"""

from utils.wechat_helper import WeChatHelper
from utils.logger_utils import Logger

# 全局WeChatHelper实例
_wechat_instance = None

def get_wechat_instance():
    """获取全局WeChatHelper实例"""
    global _wechat_instance
    if _wechat_instance is None:
        Logger.info("创建全局WeChatHelper实例...")
        _wechat_instance = WeChatHelper.get_instance()
    return _wechat_instance

def reset_wechat_instance():
    """重置全局WeChatHelper实例"""
    global _wechat_instance
    if _wechat_instance:
        Logger.info("重置全局WeChatHelper实例...")
        WeChatHelper.reset_instance()
        _wechat_instance = None

def send_message(message, recipient):
    """发送消息的便捷方法"""
    wechat = get_wechat_instance()
    return wechat.send_message(message, recipient)

def send_message_to_multiple_recipients(message, recipients):
    """发送消息给多个接收者的便捷方法"""
    wechat = get_wechat_instance()
    return wechat.send_message_to_multiple_recipients(message, recipients)

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

def get_send_stats():
    """获取发送统计信息"""
    wechat = get_wechat_instance()
    return wechat.get_send_stats() 