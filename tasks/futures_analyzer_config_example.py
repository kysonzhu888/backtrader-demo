#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股指期货分析器配置示例
展示如何自定义配置参数
"""

from stock_index_futures_analyzer import FuturesAnalyzerConfig, FuturesNetShortAnalyzer, run_stock_index_futures_analysis

def example_custom_config():
    """示例：自定义配置"""
    
    # 创建自定义配置
    config = FuturesAnalyzerConfig()
    
    # 修改运行时间为15:30
    config.scheduled_hour = 15
    config.scheduled_minute = 30
    
    # 修改阈值
    config.low_threshold = 70000   # 7万以下做多
    config.high_threshold = 120000  # 12万以上做空
    
    # 修改网络超时
    config.connection_timeout = 15  # 连接超时15秒
    config.read_timeout = 30       # 读取超时30秒
    
    # 修改重试次数
    config.max_download_retries = 5  # 单文件重试5次
    config.max_analysis_retries = 2  # 整体重试2次
    
    # 禁用启动通知（只保留错误通知）
    config.enable_startup_notification = False
    
    # 每30分钟检查一次
    config.check_interval_minutes = 30
    
    print("=== 自定义配置示例 ===")
    print(f"运行时间: {config.get_scheduled_time_str()}")
    print(f"做多阈值: {config.low_threshold/10000:.1f}万")
    print(f"做空阈值: {config.high_threshold/10000:.1f}万")
    print(f"连接超时: {config.connection_timeout}秒")
    print(f"检查间隔: {config.check_interval_minutes}分钟")
    
    return config

def example_test_run():
    """示例：立即执行一次分析（使用自定义配置）"""
    config = example_custom_config()
    
    print("\n=== 执行分析 ===")
    analyzer = FuturesNetShortAnalyzer(config)
    success = analyzer.run_analysis()
    
    if success:
        print("✅ 分析成功完成")
    else:
        print("❌ 分析失败")
        
    return success

def example_daemon_mode():
    """示例：守护进程模式（使用自定义配置）"""
    config = example_custom_config()
    
    print("\n=== 启动守护进程 ===")
    print("按 Ctrl+C 停止...")
    
    # 启动守护进程
    run_stock_index_futures_analysis(config, first_run=True)
    
    # 保持运行
    try:
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n守护进程已停止")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            # 测试模式：立即执行一次
            example_test_run()
        elif sys.argv[1] == "--daemon":
            # 守护进程模式
            example_daemon_mode()
        else:
            print("用法:")
            print("  python futures_analyzer_config_example.py --test     # 立即执行一次")
            print("  python futures_analyzer_config_example.py --daemon   # 守护进程模式")
    else:
        print("配置示例:")
        example_custom_config()
        print("\n运行选项:")
        print("  --test: 立即执行一次分析")
        print("  --daemon: 守护进程模式")