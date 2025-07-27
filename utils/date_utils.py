import environment
import pytz
from datetime import datetime
import os

from environment import debug_current_os_time


class DateUtils:
    @staticmethod
    def now(local_tz=pytz.timezone('Asia/Shanghai')):
        """
        获取当前时间。
        如果在调试模式下，返回调试时间。

        :return: 当前时间或调试时间
        """
        # 获取系统当前时间
        now = datetime.now()

        # 在调试模式下，只加载到特定时间的数据
        if os.getenv('DEBUG_MODE') == '1':
            now = datetime.strptime(f'{debug_current_os_time}', '%Y-%m-%d %H:%M:%S')

        return now

    @staticmethod
    def today(local_tz=pytz.timezone('Asia/Shanghai')):
        """
        获取今天的日期（时间部分为00:00:00）。
        如果在调试模式下，返回调试日期的00:00:00。

        :return: 今天的日期或调试日期
        """
        now = DateUtils.now(local_tz)
        return datetime(now.year, now.month, now.day)


