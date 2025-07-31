#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一的任务调度器
管理所有定时任务的启动时间
"""

import os
import time
import logging
from datetime import datetime, timedelta
from threading import Timer
from typing import Dict, Callable, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from utils.date_utils import DateUtils
from utils.logger_utils import Logger


class TaskFrequency(Enum):
    """任务频率枚举"""
    DAILY = "daily"           # 每日执行
    WEEKLY = "weekly"         # 每周执行
    MONTHLY = "monthly"       # 每月执行
    HOURLY = "hourly"         # 每小时执行
    CUSTOM = "custom"         # 自定义间隔


@dataclass
class TaskConfig:
    """任务配置"""
    name: str                          # 任务名称
    function: Callable                 # 执行函数
    hour: int = 8                      # 执行小时 (0-23)
    minute: int = 0                    # 执行分钟 (0-59)
    second: int = 0                    # 执行秒数 (0-59)
    frequency: TaskFrequency = TaskFrequency.DAILY  # 执行频率
    custom_interval_hours: int = 0     # 自定义间隔小时数
    custom_interval_minutes: int = 0   # 自定义间隔分钟数
    enabled: bool = True               # 是否启用
    description: str = ""              # 任务描述
    debug_delay: int = 3               # 调试模式下的延迟秒数
    run_in_main_thread: bool = False   # 是否在主线程中执行（用于微信相关任务）


class TaskScheduler:
    """统一的任务调度器"""
    
    def __init__(self):
        self.tasks: Dict[str, TaskConfig] = {}
        self.timers: Dict[str, Timer] = {}
        self.running = False
        
        # 检查调试模式
        self.debug_mode = os.getenv('DEBUG_MODE') == '1'
        if self.debug_mode:
            Logger.info("🔧 任务调度器运行在调试模式下 - 所有任务将在3秒后执行")
        
        # 注册所有预定义任务
        self._register_default_tasks()
        
        Logger.info("TaskScheduler 初始化完成")
    
    def _register_default_tasks(self):
        """注册所有预定义的定时任务"""
        

                # 期货数据预加载器 - 每日 7:10
        self.register_task(TaskConfig(
            name="features_data_preloader",
            function=self._import_and_run_task("features_data_preloader", "run_data_preloader"),
            hour=7, minute=10,
            description="期货数据预加载器 - 预加载主力合约数据",
            frequency=TaskFrequency.DAILY
        ))
        
        # 日线数据加载器 - 每日 7:48
        self.register_task(TaskConfig(
            name="features_daily_loader",
            function=self._import_and_run_task("features_daily_loader", "run_daily_loader"),
            hour=7, minute=48,
            description="日线数据加载器 - 加载期货日线数据",
            frequency=TaskFrequency.DAILY
        ))
        
        # 期货日报 - 每日
        self.register_task(TaskConfig(
            name="features_daily_report",
            function=self._import_and_run_task("features_daily_report", "run_daily_report"),
            hour=8, minute=38,
            description="期货日报 - 每日商品期货涨跌统计",
            frequency=TaskFrequency.DAILY,
            run_in_main_thread=True  # 微信相关任务在主线程中执行
        ))
        
        # 早间新闻播报 - 每日 8:05
        self.register_task(TaskConfig(
            name="news_reporter",
            function=self._import_and_run_task("news_reporter", "news_report"),
            hour=8, minute=5,
            description="早间新闻播报 - 财经新闻和比特币价格",
            frequency=TaskFrequency.DAILY,
            run_in_main_thread=True  # 微信相关任务在主线程中执行
        ))
        
        # 天气播报 - 每2小时执行一次
        # self.register_task(TaskConfig(
        #     name="weather_report",
        #     function=self._import_and_run_task("weather_report", "run_weather_report"),
        #     hour=0, minute=12,
        #     description="天气播报 - 每2小时播报一次天气信息",
        #     frequency=TaskFrequency.CUSTOM,
        #     custom_interval_hours=2,
        #     run_in_main_thread=True  # 微信相关任务在主线程中执行
        # ))
        
        # 期货周报 - 每周一 7:25
        self.register_task(TaskConfig(
            name="features_weekly_report",
            function=self._import_and_run_task("features_weekly_report", "run_weekly_report"),
            hour=7, minute=25,
            description="期货周报 - 每周商品期货涨跌统计",
            frequency=TaskFrequency.WEEKLY,
            run_in_main_thread=True  # 微信相关任务在主线程中执行
        ))
        
        # 期货月报 - 每月1号 7:30
        self.register_task(TaskConfig(
            name="features_monthly_report",
            function=self._import_and_run_task("features_monthly_report", "run_monthly_report"),
            hour=7, minute=30,
            description="期货月报 - 每月商品期货涨跌统计",
            frequency=TaskFrequency.MONTHLY
        ))
        
        # 港股TOP10播报 - 每日 19:30
        # self.register_task(TaskConfig(
        #     name="hk_top10_broadcaster",
        #     function=self._import_and_run_task("hk_top10_broadcaster", "run_hk_top10_broadcast"),
        #     hour=19, minute=30,
        #     description="港股TOP10播报 - 港股涨跌幅TOP10",
        #     frequency=TaskFrequency.DAILY,
        #     run_in_main_thread=True  # 微信相关任务在主线程中执行
        # ))
        
        # # 实时新闻 - 每小时执行
        # self.register_task(TaskConfig(
        #     name="live_news",
        #     function=self._import_and_run_task("live_news", "run_live_news"),
        #     hour=0, minute=23,
        #     description="实时新闻播报 - 每小时播报最新新闻",
        #     frequency=TaskFrequency.HOURLY,
        #     run_in_main_thread=True  # 微信相关任务在主线程中执行
        # ))
        
        # 数据库清理 - 每日 2:00
        self.register_task(TaskConfig(
            name="regular_cleanup_db",
            function=self._import_and_run_task("regular_cleanup_db", "run_cleanup"),
            hour=2, minute=0,
            description="数据库清理 - 清理过期数据",
            frequency=TaskFrequency.DAILY
        ))
        
        # 持仓交易策略 - 每日 14:30
        # self.register_task(TaskConfig(
        #     name="holder_trade_strategy",
        #     function=self._import_and_run_task("holder_trade_strategy", "run_strategy"),
        #     hour=23, minute=33,
        #     description="持仓交易策略 - 执行交易策略",
        #     frequency=TaskFrequency.DAILY,
        #     run_in_main_thread=True  # 微信相关任务在主线程中执行
        # ))
        
        # 分钟级监控 - 每5分钟执行
        self.register_task(TaskConfig(
            name="features_min_monitor",
            function=self._import_and_run_task("features_min_monitor", "run_min_monitor"),
            hour=0, minute=0,
            description="分钟级监控 - 监控期货价格变化",
            frequency=TaskFrequency.CUSTOM,
            custom_interval_minutes=5,
            run_in_main_thread=True  # 微信相关任务在主线程中执行
        ))
    
    def _import_and_run_task(self, module_name: str, function_name: str) -> Callable:
        """动态导入并返回任务函数"""
        def task_wrapper():
            try:
                module = __import__(f"tasks.{module_name}", fromlist=[function_name])
                if hasattr(module, function_name):
                    func = getattr(module, function_name)
                    if callable(func):
                        func()
                    else:
                        Logger.error(f"任务 {module_name}.{function_name} 不是可调用函数")
                else:
                    Logger.error(f"模块 {module_name} 中未找到函数 {function_name}")
            except Exception as e:
                Logger.error(f"执行任务 {module_name}.{function_name} 时出错: {e}")
        
        return task_wrapper
    
    def register_task(self, task_config: TaskConfig) -> None:
        """注册任务"""
        self.tasks[task_config.name] = task_config
        Logger.info(f"注册任务: {task_config.name} - {task_config.description}")
    
    def unregister_task(self, task_name: str) -> bool:
        """注销任务"""
        if task_name in self.tasks:
            del self.tasks[task_name]
            Logger.info(f"注销任务: {task_name}")
            return True
        return False
    
    def enable_task(self, task_name: str) -> bool:
        """启用任务"""
        if task_name in self.tasks:
            self.tasks[task_name].enabled = True
            Logger.info(f"启用任务: {task_name}")
            return True
        return False
    
    def disable_task(self, task_name: str) -> bool:
        """禁用任务"""
        if task_name in self.tasks:
            self.tasks[task_name].enabled = False
            Logger.info(f"禁用任务: {task_name}")
            return True
        return False
    
    def get_next_run_time(self, task_config: TaskConfig) -> datetime:
        """计算下次运行时间"""
        now = DateUtils.now()
        
        if task_config.frequency == TaskFrequency.DAILY:
            # 每日任务
            next_run = now.replace(
                hour=task_config.hour,
                minute=task_config.minute,
                second=task_config.second,
                microsecond=0
            )
            if now >= next_run:
                next_run += timedelta(days=1)
                
        elif task_config.frequency == TaskFrequency.WEEKLY:
            # 每周任务（周一执行）
            days_ahead = 7 - now.weekday()  # 距离下周一的天数
            if days_ahead == 7:  # 如果今天是周一
                days_ahead = 0
            next_run = now.replace(
                hour=task_config.hour,
                minute=task_config.minute,
                second=task_config.second,
                microsecond=0
            ) + timedelta(days=days_ahead)
            if now >= next_run:
                next_run += timedelta(days=7)
                
        elif task_config.frequency == TaskFrequency.MONTHLY:
            # 每月任务（每月1号执行）
            if now.day == 1 and now.hour >= task_config.hour and now.minute >= task_config.minute:
                # 如果今天是1号且时间已过，则下个月1号执行
                next_run = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
            else:
                # 本月1号或下个月1号
                next_run = now.replace(day=1, hour=task_config.hour, minute=task_config.minute, second=task_config.second, microsecond=0)
                if now >= next_run:
                    next_run = (next_run + timedelta(days=32)).replace(day=1)
                    
        elif task_config.frequency == TaskFrequency.HOURLY:
            # 每小时任务
            next_run = now.replace(minute=task_config.minute, second=task_config.second, microsecond=0)
            if now >= next_run:
                next_run += timedelta(hours=1)
                
        elif task_config.frequency == TaskFrequency.CUSTOM:
            # 自定义间隔任务
            interval_seconds = task_config.custom_interval_hours * 3600 + task_config.custom_interval_minutes * 60
            if interval_seconds > 0:
                next_run = now + timedelta(seconds=interval_seconds)
            else:
                # 默认按小时和分钟设置
                next_run = now.replace(
                    hour=task_config.hour,
                    minute=task_config.minute,
                    second=task_config.second,
                    microsecond=0
                )
                if now >= next_run:
                    next_run += timedelta(days=1)
        else:
            # 默认每日执行
            next_run = now.replace(
                hour=task_config.hour,
                minute=task_config.minute,
                second=task_config.second,
                microsecond=0
            )
            if now >= next_run:
                next_run += timedelta(days=1)
        
        return next_run
    
    def schedule_task(self, task_name: str) -> None:
        """调度单个任务"""
        if task_name not in self.tasks:
            Logger.error(f"任务 {task_name} 不存在")
            return
        
        task_config = self.tasks[task_name]
        if not task_config.enabled:
            Logger.info(f"任务 {task_name} 已禁用，跳过调度")
            return
        
        next_run = self.get_next_run_time(task_config)
        now = DateUtils.now()
        delay = (next_run - now).total_seconds()
        
        # 调试模式处理
        if os.getenv('DEBUG_MODE') == '1':
            delay = task_config.debug_delay
        
        Logger.info(f"任务 {task_name} 将在 {next_run.strftime('%Y-%m-%d %H:%M:%S')} 执行，延迟 {delay:.2f} 秒")
        
        def run_and_reschedule():
            try:
                Logger.info(f"开始执行任务: {task_name}")
                
                # 检查是否需要在主线程中执行
                if task_config.run_in_main_thread:
                    Logger.info(f"任务 {task_name} 将在主线程中执行")
                    # 在主线程中执行任务
                    import threading
                    if threading.current_thread() == threading.main_thread():
                        task_config.function()
                    else:
                        Logger.warning(f"任务 {task_name} 需要在主线程中执行，但当前在子线程中")
                        # 这里可以添加主线程执行逻辑
                        task_config.function()
                else:
                    # 在子线程中执行任务
                    task_config.function()
                    
                Logger.info(f"任务 {task_name} 执行完成")
            except Exception as e:
                Logger.error(f"任务 {task_name} 执行失败: {e}")
            finally:
                # 重新调度下次执行
                if self.running and task_config.enabled:
                    self.schedule_task(task_name)
        
        # 创建定时器
        timer = Timer(delay, run_and_reschedule)
        timer.start()
        self.timers[task_name] = timer
    
    def start_all_tasks(self) -> None:
        """启动所有任务"""
        if self.running:
            Logger.warning("任务调度器已在运行")
            return
        
        self.running = True
        Logger.info("启动所有定时任务...")
        
        for task_name in self.tasks:
            if self.tasks[task_name].enabled:
                self.schedule_task(task_name)
        
        Logger.info(f"已启动 {len([t for t in self.tasks.values() if t.enabled])} 个任务")
    
    def stop_all_tasks(self) -> None:
        """停止所有任务"""
        if not self.running:
            Logger.warning("任务调度器未在运行")
            return
        
        self.running = False
        Logger.info("停止所有定时任务...")
        
        for task_name, timer in self.timers.items():
            if timer.is_alive():
                timer.cancel()
                Logger.info(f"已停止任务: {task_name}")
        
        self.timers.clear()
        Logger.info("所有任务已停止")
    
    def get_task_status(self) -> List[Dict]:
        """获取所有任务状态"""
        status_list = []
        now = DateUtils.now()
        
        for task_name, task_config in self.tasks.items():
            next_run = self.get_next_run_time(task_config)
            delay = (next_run - now).total_seconds()
            
            # 调试模式处理
            if self.debug_mode:
                delay = task_config.debug_delay
            
            status = {
                'name': task_name,
                'description': task_config.description,
                'enabled': task_config.enabled,
                'frequency': task_config.frequency.value,
                'next_run': next_run.strftime('%Y-%m-%d %H:%M:%S'),
                'delay_seconds': max(0, delay),
                'is_running': task_name in self.timers and self.timers[task_name].is_alive()
            }
            status_list.append(status)
        
        return status_list
    
    def get_task_info(self, task_name: str) -> Optional[Dict]:
        """获取特定任务信息"""
        if task_name not in self.tasks:
            return None
        
        task_config = self.tasks[task_name]
        next_run = self.get_next_run_time(task_config)
        now = DateUtils.now()
        delay = (next_run - now).total_seconds()
        
        # 调试模式处理
        if self.debug_mode:
            delay = task_config.debug_delay
        
        return {
            'name': task_name,
            'description': task_config.description,
            'enabled': task_config.enabled,
            'frequency': task_config.frequency.value,
            'schedule': f"{task_config.hour:02d}:{task_config.minute:02d}:{task_config.second:02d}",
            'next_run': next_run.strftime('%Y-%m-%d %H:%M:%S'),
            'delay_seconds': max(0, delay),
            'is_running': task_name in self.timers and self.timers[task_name].is_alive()
        }


# 全局任务调度器实例
task_scheduler = TaskScheduler()


def get_task_scheduler() -> TaskScheduler:
    """获取全局任务调度器实例"""
    return task_scheduler


def start_scheduler() -> None:
    """启动任务调度器"""
    task_scheduler.start_all_tasks()


def stop_scheduler() -> None:
    """停止任务调度器"""
    task_scheduler.stop_all_tasks()


def get_all_task_status() -> List[Dict]:
    """获取所有任务状态"""
    return task_scheduler.get_task_status()


if __name__ == "__main__":
    # 测试任务调度器
    print("=== 任务调度器测试 ===")
    
    # 显示所有任务状态
    status_list = get_all_task_status()
    for status in status_list:
        print(f"任务: {status['name']}")
        print(f"  描述: {status['description']}")
        print(f"  启用: {status['enabled']}")
        print(f"  频率: {status['frequency']}")
        print(f"  下次执行: {status['next_run']}")
        print(f"  延迟: {status['delay_seconds']:.2f} 秒")
        print(f"  运行中: {status['is_running']}")
        print()
    
    # 启动调度器
    print("启动任务调度器...")
    start_scheduler()
    
    try:
        # 保持运行
        while True:
            time.sleep(60)
            print(f"调度器运行中... 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except KeyboardInterrupt:
        print("\n收到停止信号，正在停止调度器...")
        stop_scheduler()
        print("调度器已停止") 