#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基于文件锁的跨进程微信窗口互斥访问机制
解决多个Python进程同时操作微信窗口的竞争问题
"""

import os
import time
import fcntl
import threading
import tempfile
from contextlib import contextmanager
from utils.logger_utils import Logger


class WeChatProcessLock:
    """基于文件锁的微信进程锁"""
    
    def __init__(self, lock_file_path=None, timeout=60):
        """
        初始化进程锁
        
        Args:
            lock_file_path: 锁文件路径，默认在系统临时目录
            timeout: 默认超时时间（秒）
        """
        if lock_file_path is None:
            # 使用系统临时目录
            temp_dir = tempfile.gettempdir()
            lock_file_path = os.path.join(temp_dir, "wechat_process.lock")
        
        self.lock_file_path = lock_file_path
        self.default_timeout = timeout
        self.lock_file = None
        
        # 统计信息
        self.stats = {
            'total_attempts': 0,
            'successful_locks': 0,
            'timeout_failures': 0,
            'max_wait_time': 0.0,
            'total_wait_time': 0.0
        }
        
        Logger.info(f"微信进程锁初始化完成，锁文件: {self.lock_file_path}")
    
    @contextmanager
    def acquire(self, operation_type="unknown", recipient=None, timeout=None):
        """
        获取微信进程锁的上下文管理器
        
        Args:
            operation_type: 操作类型
            recipient: 接收者
            timeout: 超时时间，None使用默认值
        """
        if timeout is None:
            timeout = self.default_timeout
        
        process_id = os.getpid()
        thread_name = threading.current_thread().name
        start_time = time.time()
        
        self.stats['total_attempts'] += 1
        
        Logger.info(f"[PID:{process_id}][{thread_name}] 正在等待微信进程锁 - 操作: {operation_type}, 接收者: {recipient}")
        
        try:
            # 打开锁文件
            self.lock_file = open(self.lock_file_path, 'w')
            
            # 尝试获取独占锁
            lock_acquired = False
            wait_start = time.time()
            
            while time.time() - wait_start < timeout:
                try:
                    # 尝试非阻塞获取独占锁
                    fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    lock_acquired = True
                    break
                except BlockingIOError:
                    # 锁被其他进程占用，等待一小段时间后重试
                    time.sleep(0.1)
            
            if not lock_acquired:
                wait_time = time.time() - wait_start
                self.stats['timeout_failures'] += 1
                Logger.error(f"[PID:{process_id}][{thread_name}] 获取微信进程锁超时 ({wait_time:.2f}s)")
                raise TimeoutError(f"获取微信进程锁超时 ({wait_time:.2f}s)")
            
            wait_time = time.time() - wait_start
            self.stats['successful_locks'] += 1
            self.stats['total_wait_time'] += wait_time
            if wait_time > self.stats['max_wait_time']:
                self.stats['max_wait_time'] = wait_time
            
            # 写入锁信息
            lock_info = f"PID:{process_id} Thread:{thread_name} Operation:{operation_type} Recipient:{recipient} Time:{time.time()}\n"
            self.lock_file.write(lock_info)
            self.lock_file.flush()
            
            Logger.info(f"[PID:{process_id}][{thread_name}] 已获取微信进程锁 (等待时间: {wait_time:.2f}s)")
            
            operation_start = time.time()
            
            try:
                yield self
                operation_duration = time.time() - operation_start
                Logger.info(f"[PID:{process_id}][{thread_name}] 微信操作完成 (操作耗时: {operation_duration:.2f}s)")
            except Exception as e:
                operation_duration = time.time() - operation_start
                Logger.error(f"[PID:{process_id}][{thread_name}] 微信操作异常 (操作耗时: {operation_duration:.2f}s): {e}")
                raise
                
        finally:
            # 释放锁
            if self.lock_file:
                try:
                    fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                    self.lock_file.close()
                    total_time = time.time() - start_time
                    Logger.info(f"[PID:{process_id}][{thread_name}] 已释放微信进程锁 (总耗时: {total_time:.2f}s)")
                except Exception as e:
                    Logger.error(f"[PID:{process_id}][{thread_name}] 释放微信进程锁时出错: {e}")
                finally:
                    self.lock_file = None
    
    def get_stats(self):
        """获取锁使用统计信息"""
        avg_wait_time = 0.0
        if self.stats['successful_locks'] > 0:
            avg_wait_time = self.stats['total_wait_time'] / self.stats['successful_locks']
        
        success_rate = 0.0
        if self.stats['total_attempts'] > 0:
            success_rate = (self.stats['successful_locks'] / self.stats['total_attempts']) * 100
        
        return {
            'total_attempts': self.stats['total_attempts'],
            'successful_locks': self.stats['successful_locks'],
            'timeout_failures': self.stats['timeout_failures'],
            'success_rate': f"{success_rate:.1f}%",
            'average_wait_time': f"{avg_wait_time:.2f}s",
            'max_wait_time': f"{self.stats['max_wait_time']:.2f}s",
            'lock_file': self.lock_file_path
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_attempts': 0,
            'successful_locks': 0,
            'timeout_failures': 0,
            'max_wait_time': 0.0,
            'total_wait_time': 0.0
        }
        Logger.info("微信进程锁统计信息已重置")
    
    def is_locked(self):
        """检查锁文件是否被占用"""
        try:
            with open(self.lock_file_path, 'r') as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    return False  # 锁可用
                except BlockingIOError:
                    return True   # 锁被占用
        except FileNotFoundError:
            return False  # 锁文件不存在，锁可用
        except Exception:
            return False  # 其他错误，假设锁可用
    
    def get_lock_info(self):
        """获取当前锁文件信息"""
        try:
            if os.path.exists(self.lock_file_path):
                with open(self.lock_file_path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        return content
            return "锁文件不存在或为空"
        except Exception as e:
            return f"读取锁文件失败: {e}"


# 全局锁实例
_wechat_process_lock = None
_lock_init_lock = threading.Lock()


def get_wechat_process_lock():
    """获取全局微信进程锁实例"""
    global _wechat_process_lock
    
    if _wechat_process_lock is None:
        with _lock_init_lock:
            if _wechat_process_lock is None:
                _wechat_process_lock = WeChatProcessLock()
    
    return _wechat_process_lock


@contextmanager
def acquire_wechat_process_lock(operation_type="unknown", recipient=None, timeout=None):
    """获取微信进程锁的便捷方法"""
    lock = get_wechat_process_lock()
    with lock.acquire(operation_type, recipient, timeout):
        yield


def get_wechat_lock_stats():
    """获取微信进程锁统计信息"""
    lock = get_wechat_process_lock()
    return lock.get_stats()


def reset_wechat_lock_stats():
    """重置微信进程锁统计信息"""
    lock = get_wechat_process_lock()
    lock.reset_stats()


def is_wechat_locked():
    """检查微信进程锁是否被占用"""
    lock = get_wechat_process_lock()
    return lock.is_locked()


def get_wechat_lock_info():
    """获取微信进程锁信息"""
    lock = get_wechat_process_lock()
    return lock.get_lock_info()


if __name__ == "__main__":
    # 测试代码
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "status":
            print("微信进程锁状态:")
            print(f"是否被占用: {'是' if is_wechat_locked() else '否'}")
            print(f"锁信息: {get_wechat_lock_info()}")
            print(f"统计信息: {get_wechat_lock_stats()}")
            
        elif command == "test":
            # 简单测试
            with acquire_wechat_process_lock("test", "测试"):
                print(f"进程 {os.getpid()} 获得锁，等待5秒...")
                time.sleep(5)
                print(f"进程 {os.getpid()} 即将释放锁")
                
        else:
            print("用法: python wechat_process_lock.py [status|test]")
    else:
        print("微信进程锁模块")
        print(get_wechat_lock_stats())