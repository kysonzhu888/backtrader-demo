#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一的微信工具模块
整合所有微信相关功能，提供简洁的API接口
"""

import time
import os
import platform
import threading
from utils.logger_utils import Logger
from utils.wechat_process_lock import acquire_wechat_process_lock


class WeChat:
    """统一的微信工具类"""
    
    def __init__(self):
        """初始化微信客户端"""
        self.wx = None
        self._lock = threading.Lock()
        self._initialized = False
        self._main_thread = threading.main_thread()
        self._current_thread = threading.current_thread()
        
        # 检查是否在主线程中
        if self._current_thread == self._main_thread:
            Logger.info("在主线程中初始化微信工具")
            self._initialize_wechat()
        else:
            Logger.warning(f"在子线程 {self._current_thread.name} 中初始化微信工具")
            Logger.warning("建议在任务调度器中设置微信任务在主线程中执行")
            # 仍然尝试初始化，但给出警告
            self._initialize_wechat()
    
    def _initialize_wechat(self):
        """初始化微信客户端"""
        with self._lock:
            if self._initialized:
                return True
                
            if platform.system() == 'Windows':
                if os.getenv('DEBUG_MODE') == '1':
                    self.wx = None
                    Logger.info("调试模式：微信客户端未初始化")
                else:
                    try:
                        from wxauto import WeChat as WxAuto
                        self.wx = WxAuto()
                        Logger.info("微信客户端初始化成功")
                    except Exception as e:
                        Logger.error(f"微信客户端初始化失败: {e}")
                        self.wx = None
            else:
                self.wx = None
                Logger.info("非Windows系统：微信客户端未初始化")
            
            self._initialized = True
            return self.wx is not None

    def send_message(self, message, recipient):
        """
        发送消息
        
        Args:
            message: 消息内容
            recipient: 接收者
            
        Returns:
            bool: 发送是否成功
        """
        if not message or not message.strip():
            Logger.info("不发送空消息")
            return False
            
        if not recipient or not recipient.strip():
            Logger.warning("接收者不能为空")
            return False
        
        # 检查是否在主线程中
        if self._current_thread != self._main_thread:
            Logger.warning(f"在子线程 {self._current_thread.name} 中发送消息，可能导致wxauto操作失败")
            Logger.warning("建议在任务调度器中设置微信任务在主线程中执行")
        
        try:
            if not self.wx:
                Logger.info(f"[模拟发送] {recipient}: {message}")
                return True
            
            # 使用进程锁确保微信窗口访问的互斥性
            with acquire_wechat_process_lock('send_message', recipient, timeout=60):
                with self._lock:
                    # 切换到目标聊天窗口
                    self.wx.ChatWith(recipient)
                    time.sleep(0.8)  # 确保窗口切换完成
                    
                    # 发送消息
                    result = self.wx.SendMsg(message, recipient)
                    
                    if result:
                        Logger.info(f"消息发送成功: {recipient}")
                        return True
                    else:
                        Logger.error(f"消息发送失败: {recipient}")
                        return False
                    
        except Exception as e:
            Logger.error(f"发送消息时出错: {str(e)}")
            # 如果是COM错误，给出更明确的提示
            if "COM" in str(e) or "-2147467259" in str(e):
                Logger.error("检测到COM错误，这通常是因为在子线程中调用wxauto导致的")
                Logger.error("建议在任务调度器中设置微信任务在主线程中执行")
            return False

    def send_file(self, file_path, recipient=None):
        """
        发送文件
        
        Args:
            file_path: 文件路径
            recipient: 接收者（可选，如果不指定则发送到当前聊天窗口）
            
        Returns:
            bool: 发送是否成功
        """
        if not file_path or not os.path.exists(file_path):
            Logger.error(f"文件不存在: {file_path}")
            return False
        
        # 检查是否在主线程中
        if self._current_thread != self._main_thread:
            Logger.warning(f"在子线程 {self._current_thread.name} 中发送文件，可能导致wxauto操作失败")
            Logger.warning("建议在任务调度器中设置微信任务在主线程中执行")
            
        try:
            if not self.wx:
                Logger.info(f"[模拟发送文件] {file_path}")
                return True
            
            # 使用进程锁确保微信窗口访问的互斥性
            with acquire_wechat_process_lock('send_file', recipient, timeout=60):
                with self._lock:
                    if recipient:
                        # 如果有指定接收者，先切换到对应聊天窗口
                        self.wx.ChatWith(recipient)
                        time.sleep(0.8)  # 确保窗口切换完成
                    
                    result = self.wx.SendFiles(file_path)
                    if result:
                        Logger.info(f"文件发送成功: {file_path}")
                        return True
                    else:
                        Logger.error(f"文件发送失败: {file_path}")
                        return False
                    
        except Exception as e:
            Logger.error(f"发送文件时出错: {str(e)}")
            # 如果是COM错误，给出更明确的提示
            if "COM" in str(e) or "-2147467259" in str(e):
                Logger.error("检测到COM错误，这通常是因为在子线程中调用wxauto导致的")
                Logger.error("建议在任务调度器中设置微信任务在主线程中执行")
            return False

    def send_message_to_multiple_recipients(self, message, recipients):
        """
        发送消息给多个接收者
        
        Args:
            message: 消息内容
            recipients: 接收者列表
            
        Returns:
            int: 成功发送的数量
        """
        success_count = 0
        
        if not isinstance(recipients, list):
            recipients = [recipients]
        
        for recipient in recipients:
            if recipient and recipient.strip():
                if self.send_message(message, recipient):
                    success_count += 1
        
        Logger.info(f"已向 {success_count}/{len(recipients)} 个接收者发送消息")
        return success_count

    def get_client(self):
        """获取微信客户端实例"""
        return self.wx

    def reinitialize(self):
        """重新初始化微信客户端"""
        Logger.info("重新初始化微信客户端...")
        with self._lock:
            self._initialized = False
            self.wx = None
        return self._initialize_wechat()


# 全局实例
_wechat_instance = None
_wechat_lock = threading.Lock()


def get_wechat_instance():
    """获取全局微信实例"""
    global _wechat_instance
    
    with _wechat_lock:
        if _wechat_instance is None:
            Logger.info("创建统一版微信实例...")
            _wechat_instance = WeChat()
        return _wechat_instance


# 便捷方法 - 向后兼容原有API
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


def get_client():
    """获取微信客户端实例"""
    wechat = get_wechat_instance()
    return wechat.get_client()


# 兼容性方法
def check_wechat_health():
    """检查微信客户端健康状态（兼容性方法，总是返回True）"""
    return True


def force_reinitialize():
    """强制重新初始化微信客户端（兼容性方法）"""
    wechat = get_wechat_instance()
    return wechat.reinitialize()


def get_send_stats():
    """获取发送统计信息（兼容性方法，无统计）"""
    return {
        'note': '统一版微信工具无统计功能'
    }


def clear_sent_messages():
    """清理已发送消息记录（兼容性方法，无记录）"""
    Logger.info("统一版微信工具无消息记录需要清理")


def reset_wechat_instance():
    """重置微信实例（兼容性方法）"""
    global _wechat_instance
    with _wechat_lock:
        _wechat_instance = None
        Logger.info("统一版微信实例已重置")


# 导出进程锁监控功能
from utils.wechat_process_lock import (
    get_wechat_lock_stats,
    reset_wechat_lock_stats,
    is_wechat_locked,
    get_wechat_lock_info
)

__all__ = [
    'WeChat',
    'send_message',
    'send_message_to_multiple_recipients', 
    'send_file',
    'get_client',
    'check_wechat_health',
    'force_reinitialize',
    'get_send_stats',
    'clear_sent_messages',
    'reset_wechat_instance',
    'get_wechat_lock_stats',
    'reset_wechat_lock_stats',
    'is_wechat_locked',
    'get_wechat_lock_info'
]