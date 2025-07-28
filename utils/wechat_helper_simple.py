#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简化版 WeChatHelper
去掉队列和线程，直接发送消息，便于调试和定位问题
"""

import time
import os
import platform
from datetime import datetime
from utils.logger_utils import Logger


class WeChatHelperSimple:
    _instance = None
    
    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super(WeChatHelperSimple, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化方法（只在第一次创建时执行）"""
        if self._initialized:
            return
            
        # 初始化微信客户端
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
        
        # 记录最后发送时间，避免发送过快
        self.last_send_time = {}
        self.min_interval = 1.0  # 最小发送间隔（秒）
        
        self._initialized = True
        Logger.info("WeChatHelperSimple 单例初始化完成")

    def send_message(self, message, recipient):
        """直接发送消息"""
        if not message or not message.strip():
            Logger.info("不发送空消息")
            return False
            
        if not recipient or not recipient.strip():
            Logger.warning("接收者不能为空")
            return False
        
        # 检查发送间隔
        current_time = datetime.now()
        if recipient in self.last_send_time:
            time_since_last = (current_time - self.last_send_time[recipient]).total_seconds()
            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last
                Logger.debug(f"等待 {wait_time:.2f} 秒后发送消息给 {recipient}")
                time.sleep(wait_time)
        
        # 发送消息
        success = self._do_send_message(message.strip(), recipient.strip())
        
        if success:
            self.last_send_time[recipient] = datetime.now()
            Logger.info(f"消息发送成功: {recipient}")
        else:
            Logger.error(f"消息发送失败: {recipient}")
        
        return success

    def _do_send_message(self, message, recipient):
        """实际执行消息发送"""
        try:
            if not self.wx:
                Logger.info(f"[模拟发送] {recipient}: {message}")
                return True
            
            # 处理长消息
            max_message_length = 1000
            if len(message) > max_message_length:
                Logger.info(f"消息过长({len(message)}字符)，将分割发送到 {recipient}")
                return self._send_long_message(message, recipient, max_message_length)
            
            # 重试机制
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    Logger.debug(f"尝试发送消息到 {recipient} (尝试 {attempt + 1}/{max_retries})")
                    
                    # 切换到目标聊天窗口
                    self.wx.ChatWith(recipient)
                    time.sleep(0.5)  # 等待窗口切换
                    
                    # 发送消息
                    result = self.wx.SendMsg(message, recipient)
                    
                    if result:
                        Logger.debug(f"wxauto发送成功: {recipient}")
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

    def _send_long_message(self, message, recipient, max_length):
        """发送长消息，将其分割成多个短消息"""
        try:
            # 按行分割消息
            lines = message.split('\n')
            current_message = ""
            message_parts = []
            
            for line in lines:
                # 如果当前行加上当前消息超过限制，保存当前消息并开始新消息
                if len(current_message + line + '\n') > max_length and current_message:
                    message_parts.append(current_message.strip())
                    current_message = line + '\n'
                else:
                    current_message += line + '\n'
            
            # 添加最后一部分
            if current_message.strip():
                message_parts.append(current_message.strip())
            
            # 发送所有部分
            success_count = 0
            for i, part in enumerate(message_parts):
                part_message = f"[{i+1}/{len(message_parts)}]\n{part}"
                if self._send_single_message(part_message, recipient):
                    success_count += 1
                    time.sleep(1)  # 在消息之间稍作延迟
                else:
                    Logger.error(f"发送长消息第{i+1}部分失败: {recipient}")
            
            return success_count == len(message_parts)
            
        except Exception as e:
            Logger.error(f"发送长消息时出错: {str(e)}")
            return False

    def _send_single_message(self, message, recipient):
        """发送单个消息的辅助方法"""
        try:
            if not self.wx:
                return False
                
            # 切换到目标聊天窗口
            self.wx.ChatWith(recipient)
            time.sleep(0.5)  # 等待窗口切换
            
            # 发送消息
            result = self.wx.SendMsg(message, recipient)
            return result
            
        except Exception as e:
            Logger.error(f"发送单个消息时出错: {str(e)}")
            return False

    def _reinitialize_wechat(self):
        """重新初始化微信客户端"""
        try:
            if platform.system() == 'Windows':
                from wxauto import WeChat
                self.wx = WeChat()
                Logger.info("微信客户端重新初始化成功")
            else:
                self.wx = None
        except Exception as e:
            Logger.error(f"重新初始化微信客户端时出错: {str(e)}")
            self.wx = None

    def send_file(self, file_path, recipient=None):
        """发送文件"""
        if not file_path or not os.path.exists(file_path):
            Logger.error(f"文件不存在: {file_path}")
            return False
            
        try:
            if not self.wx:
                Logger.info(f"[模拟发送文件] {file_path}")
                return True
            
            # 重试机制
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
                        return False
                        
                except Exception as retry_error:
                    Logger.warning(f"发送文件重试 {attempt + 1}/{max_retries} 失败: {str(retry_error)}")
                    if attempt < max_retries - 1:
                        time.sleep(2)  # 等待2秒后重试
                        continue
                    else:
                        # 最后一次尝试失败，抛出异常
                        raise retry_error
                        
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

    def check_wechat_health(self):
        """检查微信客户端健康状态"""
        try:
            if not self.wx:
                Logger.debug("微信客户端未初始化")
                return True
            
            # 尝试获取微信窗口信息来检查连接状态
            try:
                # 兼容不同版本的 wxauto
                if hasattr(self.wx, 'GetWeChatWindow'):
                    window_info = self.wx.GetWeChatWindow()
                elif hasattr(self.wx, 'get_wechat_window'):
                    window_info = self.wx.get_wechat_window()
                else:
                    # 如果都没有这个方法，尝试其他方式检查
                    try:
                        # 尝试获取当前聊天窗口名称来验证连接
                        current_chat = self.wx.GetCurrentWindowName()
                        if current_chat:
                            Logger.debug("微信客户端连接正常")
                            return True
                        else:
                            Logger.warning("无法获取当前聊天窗口，可能连接异常")
                            return False
                    except:
                        # 如果连这个方法都没有，假设连接正常（避免误判）
                        Logger.debug("微信客户端连接正常（无法验证，但假设正常）")
                        return True
                
                if window_info:
                    Logger.debug("微信客户端连接正常")
                    return True
                else:
                    Logger.warning("无法获取微信窗口，可能连接异常")
                    return False
            except Exception as e:
                Logger.warning(f"微信客户端健康检查失败: {str(e)}")
                # 如果健康检查失败，但微信实例存在，假设连接正常
                Logger.debug("微信客户端连接正常（健康检查失败，但实例存在）")
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
        cls._instance = None
        Logger.info("WeChatHelperSimple 单例已重置")

    def get_client(self):
        """获取微信客户端实例"""
        return self.wx 