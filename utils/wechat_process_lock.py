#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基于文件锁的跨进程微信窗口互斥访问机制
解决多个Python进程同时操作微信窗口的竞争问题
"""

import os
import time
import threading
import tempfile
import platform
from contextlib import contextmanager
from utils.logger_utils import Logger

# 跨平台文件锁实现
if platform.system() == 'Windows':
    import msvcrt
else:
    import fcntl


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
        self.is_windows = platform.system() == 'Windows'
        
        # 统计信息
        self.stats = {
            'total_attempts': 0,
            'successful_locks': 0,
            'timeout_failures': 0,
            'max_wait_time': 0.0,
            'total_wait_time': 0.0
        }
        
        Logger.info(f"微信进程锁初始化完成，锁文件: {self.lock_file_path} (平台: {platform.system()})")
    
    def _acquire_lock_unix(self, timeout):
        """Unix/Linux/MacOS 系统的锁获取"""
        import fcntl
        
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
            
            return lock_acquired, time.time() - wait_start
            
        except Exception as e:
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            raise e
    
    def _release_lock_unix(self):
        """Unix/Linux/MacOS 系统的锁释放"""
        if self.lock_file:
            try:
                import fcntl
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
            except Exception as e:
                Logger.error(f"释放Unix锁时出错: {e}")
            finally:
                self.lock_file = None
    
    def _acquire_lock_windows(self, timeout):
        """Windows 系统的锁获取 - 使用独占文件创建方式"""
        wait_start = time.time()
        
        while time.time() - wait_start < timeout:
            try:
                # 尝试以独占方式创建锁文件
                # 使用 'x' 模式确保文件不存在时才创建，存在则抛出异常
                self.lock_file = open(self.lock_file_path, 'x')
                return True, time.time() - wait_start
                
            except FileExistsError:
                # 锁文件已存在，说明被其他进程占用
                # 检查是否是僵尸锁文件（进程已结束但文件还在）
                try:
                    # 尝试读取锁文件内容，如果能读取说明文件可能是僵尸锁
                    with open(self.lock_file_path, 'r') as f:
                        content = f.read().strip()
                        if content:
                            # 检查锁文件是否超过5分钟（可能是僵尸锁）
                            import os
                            lock_age = time.time() - os.path.getmtime(self.lock_file_path)
                            if lock_age > 300:  # 5分钟
                                Logger.warning(f"发现可能的僵尸锁文件，年龄: {lock_age:.1f}秒，尝试清理...")
                                try:
                                    os.remove(self.lock_file_path)
                                    continue  # 重新尝试获取锁
                                except Exception as e:
                                    Logger.error(f"清理僵尸锁文件失败: {e}")
                except Exception:
                    pass  # 忽略读取错误
                
                time.sleep(0.1)
                continue
                
            except Exception as e:
                Logger.error(f"Windows锁获取异常: {e}")
                if self.lock_file:
                    try:
                        self.lock_file.close()
                    except:
                        pass
                    self.lock_file = None
                time.sleep(0.1)
                continue
        
        return False, time.time() - wait_start
    
    def _release_lock_windows(self):
        """Windows 系统的锁释放 - 删除锁文件"""
        if self.lock_file:
            try:
                # 关闭文件
                self.lock_file.close()
                
                # 删除锁文件
                import os
                if os.path.exists(self.lock_file_path):
                    os.remove(self.lock_file_path)
                    
            except Exception as e:
                Logger.error(f"释放Windows锁时出错: {e}")
                # 即使删除失败，也要尝试清理文件句柄
                try:
                    import os
                    if os.path.exists(self.lock_file_path):
                        os.remove(self.lock_file_path)
                except:
                    pass
            finally:
                self.lock_file = None
    
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
            # 如果等待时间超过30秒，先尝试清理僵尸锁
            if timeout > 30:
                Logger.info("等待时间较长，先检查是否有僵尸锁...")
                self.cleanup_zombie_lock()
            
            # 根据平台选择锁获取方式
            if self.is_windows:
                lock_acquired, wait_time = self._acquire_lock_windows(timeout)
            else:
                lock_acquired, wait_time = self._acquire_lock_unix(timeout)
            
            if not lock_acquired:
                self.stats['timeout_failures'] += 1
                Logger.error(f"[PID:{process_id}][{thread_name}] 获取微信进程锁超时 ({wait_time:.2f}s)")
                raise TimeoutError(f"获取微信进程锁超时 ({wait_time:.2f}s)")
            
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
                    if self.is_windows:
                        self._release_lock_windows()
                    else:
                        self._release_lock_unix()
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
            if self.is_windows:
                return self._is_locked_windows()
            else:
                return self._is_locked_unix()
        except FileNotFoundError:
            return False  # 锁文件不存在，锁可用
        except Exception:
            return False  # 其他错误，假设锁可用
    
    def _is_locked_unix(self):
        """Unix系统检查锁状态"""
        import fcntl
        try:
            with open(self.lock_file_path, 'r') as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    return False  # 锁可用
                except BlockingIOError:
                    return True   # 锁被占用
        except FileNotFoundError:
            return False
    
    def _is_locked_windows(self):
        """Windows系统检查锁状态 - 基于文件存在性"""
        import os
        try:
            # 简单检查锁文件是否存在
            if os.path.exists(self.lock_file_path):
                # 检查是否是僵尸锁文件
                try:
                    lock_age = time.time() - os.path.getmtime(self.lock_file_path)
                    if lock_age > 300:  # 5分钟以上的锁文件可能是僵尸锁
                        Logger.warning(f"检测到可能的僵尸锁文件，年龄: {lock_age:.1f}秒")
                        return False  # 认为锁可用，让获取锁的逻辑来清理
                    return True  # 锁被占用
                except Exception:
                    return True  # 出错时保守认为被占用
            else:
                return False  # 锁文件不存在，锁可用
        except Exception:
            return False  # 出错时认为锁可用
    
    def get_lock_info(self):
        """获取当前锁文件信息"""
        import os
        try:
            if os.path.exists(self.lock_file_path):
                # 获取文件信息
                stat_info = os.stat(self.lock_file_path)
                file_age = time.time() - stat_info.st_mtime
                
                with open(self.lock_file_path, 'r') as f:
                    content = f.read().strip()
                    
                if content:
                    return f"{content} | 文件年龄: {file_age:.1f}秒"
                else:
                    return f"锁文件为空 | 文件年龄: {file_age:.1f}秒"
            return "锁文件不存在"
        except Exception as e:
            return f"读取锁文件失败: {e}"
    
    def cleanup_zombie_lock(self):
        """清理僵尸锁文件"""
        import os
        try:
            if os.path.exists(self.lock_file_path):
                # 检查文件年龄
                lock_age = time.time() - os.path.getmtime(self.lock_file_path)
                
                if lock_age > 30:  # 30秒以上认为是僵尸锁
                    Logger.warning(f"清理僵尸锁文件，年龄: {lock_age:.1f}秒")
                    os.remove(self.lock_file_path)
                    Logger.info("僵尸锁文件清理成功")
                    return True
                else:
                    Logger.info(f"锁文件较新，年龄: {lock_age:.1f}秒，不清理")
                    return False
            else:
                Logger.info("锁文件不存在，无需清理")
                return True
        except Exception as e:
            Logger.error(f"清理僵尸锁文件失败: {e}")
            return False


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


def cleanup_wechat_zombie_lock():
    """清理微信僵尸锁文件"""
    lock = get_wechat_process_lock()
    return lock.cleanup_zombie_lock()


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