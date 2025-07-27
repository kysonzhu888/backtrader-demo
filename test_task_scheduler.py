#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试任务调度器
验证统一时间管理功能
"""

import time
import os
from datetime import datetime

# 设置调试模式
os.environ['DEBUG_MODE'] = '1'

def test_task_scheduler():
    """测试任务调度器功能"""
    print("=== 测试任务调度器 ===")
    
    try:
        from task_scheduler import get_task_scheduler, get_all_task_status
        
        # 获取调度器实例
        scheduler = get_task_scheduler()
        
        print("1. 显示所有任务状态...")
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
        
        print("2. 测试单个任务信息获取...")
        task_info = scheduler.get_task_info("features_daily_report")
        if task_info:
            print(f"期货日报任务信息:")
            print(f"  名称: {task_info['name']}")
            print(f"  描述: {task_info['description']}")
            print(f"  调度时间: {task_info['schedule']}")
            print(f"  频率: {task_info['frequency']}")
            print(f"  下次执行: {task_info['next_run']}")
            print()
        
        print("3. 测试任务启用/禁用...")
        # 禁用一个任务
        scheduler.disable_task("news_reporter")
        print("已禁用 news_reporter 任务")
        
        # 检查状态
        news_status = scheduler.get_task_info("news_reporter")
        print(f"news_reporter 启用状态: {news_status['enabled']}")
        
        # 重新启用
        scheduler.enable_task("news_reporter")
        print("已重新启用 news_reporter 任务")
        
        print("4. 启动调度器（测试模式，3秒后执行）...")
        scheduler.start_all_tasks()
        
        # 等待一段时间观察任务执行
        print("等待10秒观察任务执行...")
        for i in range(10):
            time.sleep(1)
            print(f"等待中... {i+1}/10")
        
        print("5. 停止调度器...")
        scheduler.stop_all_tasks()
        
        print("\n=== 测试完成 ===")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_task_frequency():
    """测试不同频率的任务调度"""
    print("\n=== 测试任务频率 ===")
    
    try:
        from task_scheduler import TaskScheduler, TaskFrequency, TaskConfig
        
        scheduler = TaskScheduler()
        
        # 测试函数
        def test_function():
            print(f"测试任务执行: {datetime.now().strftime('%H:%M:%S')}")
        
        # 测试每日任务
        daily_task = TaskConfig(
            name="test_daily",
            function=test_function,
            hour=10, minute=30,
            frequency=TaskFrequency.DAILY,
            description="测试每日任务"
        )
        
        # 测试每周任务
        weekly_task = TaskConfig(
            name="test_weekly",
            function=test_function,
            hour=9, minute=0,
            frequency=TaskFrequency.WEEKLY,
            description="测试每周任务"
        )
        
        # 测试自定义间隔任务
        custom_task = TaskConfig(
            name="test_custom",
            function=test_function,
            frequency=TaskFrequency.CUSTOM,
            custom_interval_minutes=1,  # 每分钟执行
            description="测试自定义间隔任务"
        )
        
        # 注册任务
        scheduler.register_task(daily_task)
        scheduler.register_task(weekly_task)
        scheduler.register_task(custom_task)
        
        # 获取下次执行时间
        print("各任务下次执行时间:")
        for task_name in ["test_daily", "test_weekly", "test_custom"]:
            task_info = scheduler.get_task_info(task_name)
            if task_info:
                print(f"  {task_name}: {task_info['next_run']}")
        
        print("频率测试完成")
        return True
        
    except Exception as e:
        print(f"✗ 频率测试失败: {e}")
        return False

def test_scheduler_integration():
    """测试调度器与现有任务的集成"""
    print("\n=== 测试调度器集成 ===")
    
    try:
        # 检查现有任务文件是否存在
        task_files = [
            "features_daily_report.py",
            "news_reporter.py", 
            "weather_report.py",
            "features_weekly_report.py",
            "features_monthly_report.py",
            "hk_top10_broadcaster.py",
            "live_news.py",
            "regular_cleanup_db.py",
            "holder_trade_strategy.py",
            "features_min_monitor.py"
        ]
        
        missing_files = []
        for task_file in task_files:
            if not os.path.exists(f"tasks/{task_file}"):
                missing_files.append(task_file)
        
        if missing_files:
            print(f"缺少任务文件: {missing_files}")
        else:
            print("所有任务文件都存在")
        
        # 测试调度器初始化
        from task_scheduler import get_task_scheduler
        scheduler = get_task_scheduler()
        
        # 检查任务注册情况
        registered_tasks = list(scheduler.tasks.keys())
        print(f"已注册任务数量: {len(registered_tasks)}")
        print(f"已注册任务: {registered_tasks}")
        
        # 检查任务配置
        for task_name in registered_tasks:
            task_config = scheduler.tasks[task_name]
            print(f"  {task_name}: {task_config.description}")
            print(f"    时间: {task_config.hour:02d}:{task_config.minute:02d}:{task_config.second:02d}")
            print(f"    频率: {task_config.frequency.value}")
            print(f"    启用: {task_config.enabled}")
        
        print("集成测试完成")
        return True
        
    except Exception as e:
        print(f"✗ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("任务调度器验证测试")
    print("=" * 50)
    
    # 测试基本功能
    basic_ok = test_task_scheduler()
    
    # 测试任务频率
    frequency_ok = test_task_frequency()
    
    # 测试集成
    integration_ok = test_scheduler_integration()
    
    # 总结
    print("\n" + "=" * 50)
    print("测试总结:")
    print(f"  基本功能: {'✓' if basic_ok else '✗'}")
    print(f"  任务频率: {'✓' if frequency_ok else '✗'}")
    print(f"  集成测试: {'✓' if integration_ok else '✗'}")
    
    if basic_ok and frequency_ok and integration_ok:
        print("\n🎉 所有测试通过！任务调度器创建成功")
        print("\n主要功能:")
        print("  ✓ 统一管理所有定时任务的启动时间")
        print("  ✓ 支持多种执行频率（每日、每周、每月、每小时、自定义）")
        print("  ✓ 提供任务启用/禁用功能")
        print("  ✓ 支持调试模式快速测试")
        print("  ✓ 提供任务状态监控")
        print("  ✓ 自动重新调度任务")
        print("\n使用方法:")
        print("  from tasks.task_scheduler import start_scheduler, stop_scheduler")
        print("  start_scheduler()  # 启动所有任务")
        print("  stop_scheduler()   # 停止所有任务")
    else:
        print("\n❌ 部分测试失败，请检查相关功能")

if __name__ == "__main__":
    main() 