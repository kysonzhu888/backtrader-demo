import logging
import time
import os
import queue
import threading
from datetime import datetime

import environment


class WeChatHelper:
    def __init__(self):
        import platform
        if platform.system() == 'Windows':
            if os.getenv('DEBUG_MODE') == '1':
                self.wx = None
            else:
                from wxauto import WeChat
                self.wx = WeChat()
        else:
            self.wx = None
            
        # 创建消息队列和信号量
        self.message_queue = queue.Queue()
        self.semaphore = threading.Semaphore(1)  # 限制同时只有一个发送线程
        self.last_send_time = {}  # 记录每个接收者最后发送时间
        
        # 启动消息处理线程
        self.message_thread = threading.Thread(target=self._process_message_queue, daemon=True)
        self.message_thread.start()

    def _process_message_queue(self):
        """处理消息队列的后台线程"""
        while True:
            try:
                message, recipient = self.message_queue.get()
                self._send_message_safe(message, recipient)
                self.message_queue.task_done()
            except Exception as e:
                logging.error(f"处理消息队列时出错: {str(e)}")

    def _send_message_safe(self, message, recipient):
        """安全地发送消息，包含重试机制"""
        with self.semaphore:
            try:
                # 检查是否需要等待
                current_time = datetime.now()
                if recipient in self.last_send_time:
                    time_since_last = (current_time - self.last_send_time[recipient]).total_seconds()
                    if time_since_last < 2:  # 如果距离上次发送不到2秒
                        time.sleep(2 - time_since_last)  # 等待剩余时间

                # 发送消息
                if self.wx:
                    self.wx.SendMsg(message, recipient)
                else:
                    print(f"[模拟发送] {recipient}: {message}")

                # 更新最后发送时间
                self.last_send_time[recipient] = datetime.now()
                
            except Exception as e:
                logging.error(f"发送消息时出错: {str(e)}")
                # 如果发送失败，等待后重试
                time.sleep(2)
                try:
                    if self.wx:
                        self.wx.SendMsg(message, recipient)
                    else:
                        print(f"[模拟发送重试] {recipient}: {message}")
                except Exception as retry_e:
                    logging.error(f"重试发送消息时出错: {str(retry_e)}")

    def send_message(self, message, recipient):
        """将消息添加到队列"""
        if message is None:
            logging.info("不发送空信息")
            return
        self.message_queue.put((message, recipient))

    def send_message_to_multiple_recipients(self, message, recipients):
        """发送消息给多个接收者"""
        if message is None:
            logging.info("不发送空信息")
            return
            
        if not isinstance(recipients, list):
            recipients = [recipients]

        for recipient in recipients:
            self.send_message(message, recipient)

    def send_file(self, file_path):
        """发送文件"""
        if self.wx:
            self.wx.SendFiles(file_path)
        else:
            print(f"[模拟发送] {file_path}")

    def get_client(self):
        return self.wx
