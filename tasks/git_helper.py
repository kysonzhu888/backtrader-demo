import os
import platform
import time
from datetime import datetime
from threading import Timer

 # 网页3

def push_to_remote():
    # 优先检测环境变量中的git命令
    system = platform.system()
    if system == "Windows":
        # 定义Git短路径常量
        git_short_path = r"C:\Progra~1\Git\bin\git"
    elif system == "Darwin":
        git_short_path = r"git"
    else:
        git_short_path = r"git"


    """
    将futures_data.db推送到远程数据库，提交信息为"更新数据库"。
    """
    os.system(f'{git_short_path} add futures_data.db')
    os.system(f'{git_short_path} commit -m "更新数据库 at time {datetime.now()}" ')
    os.system(f'{git_short_path} push')


def schedule_git_push(interval):
    """
    每隔指定的时间间隔执行一次push_to_remote。
    :param interval: 时间间隔，单位为秒
    """
    Timer(interval, schedule_git_push, [interval]).start()
    push_to_remote()


if __name__ == "__main__":
    # 每隔2小时（60*60*2秒）执行一次
    schedule_git_push(60*60*2)