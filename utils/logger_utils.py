import logging
import os
import threading
from datetime import datetime


class Logger:
    """日志管理器，封装 logging 功能"""
    
    _loggers = {}
    _file_handlers = {}
    _lock = threading.Lock()
    _console_handler = None
    _initialized = False
    
    @classmethod
    def _ensure_initialized(cls):
        """确保Logger已初始化"""
        if not cls._initialized:
            with cls._lock:
                if not cls._initialized:
                    cls._setup_console_handler()
                    cls._initialized = True
    
    @classmethod
    def _setup_console_handler(cls):
        """设置控制台处理器"""
        cls._console_handler = logging.StreamHandler()
        cls._console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        cls._console_handler.setLevel(logging.DEBUG)
    
    @classmethod
    def _get_logger(cls, name, level):
        """获取指定名称和级别的logger"""
        cls._ensure_initialized()
        
        logger_key = f"{name}_{logging.getLevelName(level)}"
        
        if logger_key not in cls._loggers:
            with cls._lock:
                if logger_key not in cls._loggers:
                    logger = logging.getLogger(logger_key)
                    logger.setLevel(level)
                    logger.handlers.clear()
                    logger.propagate = False
                    logger.addHandler(cls._console_handler)
                    cls._loggers[logger_key] = logger
        
        return cls._loggers[logger_key]
    
    @classmethod
    def _get_file_handler(cls, name, level):
        """获取文件处理器"""
        handler_key = f"{name}_{logging.getLevelName(level)}"
        
        if handler_key not in cls._file_handlers:
            with cls._lock:
                if handler_key not in cls._file_handlers:
                    log_dir = 'data/logs'
                    if not os.path.exists(log_dir):
                        os.makedirs(log_dir)
                    
                    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
                    log_file = os.path.join(log_dir, f'{name}_{logging.getLevelName(level).lower()}_{current_time}.txt')
                    
                    file_handler = logging.FileHandler(log_file, encoding='utf-8')
                    file_handler.setFormatter(logging.Formatter(
                        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S'
                    ))
                    file_handler.setLevel(level)
                    cls._file_handlers[handler_key] = file_handler
        
        return cls._file_handlers[handler_key]
    
    @classmethod
    def _log(cls, level, message, save_to_file=False, logger_name='default'):
        """统一的日志记录方法"""
        logger = cls._get_logger(logger_name, level)
        
        if save_to_file:
            file_handler = cls._get_file_handler(logger_name, level)
            if file_handler not in logger.handlers:
                logger.addHandler(file_handler)
        
        logger.log(level, message)

    @classmethod
    def debug(cls, message, save_to_file=False, logger_name='default'):
        """输出调试信息"""
        cls._log(logging.DEBUG, message, save_to_file, logger_name)

    @classmethod
    def info(cls, message, save_to_file=False, logger_name='default'):
        """输出普通信息"""
        cls._log(logging.INFO, message, save_to_file, logger_name)

    @classmethod
    def warning(cls, message, save_to_file=False, logger_name='default'):
        """输出警告信息"""
        cls._log(logging.WARNING, message, save_to_file, logger_name)

    @classmethod
    def error(cls, message, save_to_file=False, logger_name='default'):
        """输出错误信息"""
        cls._log(logging.ERROR, message, save_to_file, logger_name)

    @classmethod
    def critical(cls, message, save_to_file=False, logger_name='default'):
        """输出严重错误信息"""
        cls._log(logging.CRITICAL, message, save_to_file, logger_name)


# 使用示例
if __name__ == "__main__":
    print("=== 测试Logger功能 ===")
    print("1. 测试控制台输出（save_to_file=False）")
    Logger.debug("这是一条调试信息 - 仅控制台", save_to_file=False)
    Logger.info("这是一条普通信息 - 仅控制台", save_to_file=False)
    Logger.warning("这是一条警告信息 - 仅控制台", save_to_file=False)
    
    print("\n2. 测试文件输出（save_to_file=True）")
    Logger.debug("这是一条调试信息 - 保存到文件", save_to_file=True)
    Logger.info("这是一条普通信息 - 保存到文件", save_to_file=True)
    Logger.warning("这是一条警告信息 - 保存到文件", save_to_file=True)
    Logger.error("这是一条错误信息 - 保存到文件", save_to_file=True)
    Logger.critical("这是一条严重错误信息 - 保存到文件", save_to_file=True)
    
    print("\n3. 测试不同logger_name")
    Logger.info("测试模块A的日志", save_to_file=True, logger_name="module_a")
    Logger.error("测试模块B的错误", save_to_file=True, logger_name="module_b")
