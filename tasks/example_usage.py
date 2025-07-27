#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
任务调度器使用示例
展示如何从统一的时间管理类获取任务启动时间
"""

import time
from datetime import datetime

# 方法1: 直接使用调度器启动所有任务
def start_all_scheduled_tasks():
    """启动所有预定义的定时任务"""
    print("=== 启动所有定时任务 ===")
    
    from task_scheduler import start_scheduler, stop_scheduler
    
    try:
        # 启动调度器
        start_scheduler()
        print("所有定时任务已启动")
        
        # 保持运行
        while True:
            time.sleep(60)
            print(f"调度器运行中... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
    except KeyboardInterrupt:
        print("\n收到停止信号...")
        stop_scheduler()
        print("所有任务已停止")

# 方法2: 获取特定任务的启动时间
def get_task_schedule_info():
    """获取任务调度信息"""
    print("=== 获取任务调度信息 ===")
    
    from task_scheduler import get_task_scheduler
    
    scheduler = get_task_scheduler()
    
    # 获取所有任务状态
    status_list = scheduler.get_task_status()
    
    print("当前所有任务调度信息:")
    print("-" * 80)
    print(f"{'任务名称':<20} {'描述':<25} {'时间':<10} {'频率':<10} {'下次执行':<20}")
    print("-" * 80)
    
    for status in status_list:
        if status['enabled']:
            task_config = scheduler.tasks[status['name']]
            schedule_time = f"{task_config.hour:02d}:{task_config.minute:02d}:{task_config.second:02d}"
            print(f"{status['name']:<20} {status['description']:<25} {schedule_time:<10} {status['frequency']:<10} {status['next_run']:<20}")
    
    print("-" * 80)

# 方法3: 修改现有任务以使用统一调度器
def modify_existing_task_example():
    """展示如何修改现有任务"""
    print("=== 修改现有任务示例 ===")
    
    # 原始代码（features_daily_report.py 中的 schedule_task 函数）:
    """
    def schedule_task():
        # 设置下次运行时间
        now = DateUtils.now()
        next_run = now.replace(hour=8, minute=1, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        delay = (next_run - now).total_seconds()

        # 如果是 debug 模式，则立刻执行
        if os.getenv('DEBUG_MODE') == '1':
            delay = 3

        logging.info(f"日报即将在{delay}秒后执行，请等待...")
        Timer(delay, run_daily_report).start()
    """
    
    # 修改后的代码:
    """
    # 删除原有的 schedule_task 函数，改为使用统一调度器
    
    # 在文件末尾添加:
    if __name__ == "__main__":
        # 方法1: 直接运行任务（用于测试）
        run_daily_report()
        
        # 方法2: 使用统一调度器（推荐）
        from tasks.task_scheduler import start_scheduler
        start_scheduler()
    """
    
    print("修改要点:")
    print("1. 删除原有的 schedule_task 函数")
    print("2. 保留 run_daily_report 等核心执行函数")
    print("3. 在 __main__ 中使用统一调度器")
    print("4. 任务配置已在 task_scheduler.py 中预定义")

# 方法4: 添加新任务到调度器
def add_new_task_example():
    """展示如何添加新任务"""
    print("=== 添加新任务示例 ===")
    
    from task_scheduler import TaskScheduler, TaskConfig, TaskFrequency
    
    def new_task_function():
        """新任务的执行函数"""
        print(f"新任务执行: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        # 在这里添加具体的任务逻辑
    
    # 创建任务配置
    new_task = TaskConfig(
        name="my_new_task",
        function=new_task_function,
        hour=15, minute=30,  # 每天15:30执行
        frequency=TaskFrequency.DAILY,
        description="我的新任务 - 示例任务",
        enabled=True
    )
    
    # 注册任务
    scheduler = TaskScheduler()
    scheduler.register_task(new_task)
    
    print(f"新任务已注册: {new_task.name}")
    print(f"执行时间: {new_task.hour:02d}:{new_task.minute:02d}:{new_task.second:02d}")
    print(f"执行频率: {new_task.frequency.value}")

# 方法5: 动态管理任务
def manage_tasks_dynamically():
    """动态管理任务示例"""
    print("=== 动态管理任务示例 ===")
    
    from task_scheduler import get_task_scheduler
    
    scheduler = get_task_scheduler()
    
    # 禁用特定任务
    scheduler.disable_task("news_reporter")
    print("已禁用 news_reporter 任务")
    
    # 启用任务
    scheduler.enable_task("news_reporter")
    print("已启用 news_reporter 任务")
    
    # 获取任务详细信息
    task_info = scheduler.get_task_info("features_daily_report")
    if task_info:
        print(f"期货日报任务详情:")
        print(f"  名称: {task_info['name']}")
        print(f"  描述: {task_info['description']}")
        print(f"  调度时间: {task_info['schedule']}")
        print(f"  下次执行: {task_info['next_run']}")
        print(f"  启用状态: {task_info['enabled']}")

# 方法6: 监控任务状态
def monitor_task_status():
    """监控任务状态"""
    print("=== 监控任务状态 ===")
    
    from task_scheduler import get_all_task_status
    
    while True:
        status_list = get_all_task_status()
        
        print(f"\n任务状态监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)
        
        for status in status_list:
            if status['enabled']:
                status_icon = "🟢" if status['is_running'] else "⚪"
                print(f"{status_icon} {status['name']:<20} 下次执行: {status['next_run']}")
        
        time.sleep(30)  # 每30秒更新一次

def main():
    """主函数 - 展示各种使用方法"""
    print("任务调度器使用示例")
    print("=" * 50)
    
    # 1. 获取任务调度信息
    get_task_schedule_info()
    
    # 2. 展示修改现有任务的方法
    modify_existing_task_example()
    
    # 3. 展示添加新任务的方法
    add_new_task_example()
    
    # 4. 展示动态管理任务
    manage_tasks_dynamically()
    
    print("\n" + "=" * 50)
    print("使用建议:")
    print("1. 对于现有任务，建议逐步迁移到统一调度器")
    print("2. 新任务直接使用 TaskConfig 配置")
    print("3. 使用 get_task_scheduler() 获取调度器实例")
    print("4. 通过 start_scheduler() 启动所有任务")
    print("5. 使用 get_all_task_status() 监控任务状态")
    
    print("\n快速开始:")
    print("from tasks.task_scheduler import start_scheduler")
    print("start_scheduler()  # 启动所有任务")


if __name__ == "__main__":
    main() 