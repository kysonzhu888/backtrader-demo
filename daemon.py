import subprocess
import time
import os
import platform


def get_python_executable():
    """根据操作系统返回合适的 Python 可执行文件路径。"""
    if platform.system() == 'Windows':
        # return os.path.join(os.getcwd(), '.venv', 'Scripts', 'python.exe')
        # return os.path.join(os.getcwd(), '.venv', 'Scripts', 'python.exe')
        return os.path.join('F:\\', '.venv', 'Scripts', 'python.exe')
    else:
        return os.path.join(os.getcwd(), '.venv', 'bin', 'python')


def start_process(script_name, args=None):
    python_executable = get_python_executable()

    script_path = os.path.join(os.getcwd(), script_name)
    cmd = [python_executable, script_path]
    if args:
        cmd.extend(args)
    return subprocess.Popen(cmd)


PROCESS_CONFIG = {
    # "main.py": {"script": "main.py"},
    "pow_wave_strategy.py": {"script": os.path.join("power_wave_strategy", "pow_wave_strategy.py")},
    "task_scheduler.py": {"script": "task_scheduler.py"},
    # # "stock_market_service.py": {"script": os.path.join("mini_stock", "stock_market_service.py")},
    "features_min_loader.py": {"script": os.path.join("pinbar_strategy", "features_min_loader.py")},
    "if_amount_realtime.py": {"script": os.path.join("monitor", "if_amount_realtime.py")},
    "live_news.py": {"script": os.path.join("tasks", "live_news.py")},
    "hk_top10_broadcaster.py": {"script": os.path.join("tasks", "hk_top10_broadcaster.py")},
    "weather_report.py": {"script": os.path.join("tasks", "weather_report.py")},
    "holder_trade_strategy.py": {"script": os.path.join("tasks", "holder_trade_strategy.py")},
    "stock_index_futures_analyzer.py": {"script": os.path.join("tasks", "stock_index_futures_analyzer.py"), "args": ["--daemon"]},
    "news_reporter.py": {"script": os.path.join("tasks", "news_reporter.py"), "args": ["--daemon"]},
    "features_daily_report.py": {"script": os.path.join("tasks", "features_daily_report.py"), "args": ["--daemon"]},
    "features_weekly_report.py": {"script": os.path.join("tasks", "features_weekly_report.py"), "args": ["--daemon"]},
    "features_monthly_report.py": {"script": os.path.join("tasks", "features_monthly_report.py"), "args": ["--daemon"]},
    "regular_cleanup_db.py": {"script": os.path.join("tasks", "regular_cleanup_db.py"), "args": ["--daemon"]},
}


def monitor_processes():
    processes = {}
    for name, config in PROCESS_CONFIG.items():
        script = config["script"]
        args = config.get("args")
        processes[name] = start_process(script, args)
    
    try:
        while True:
            for name, config in PROCESS_CONFIG.items():
                script = config["script"]
                args = config.get("args")
                if processes[name].poll() is not None:
                    print(f"{script} 已终止，正在重启...")
                    processes[name] = start_process(script, args)
            time.sleep(5)
    except KeyboardInterrupt:
        print("守护进程已停止。")
        for proc in processes.values():
            proc.terminate()


if __name__ == "__main__":
    monitor_processes()
