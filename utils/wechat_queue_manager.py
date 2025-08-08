#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
微信窗口队列管理器
解决多进程同时操作微信窗口的竞争问题
"""

import time
import threading
import queue
from contextlib import contextmanager
from utils.logger_utils import Logger


class WeChatQueueManager:
    """微信窗口访问队列管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化队列管理器"""
        if self._initialized:
            return
            
        # 微信窗口访问信号量 - 同时只允许1个进程操作微信窗口
        self._wechat_semaphore = threading.Semaphore(1)
        
        # 操作队列 - 记录操作历史和统计
        self._operation_queue = queue.Queue()
        self._operation_history = []
        self._operation_stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'average_wait_time': 0.0,
            'max_wait_time': 0.0
        }
        
        # 当前操作信息
        self._current_operation = {
            'thread_name': None,
            'operation_type': None,
            'recipient': None,
            'start_time': None
        }
        
        self._initialized = True
        Logger.info("微信队列管理器初始化完成")
    
    @contextmanager
    def acquire_wechat_window(self, operation_type, recipient=None, timeout=30):
        """
        获取微信窗口访问权限的上下文管理器
        
        Args:
            operation_type: 操作类型 ('send_message', 'send_file', 'chat_switch')
            recipient: 接收者
            timeout: 超时时间（秒）
        """
        thread_name = threading.current_thread().name
        start_time = time.time()
        
        Logger.info(f"[{thread_name}] 正在等待微信窗口访问权限 - 操作: {operation_type}, 接收者: {recipient}")
        
        # 尝试获取信号量
        acquired = self._wechat_semaphore.acquire(timeout=timeout)
        
        if not acquired:
            wait_time = time.time() - start_time
            Logger.error(f"[{thread_name}] 获取微信窗口访问权限超时 ({wait_time:.2f}s)")
            self._update_stats(False, wait_time)
            raise TimeoutError(f"获取微信窗口访问权限超时 ({wait_time:.2f}s)")
        
        wait_time = time.time() - start_time
        Logger.info(f"[{thread_name}] 已获取微信窗口访问权限 (等待时间: {wait_time:.2f}s)")
        
        # 记录当前操作
        self._current_operation.update({
            'thread_name': thread_name,
            'operation_type': operation_type,
            'recipient': recipient,
            'start_time': time.time()
        })
        
        operation_success = False
        
        try:
            yield self  # 执行用户操作
            operation_success = True
            Logger.info(f"[{thread_name}] 微信操作完成 - 操作: {operation_type}")
            
        except Exception as e:
            Logger.error(f"[{thread_name}] 微信操作异常 - 操作: {operation_type}, 错误: {e}")
            raise
            
        finally:
            # 操作完成后的清理
            operation_duration = time.time() - self._current_operation['start_time']
            
            # 记录操作历史
            operation_record = {
                'thread_name': thread_name,
                'operation_type': operation_type,
                'recipient': recipient,
                'wait_time': wait_time,
                'operation_duration': operation_duration,
                'success': operation_success,
                'timestamp': time.time()
            }
            
            self._operation_history.append(operation_record)
            
            # 保持历史记录在合理范围内
            if len(self._operation_history) > 100:
                self._operation_history = self._operation_history[-50:]
            
            # 更新统计信息
            self._update_stats(operation_success, wait_time)
            
            # 清理当前操作信息
            self._current_operation = {
                'thread_name': None,
                'operation_type': None,
                'recipient': None,
                'start_time': None
            }
            
            # 释放信号量
            self._wechat_semaphore.release()
            Logger.info(f"[{thread_name}] 已释放微信窗口访问权限 (操作耗时: {operation_duration:.2f}s)")
    
    def _update_stats(self, success, wait_time):
        """更新统计信息"""
        self._operation_stats['total_operations'] += 1
        
        if success:
            self._operation_stats['successful_operations'] += 1
        else:
            self._operation_stats['failed_operations'] += 1
        
        # 更新等待时间统计
        if wait_time > self._operation_stats['max_wait_time']:
            self._operation_stats['max_wait_time'] = wait_time
        
        total_ops = self._operation_stats['total_operations']
        current_avg = self._operation_stats['average_wait_time']
        self._operation_stats['average_wait_time'] = (current_avg * (total_ops - 1) + wait_time) / total_ops
    
    def get_queue_status(self):
        """获取队列状态"""
        return {
            'available_permits': self._wechat_semaphore._value,  # 可用许可数
            'current_operation': self._current_operation.copy(),
            'queue_size': self._operation_queue.qsize(),
            'stats': self._operation_stats.copy(),
            'recent_operations': self._operation_history[-10:] if self._operation_history else []
        }
    
    def get_stats(self):
        """获取详细统计信息"""
        status = self.get_queue_status()
        
        # 计算成功率
        total = status['stats']['total_operations']
        success_rate = (status['stats']['successful_operations'] / total * 100) if total > 0 else 0
        
        return {
            'total_operations': total,
            'success_rate': f"{success_rate:.1f}%",
            'average_wait_time': f"{status['stats']['average_wait_time']:.2f}s",
            'max_wait_time': f"{status['stats']['max_wait_time']:.2f}s",
            'current_operation': status['current_operation'],
            'available_permits': status['available_permits']
        }
    
    def reset_stats(self):
        """重置统计信息"""
        with self._lock:
            self._operation_history.clear()
            self._operation_stats = {
                'total_operations': 0,
                'successful_operations': 0,
                'failed_operations': 0,
                'average_wait_time': 0.0,
                'max_wait_time': 0.0
            }
            Logger.info("微信队列管理器统计信息已重置")


# 全局实例
def get_wechat_queue_manager():
    """获取微信队列管理器单例"""
    return WeChatQueueManager()


# 便捷方法
def acquire_wechat_window(operation_type, recipient=None, timeout=30):
    """获取微信窗口访问权限（便捷方法）"""
    manager = get_wechat_queue_manager()
    return manager.acquire_wechat_window(operation_type, recipient, timeout)


def get_wechat_queue_status():
    """获取微信队列状态（便捷方法）"""
    manager = get_wechat_queue_manager()
    return manager.get_queue_status()


def get_wechat_queue_stats():
    """获取微信队列统计信息（便捷方法）"""
    manager = get_wechat_queue_manager()
    return manager.get_stats()


def reset_wechat_queue_stats():
    """重置微信队列统计信息（便捷方法）"""
    manager = get_wechat_queue_manager()
    return manager.reset_stats()