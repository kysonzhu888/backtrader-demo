import time
import os
import queue
import threading
from datetime import datetime
import hashlib

from utils.logger_utils import Logger


class WeChatHelper:
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(WeChatHelper, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化方法（只在第一次创建时执行）"""
        if self._initialized:
            return
            
        import platform
        if platform.system() == 'Windows':
            if os.getenv('DEBUG_MODE') == '1':
                self.wx = None
            else:
                from wxauto import WeChat
                self.wx = WeChat()
        else:
            self.wx = None
            
        # 创建消息队列
        self.message_queue = queue.Queue()
        
        # 线程安全的时间记录和消息去重
        self.last_send_time = {}  # 记录每个接收者最后发送时间
        self.sent_messages = set()  # 记录已发送的消息，防止重复
        self.lock = threading.RLock()  # 可重入锁，用于保护共享资源
        
        # 控制变量
        self.running = True
        self.min_interval = 2.0  # 最小发送间隔（秒）
        
        # 启动消息处理线程
        self.message_thread = threading.Thread(target=self._process_message_queue, daemon=True)
        self.message_thread.start()
        
        self._initialized = True
        Logger.info("WeChatHelper 单例初始化完成")

    def _get_message_hash(self, message, recipient):
        """生成消息的唯一标识"""
        content = f"{message}:{recipient}:{datetime.now().strftime('%Y%m%d%H%M')}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _process_message_queue(self):
        """处理消息队列的后台线程"""
        while self.running:
            try:
                # 从队列获取消息，设置超时以便能够响应停止信号
                try:
                    message, recipient = self.message_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                # 处理消息
                self._send_message_safe(message, recipient)
                self.message_queue.task_done()
                
            except Exception as e:
                Logger.error(f"处理消息队列时出错: {str(e)}")
                # 短暂等待后继续处理
                time.sleep(1)

    def _send_message_safe(self, message, recipient):
        """安全地发送消息，包含重试机制"""
        with self.lock:
            try:
                # 生成消息哈希，用于去重
                message_hash = self._get_message_hash(message, recipient)
                
                # 检查是否已经发送过相同消息
                if message_hash in self.sent_messages:
                    Logger.info(f"跳过重复消息: {recipient}")
                    return
                
                # 检查发送间隔
                current_time = datetime.now()
                if recipient in self.last_send_time:
                    time_since_last = (current_time - self.last_send_time[recipient]).total_seconds()
                    if time_since_last < self.min_interval:
                        wait_time = self.min_interval - time_since_last
                        Logger.debug(f"等待 {wait_time:.2f} 秒后发送消息给 {recipient}")
                        time.sleep(wait_time)

                # 发送消息
                success = self._do_send_message(message, recipient)
                
                if success:
                    # 更新最后发送时间和已发送消息记录
                    self.last_send_time[recipient] = datetime.now()
                    self.sent_messages.add(message_hash)
                    
                    # 清理旧的已发送消息记录（保留最近1000条）
                    if len(self.sent_messages) > 1000:
                        # 简单清理：保留最近的消息哈希
                        self.sent_messages = set(list(self.sent_messages)[-500:])
                    
                    Logger.info(f"消息发送成功: {recipient}")
                else:
                    Logger.error(f"消息发送失败: {recipient}")
                
            except Exception as e:
                Logger.error(f"发送消息时出错: {str(e)}")

    def _do_send_message(self, message, recipient):
        """实际执行消息发送"""
        try:
            if self.wx:
                # 添加重试机制和错误处理
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # 先尝试切换到目标聊天窗口
                        self.wx.ChatWith(recipient)
                        time.sleep(0.5)  # 等待窗口切换
                        
                        # 发送消息
                        result = self.wx.SendMsg(message, recipient)
                        
                        # 检查发送结果
                        if result:
                            return True
                        else:
                            Logger.warning(f"wxauto发送消息返回False (尝试 {attempt + 1}/{max_retries}): {recipient}")
                            if attempt < max_retries - 1:
                                time.sleep(1)  # 等待1秒后重试
                                continue
                            return False
                            
                    except Exception as retry_error:
                        Logger.warning(f"发送消息重试 {attempt + 1}/{max_retries} 失败: {str(retry_error)}")
                        if attempt < max_retries - 1:
                            time.sleep(2)  # 等待2秒后重试
                            continue
                        else:
                            # 最后一次尝试失败，抛出异常
                            raise retry_error
                            
            else:
                # 模拟发送
                print(f"[模拟发送] {recipient}: {message}")
                return True
                
        except Exception as e:
            Logger.error(f"执行消息发送时出错: {str(e)}")
            # 如果是COM错误，尝试重新初始化微信客户端
            if "COM" in str(e) or "-2147467259" in str(e):
                Logger.warning("检测到COM错误，尝试重新初始化微信客户端...")
                try:
                    self._reinitialize_wechat()
                except Exception as reinit_error:
                    Logger.error(f"重新初始化微信客户端失败: {str(reinit_error)}")
            return False

    def _reinitialize_wechat(self):
        """重新初始化微信客户端"""
        try:
            import platform
            if platform.system() == 'Windows':
                from wxauto import WeChat
                self.wx = WeChat()
                Logger.info("微信客户端重新初始化成功")
            else:
                self.wx = None
        except Exception as e:
            Logger.error(f"重新初始化微信客户端时出错: {str(e)}")
            self.wx = None

    def send_message(self, message, recipient):
        """将消息添加到队列"""
        if not message or not message.strip():
            Logger.info("不发送空信息")
            return
            
        if not recipient or not recipient.strip():
            Logger.warning("接收者不能为空")
            return
            
        try:
            self.message_queue.put((message.strip(), recipient.strip()))
            Logger.debug(f"消息已加入队列: {recipient}")
        except queue.Full:
            Logger.error(f"消息队列已满，无法添加消息: {recipient}")

    def send_message_to_multiple_recipients(self, message, recipients):
        """发送消息给多个接收者"""
        if not message or not message.strip():
            Logger.info("不发送空信息")
            return
            
        if not recipients:
            Logger.warning("接收者列表不能为空")
            return
            
        if not isinstance(recipients, list):
            recipients = [recipients]

        success_count = 0
        for recipient in recipients:
            if recipient and recipient.strip():
                self.send_message(message, recipient)
                success_count += 1
            else:
                Logger.warning(f"跳过空的接收者: {recipient}")
        
        Logger.info(f"已向 {success_count} 个接收者发送消息")

    def send_file(self, file_path, recipient=None):
        """发送文件"""
        if not file_path or not os.path.exists(file_path):
            Logger.error(f"文件不存在: {file_path}")
            return False
            
        try:
            if self.wx:
                # 添加重试机制
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        if recipient:
                            # 如果有指定接收者，先切换到对应聊天窗口
                            self.wx.ChatWith(recipient)
                            time.sleep(0.5)  # 等待窗口切换
                        
                        result = self.wx.SendFiles(file_path)
                        if result:
                            Logger.info(f"文件发送成功: {file_path}")
                            return True
                        else:
                            Logger.warning(f"文件发送返回False (尝试 {attempt + 1}/{max_retries}): {file_path}")
                            if attempt < max_retries - 1:
                                time.sleep(1)  # 等待1秒后重试
                                continue
                        Logger.error(f"文件发送失败: {file_path}")
                        return False
                            
                    except Exception as retry_error:
                        Logger.warning(f"发送文件重试 {attempt + 1}/{max_retries} 失败: {str(retry_error)}")
                        if attempt < max_retries - 1:
                            time.sleep(2)  # 等待2秒后重试
                            continue
                        else:
                            # 最后一次尝试失败，抛出异常
                            raise retry_error
            else:
                print(f"[模拟发送文件] {file_path}")
                return True
                
        except Exception as e:
            Logger.error(f"发送文件时出错: {str(e)}")
            # 如果是COM错误，尝试重新初始化微信客户端
            if "COM" in str(e) or "-2147467259" in str(e):
                Logger.warning("检测到COM错误，尝试重新初始化微信客户端...")
                try:
                    self._reinitialize_wechat()
                except Exception as reinit_error:
                    Logger.error(f"重新初始化微信客户端失败: {str(reinit_error)}")
            return False

    def get_client(self):
        """获取微信客户端实例"""
        return self.wx

    def get_queue_size(self):
        """获取当前队列大小"""
        return self.message_queue.qsize()

    def check_wechat_health(self):
        """检查微信客户端健康状态"""
        try:
            if self.wx:
                # 尝试获取微信窗口信息来检查连接状态
                try:
                    # 简单的健康检查：尝试获取微信窗口
                    window_info = self.wx.GetWeChatWindow()
                    if window_info:
                        Logger.debug("微信客户端连接正常")
                        return True
                    else:
                        Logger.warning("无法获取微信窗口，可能连接异常")
                        return False
                except Exception as e:
                    Logger.warning(f"微信客户端健康检查失败: {str(e)}")
                    return False
            else:
                Logger.debug("微信客户端未初始化（调试模式或非Windows系统）")
                return True
        except Exception as e:
            Logger.error(f"检查微信客户端健康状态时出错: {str(e)}")
            return False

    def force_reinitialize(self):
        """强制重新初始化微信客户端"""
        Logger.info("强制重新初始化微信客户端...")
        try:
            self._reinitialize_wechat()
            return self.check_wechat_health()
        except Exception as e:
            Logger.error(f"强制重新初始化失败: {str(e)}")
            return False

    @classmethod
    def get_instance(cls):
        """获取全局单例实例"""
        return cls()

    @classmethod
    def reset_instance(cls):
        """重置单例实例（用于测试或特殊情况）"""
        with cls._lock:
            if cls._instance:
                cls._instance.stop()
                cls._instance = None
            Logger.info("WeChatHelper 单例已重置")

    def get_send_stats(self):
        """获取发送统计信息"""
        with self.lock:
            return {
                'queue_size': self.message_queue.qsize(),
                'sent_messages_count': len(self.sent_messages),
                'recipients_count': len(self.last_send_time),
                'last_send_times': {k: v.isoformat() for k, v in self.last_send_time.items()}
            }

    def clear_sent_messages(self):
        """清理已发送消息记录"""
        with self.lock:
            self.sent_messages.clear()
            Logger.info("已清理发送消息记录")

    def stop(self):
        """停止消息处理"""
        self.running = False
        Logger.info("WeChatHelper 正在停止...")
        
        # 等待队列处理完成
        try:
            self.message_queue.join()
        except Exception as e:
            Logger.warning(f"等待队列处理完成时出错: {e}")
        
        Logger.info("WeChatHelper 已停止")
