import logging
import os
from datetime import datetime


class Logger:
    """日志管理器，封装 logging 功能"""

    _file_handler = None

    @classmethod
    def _get_file_handler(cls, name):
        """获取文件处理器"""
        if cls._file_handler is None:
            # 确保日志目录存在
            log_dir = 'data/logs'
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            # 生成日志文件名（使用当前时间）
            current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = os.path.join(log_dir, f'{name}_{current_time}.txt')

            # 创建文件处理器
            cls._file_handler = logging.FileHandler(log_file, encoding='utf-8')
            cls._file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))

        return cls._file_handler

    @classmethod
    def debug(cls, message, save_to_file=False):
        """输出调试信息"""
        logger = logging.getLogger('default')
        file_handler = None
        if save_to_file:
            file_handler = cls._get_file_handler('default')
            logger.addHandler(file_handler)
        logger.debug(message)
        if save_to_file and file_handler:
            logger.removeHandler(file_handler)

    @classmethod
    def info(cls, message, save_to_file=False):
        """输出普通信息"""
        logger = logging.getLogger('default')
        file_handler = None
        if save_to_file:
            file_handler = cls._get_file_handler('default')
            logger.addHandler(file_handler)
        logger.info(message)
        if save_to_file and file_handler:
            logger.removeHandler(file_handler)

    @classmethod
    def warning(cls, message, save_to_file=False):
        """输出警告信息"""
        logger = logging.getLogger('default')
        file_handler = None
        if save_to_file:
            file_handler = cls._get_file_handler('default')
            logger.addHandler(file_handler)
        logger.warning(message)
        if save_to_file and file_handler:
            logger.removeHandler(file_handler)

    @classmethod
    def error(cls, message, save_to_file=False):
        """输出错误信息"""
        logger = logging.getLogger('default')
        file_handler = None
        if save_to_file:
            file_handler = cls._get_file_handler('default')
            logger.addHandler(file_handler)
        logger.error(message)
        if save_to_file and file_handler:
            logger.removeHandler(file_handler)

    @classmethod
    def critical(cls, message, save_to_file=False):
        """输出严重错误信息"""
        logger = logging.getLogger('default')
        file_handler = None
        if save_to_file:
            file_handler = cls._get_file_handler('default')
            logger.addHandler(file_handler)
        logger.critical(message)
        if save_to_file and file_handler:
            logger.removeHandler(file_handler)


# 使用示例
if __name__ == "__main__":
    # 配置基本的日志格式
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 测试不同级别的日志
    Logger.debug("这是一条调试信息", save_to_file=True)
    Logger.info("这是一条普通信息", save_to_file=False)
    Logger.warning("这是一条警告信息", save_to_file=True)
    Logger.error("这是一条错误信息", save_to_file=True)
    Logger.critical("这是一条严重错误信息", save_to_file=True)
