#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
最终简化版 WeChatHelper
确保所有微信操作都在主线程中执行
"""

import time
import os
import platform
import threading
import queue
from utils.logger_utils import Logger
from utils.wechat_process_lock import acquire_wechat_process_lock


class WeChatHelperMainThreadFinal:
    def __init__(self):
        """初始化微信客户端"""
        self.wx = None
        self._lock = threading.Lock()
        self._initialized = False
        self._main_thread = threading.main_thread()
        self._current_thread = threading.current_thread()
        
        # 消息队列，用于子线程到主线程的通信
        self._task_queue = queue.Queue()
        self._result_queue = queue.Queue()
        self._running = True
        
        # 检查是否在主线程中
        if self._current_thread == self._main_thread:
            Logger.info("在主线程中初始化微信工具")
            self._initialize_wechat()
        else:
            Logger.info(f"在子线程 {self._current_thread.name} 中初始化微信工具，将使用主线程执行")
            # 在子线程中，不立即初始化，而是通过主线程执行
    
    def _initialize_wechat(self):
        """初始化微信客户端（必须在主线程中调用）"""
        if self._current_thread != self._main_thread:
            Logger.error("微信初始化必须在主线程中执行")
            return False
            
        with self._lock:
            if self._initialized:
                return True
                
            if platform.system() == 'Windows':
                if os.getenv('DEBUG_MODE') == '1':
                    self.wx = None
                    Logger.info("调试模式：微信客户端未初始化")
                else:
                    try:
                        from wxauto import WeChat
                        self.wx = WeChat()
                        Logger.info("微信客户端初始化成功")
                    except Exception as e:
                        Logger.error(f"微信客户端初始化失败: {e}")
                        self.wx = None
            else:
                self.wx = None
                Logger.info("非Windows系统：微信客户端未初始化")
            
            self._initialized = True
            return self.wx is not None

    def _execute_in_main_thread(self, operation, *args, **kwargs):
        """确保操作在主线程中执行"""
        if self._current_thread == self._main_thread:
            # 如果已经在主线程中，直接执行
            return operation(*args, **kwargs)
        else:
            # 如果在子线程中，通过主线程执行
            Logger.debug(f"在子线程 {self._current_thread.name} 中，通过主线程执行操作")
            
            # 创建任务
            task = {
                'operation': operation,
                'args': args,
                'kwargs': kwargs,
                'result_queue': queue.Queue()
            }
            
            # 将任务放入主线程队列
            self._task_queue.put(task)
            
            # 等待结果
            try:
                result = task['result_queue'].get(timeout=30)  # 30秒超时
                return result
            except queue.Empty:
                Logger.error("等待主线程执行超时")
                return False

    def _send_message_main_thread(self, message, recipient):
        """在主线程中发送消息"""
        if self._current_thread != self._main_thread:
            Logger.error("发送消息必须在主线程中执行")
            return False
            
        if not message or not message.strip():
            Logger.info("不发送空消息")
            return False
            
        if not recipient or not recipient.strip():
            Logger.warning("接收者不能为空")
            return False
        
        try:
            if not self.wx:
                Logger.info(f"[模拟发送] {recipient}: {message}")
                return True
            
            # 使用进程锁确保微信窗口访问的互斥性
            with acquire_wechat_process_lock('send_message', recipient, timeout=60):
                with self._lock:
                    # 切换到目标聊天窗口
                    self.wx.ChatWith(recipient)
                    time.sleep(0.8)  # 增加等待时间，确保窗口切换完成
                    
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
            return False

    def _send_file_main_thread(self, file_path, recipient=None):
        """在主线程中发送文件"""
        if self._current_thread != self._main_thread:
            Logger.error("发送文件必须在主线程中执行")
            return False
            
        if not file_path or not os.path.exists(file_path):
            Logger.error(f"文件不存在: {file_path}")
            return False
            
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
                        time.sleep(0.8)  # 增加等待时间，确保窗口切换完成
                    
                    result = self.wx.SendFiles(file_path)
                    if result:
                        Logger.info(f"文件发送成功: {file_path}")
                        return True
                    else:
                        Logger.error(f"文件发送失败: {file_path}")
                        return False
                    
        except Exception as e:
            Logger.error(f"发送文件时出错: {str(e)}")
            return False

    def send_message(self, message, recipient):
        """发送消息（确保在主线程中执行）"""
        return self._execute_in_main_thread(self._send_message_main_thread, message, recipient)

    def send_file(self, file_path, recipient=None):
        """发送文件（确保在主线程中执行）"""
        return self._execute_in_main_thread(self._send_file_main_thread, file_path, recipient)

    def get_client(self):
        """获取微信客户端实例"""
        return self.wx

    def reinitialize(self):
        """重新初始化微信客户端"""
        return self._execute_in_main_thread(self._initialize_wechat)

    def process_main_thread_tasks(self):
        """处理主线程任务（必须在主线程中调用）"""
        if self._current_thread != self._main_thread:
            Logger.error("主线程任务处理必须在主线程中调用")
            return False
            
        # 初始化微信客户端
        self._initialize_wechat()
        
        # 处理任务队列
        while self._running:
            try:
                # 从队列获取任务
                task = self._task_queue.get(timeout=1)
                
                # 执行操作
                try:
                    result = task['operation'](*task['args'], **task['kwargs'])
                    task['result_queue'].put(result)
                except Exception as e:
                    Logger.error(f"执行任务时出错: {e}")
                    task['result_queue'].put(False)
                    
            except queue.Empty:
                continue
            except Exception as e:
                Logger.error(f"主线程任务处理出错: {e}")
                break
        
        Logger.info("主线程任务处理已停止")

    def stop(self):
        """停止主线程任务处理"""
        self._running = False
        Logger.info("正在停止主线程任务处理...")


# 全局实例
_wechat_instance = None
_wechat_lock = threading.Lock()


def get_wechat_instance():
    """获取全局微信实例"""
    global _wechat_instance
    
    with _wechat_lock:
        if _wechat_instance is None:
            Logger.info("创建主线程版微信实例...")
            _wechat_instance = WeChatHelperMainThreadFinal()
        return _wechat_instance


def send_message(message, recipient):
    """发送消息的便捷方法"""
    wechat = get_wechat_instance()
    return wechat.send_message(message, recipient)


def send_message_to_multiple_recipients(message, recipients):
    """发送消息给多个接收者的便捷方法"""
    success_count = 0
    
    if not isinstance(recipients, list):
        recipients = [recipients]
    
    for recipient in recipients:
        if recipient and recipient.strip():
            wechat = get_wechat_instance()
            if wechat.send_message(message, recipient):
                success_count += 1
    
    Logger.info(f"已向 {success_count}/{len(recipients)} 个接收者发送消息")
    return success_count


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
        'note': '主线程版微信工具无统计功能'
    }


def clear_sent_messages():
    """清理已发送消息记录（兼容性方法，无记录）"""
    Logger.info("主线程版微信工具无消息记录需要清理")


def reset_wechat_instance():
    """重置微信实例（兼容性方法）"""
    global _wechat_instance
    with _wechat_lock:
        _wechat_instance = None
        Logger.info("主线程版微信实例已重置")


def start_main_thread_worker():
    """启动主线程工作器（必须在主线程中调用）"""
    wechat = get_wechat_instance()
    return wechat.process_main_thread_tasks()


def stop_main_thread_worker():
    """停止主线程工作器"""
    global _wechat_instance
    if _wechat_instance:
        _wechat_instance.stop()
        _wechat_instance = None 