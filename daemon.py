import subprocess
import time
import os
import platform
import logging
from datetime import datetime, timedelta
from collections import defaultdict, deque


def get_python_executable():
    """根据操作系统返回合适的 Python 可执行文件路径。"""
    # 优先使用环境变量
    venv_path = os.environ.get('VENV_PATH')
    if venv_path and os.path.exists(venv_path):
        if platform.system() == 'Windows':
            python_exe = os.path.join(venv_path, 'Scripts', 'python.exe')
        else:
            python_exe = os.path.join(venv_path, 'bin', 'python')
        if os.path.exists(python_exe):
            return python_exe
    
    # 自动检测虚拟环境路径
    possible_paths = []
    if platform.system() == 'Windows':
        possible_paths = [
            os.path.join(os.getcwd(), '.venv', 'Scripts', 'python.exe'),
            os.path.join('F:\\', '.venv', 'Scripts', 'python.exe'),  # 保留原有路径作为备选
            os.path.join(os.path.expanduser('~'), '.venv', 'Scripts', 'python.exe'),
        ]
    else:
        possible_paths = [
            os.path.join(os.getcwd(), '.venv', 'bin', 'python'),
            os.path.join(os.path.expanduser('~'), '.venv', 'bin', 'python'),
        ]
    
    # 检测可用路径
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # 如果都找不到，使用系统 Python
    return 'python'


def setup_logging():
    """设置日志记录"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('daemon.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


class ProcessRestartMonitor:
    """进程重启监控器"""
    def __init__(self, time_window=300, max_restarts=3):  # 5分钟内最多重启3次
        self.time_window = time_window  # 时间窗口（秒）
        self.max_restarts = max_restarts  # 最大重启次数
        self.restart_times = defaultdict(deque)  # 每个进程的重启时间记录
        self.blocked_processes = set()  # 被阻止重启的进程
        
    def can_restart(self, process_name):
        """检查进程是否可以重启"""
        if process_name in self.blocked_processes:
            return False
            
        now = datetime.now()
        restart_queue = self.restart_times[process_name]
        
        # 清理超出时间窗口的记录
        while restart_queue and (now - restart_queue[0]).seconds > self.time_window:
            restart_queue.popleft()
        
        return len(restart_queue) < self.max_restarts
    
    def record_restart(self, process_name, logger):
        """记录重启事件"""
        now = datetime.now()
        self.restart_times[process_name].append(now)
        
        restart_count = len(self.restart_times[process_name])
        logger.warning(f"进程 {process_name} 重启，当前时间窗口内重启次数: {restart_count}")
        
        if restart_count >= self.max_restarts:
            self.blocked_processes.add(process_name)
            logger.error(f"进程 {process_name} 在 {self.time_window} 秒内重启次数过多({restart_count}次)，已暂停重启！")
            return False
        
        return True


def start_process(script_name, args=None, logger=None):
    """启动进程"""
    python_executable = get_python_executable()
    script_path = os.path.join(os.getcwd(), script_name)
    cmd = [python_executable, script_path]
    if args:
        cmd.extend(args)
    
    try:
        process = subprocess.Popen(cmd)
        if logger:
            logger.info(f"成功启动进程: {script_name} (PID: {process.pid})")
        return process
    except Exception as e:
        if logger:
            logger.error(f"启动进程 {script_name} 失败: {e}")
        return None


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
    """监控并管理所有进程"""
    logger = setup_logging()
    monitor = ProcessRestartMonitor()
    processes = {}
    
    logger.info("守护进程启动，开始监控子进程...")
    
    # 初始化所有进程
    for name, config in PROCESS_CONFIG.items():
        script = config["script"]
        args = config.get("args")
        process = start_process(script, args, logger)
        if process:
            processes[name] = process
        else:
            logger.error(f"初始化进程 {name} 失败")
    
    try:
        while True:
            for name, config in PROCESS_CONFIG.items():
                if name not in processes:
                    continue
                    
                process = processes[name]
                if process and process.poll() is not None:
                    # 进程已终止
                    script = config["script"]
                    args = config.get("args")
                    
                    logger.warning(f"检测到进程 {name} 已终止 (退出码: {process.returncode})")
                    
                    # 检查是否可以重启
                    if monitor.can_restart(name):
                        if monitor.record_restart(name, logger):
                            new_process = start_process(script, args, logger)
                            if new_process:
                                processes[name] = new_process
                            else:
                                logger.error(f"重启进程 {name} 失败")
                    else:
                        logger.error(f"进程 {name} 重启次数过多，已停止重启")
                        del processes[name]
            
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭所有进程...")
        for name, proc in processes.items():
            if proc and proc.poll() is None:
                logger.info(f"正在终止进程 {name}...")
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning(f"进程 {name} 未在10秒内响应，强制杀死")
                    proc.kill()
        logger.info("守护进程已停止")


if __name__ == "__main__":
    monitor_processes()
