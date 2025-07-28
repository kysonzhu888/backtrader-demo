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


def start_process(script_name):
    python_executable = get_python_executable()
    script_path = os.path.join(os.getcwd(), python_executable)
    return subprocess.Popen([python_executable, script_path])


PROCESS_CONFIG = {
    # "main.py": "main.py",
    # "pow_wave_strategy.py": "pow_wave_strategy.py",
    "task_scheduler.py": "task_scheduler.py",
    # "if_amount_realtime.py":"if_amount_realtime.py",
    # "stock_market_service.py": os.path.join("mini_stock", "stock_market_service.py"),
    "features_min_loader.py": os.path.join("pinbar_strategy", "features_min_loader.py"),
    "if_amount_realtime.py": os.path.join("monitor", "if_amount_realtime.py"),
}


def monitor_processes():
    processes = {name: start_process(script) for name, script in PROCESS_CONFIG.items()}
    try:
        while True:
            for name, script in PROCESS_CONFIG.items():
                if processes[name].poll() is not None:
                    print(f"{script} 已终止，正在重启...")
                    processes[name] = start_process(script)
            time.sleep(5)
    except KeyboardInterrupt:
        print("守护进程已停止。")
        for proc in processes.values():
            proc.terminate()


if __name__ == "__main__":
    monitor_processes()
