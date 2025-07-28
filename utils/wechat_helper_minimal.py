#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
最简化版 WeChatHelper
去掉所有复杂功能，只保留最基本的发送功能
"""

import time
import os
import platform
from utils.logger_utils import Logger


class WeChatHelperMinimal:
    def __init__(self):
        """初始化微信客户端"""
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

    def send_message(self, message, recipient):
        """发送消息"""
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
            
            # 切换到目标聊天窗口
            self.wx.ChatWith(recipient)
            time.sleep(0.5)  # 等待窗口切换
            
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

    def send_file(self, file_path, recipient=None):
        """发送文件"""
        if not file_path or not os.path.exists(file_path):
            Logger.error(f"文件不存在: {file_path}")
            return False
            
        try:
            if not self.wx:
                Logger.info(f"[模拟发送文件] {file_path}")
                return True
            
            if recipient:
                # 如果有指定接收者，先切换到对应聊天窗口
                self.wx.ChatWith(recipient)
                time.sleep(0.5)  # 等待窗口切换
            
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

    def get_client(self):
        """获取微信客户端实例"""
        return self.wx 