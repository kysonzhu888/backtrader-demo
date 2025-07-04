import os

import environment
from date_utils import DateUtils
from environment import group_chat_name_vip
import threading
import time
import logging
from datetime import datetime, timedelta
import random

from text_utils import TextUtils
from wechat_helper import WeChatHelper

from tushare_helper import TushareHelper

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NewsBroadcaster")

# 定义所有可能的新闻源
available_sources = ['sina', 'wallstreetcn', '10jqka', 'eastmoney', 'yuncaijing', 'fenghuang',
                     'jinrongjie']
# 定义目标微信群列表
target_groups = ["算法学习二群","算法学习三群", "kyson的亿万俱乐部二群", "kyson的亿万俱乐部三群","投资策略VIP群"]

def broadcast_news_task():
    """
    实际执行新闻获取和播报的任务。
    """
    logger.info("正在获取新闻...")
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)

        # 随机选择 5 个新闻源
        selected_sources = random.sample(available_sources, 5)
        logger.info(f"本次播报选择的新闻源: {selected_sources}")

        # 为每个选定的新闻源获取新闻并发送到对应的群组
        for src, group in zip(selected_sources, target_groups):
            logger.info(f"正在从 {src} 获取新闻并发送到 {group}...")
            news_df = TushareHelper.live_news(start_date=start_time, end_date=end_time, src=src)

            if news_df is not None and not news_df.empty:
                news_titles = []
                for index, row in news_df.head(10).iterrows():
                    title = row.get('title')
                    if title is None or (isinstance(title, str) and not title.strip()):
                        news_titles.append('')
                    else:
                        news_titles.append(str(title).strip())

                unique_news_titles = []
                seen_titles = set()
                for title in news_titles:
                    if title and title not in seen_titles:
                        unique_news_titles.append(title)
                        seen_titles.add(title)

                if unique_news_titles:
                    # 将去重后的标题用换行符连接起来，并加上序号
                    numbered_titles = [f"{i + 1}. {title}" for i, title in enumerate(unique_news_titles)]
                    broadcast_message = f"不定期新闻播报来了: \n" + "\n".join(numbered_titles)

                    # 使用 WeChatHelper 播报
                    wechat_helper = WeChatHelper()
                    wechat_helper.send_message(broadcast_message, group)
                    # 在发送给不同群之间稍作延迟
                    time.sleep(5)
                else:
                    logger.info(f"从 {src} 未获取到新闻标题。")
            else:
                logger.info(f"从 {src} 未获取到新闻或新闻列表为空。")

    except Exception as e:
        logger.error(f"获取或播报新闻时发生错误: {e}")

    # 任务执行完毕，调度下一次任务
    schedule_next_broadcast()


def schedule_next_broadcast():
    """
    计算下一次播报的时间并启动 Timer。
    """
    now = DateUtils.now()
    # 计算距离下一个整点小时的秒数
    next_hour = now.replace(minute=8, second=55)
    delay_seconds = (next_hour - now).total_seconds()

    # 如果计算出的延迟小于等于 0，说明当前时间已经在整点之后了，直接调度到下一个整点小时
    if delay_seconds <= 0:
        next_hour = now.replace(minute=8, second=55) + timedelta(hours=1)
        delay_seconds = (next_hour - now).total_seconds()

    # 如果是 debug 模式，则立刻执行
    if os.getenv('DEBUG_MODE') == '1':
        delay_seconds = 3
    logger.info(f"下一次新闻播报将在 {delay_seconds:.2f} 秒后执行 ({next_hour})...")

    # 使用 Timer 调度任务
    threading.Timer(delay_seconds, broadcast_news_task).start()


# 如何使用这个脚本（示例，直接运行即可启动调度）
if __name__ == "__main__":
    logger.info("新闻播报调度脚本启动...")
    # 启动第一次调度
    schedule_next_broadcast()
