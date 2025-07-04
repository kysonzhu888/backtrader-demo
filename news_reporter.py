import environment
import os
from threading import Timer

import requests
from database_helper import DatabaseHelper
from date_utils import DateUtils
from environment import group_chat_name_vip
import logging

from datetime import datetime, timedelta

from wechat_helper import WeChatHelper


def get_news():
    # 使用yfinance获取美股三大指数的收盘价
    # indexes = {'标普500': '^GSPC', '道琼斯': '^DJI', '纳斯达克': '^IXIC'}
    # stocks = []
    # today = datetime.now()
    #
    # for name, symbol in indexes.items():
    #     ticker = yf.Ticker(symbol)
    #
    #     if today.weekday() == 0:  # 如果今天是周一
    #         # 获取上周一到上周五的数据
    #         last_monday = today - timedelta(days=7)
    #         last_friday = today - timedelta(days=3)
    #         last_week_data = ticker.history(start=last_monday, end=last_friday + timedelta(days=1))
    #         close_price_last_monday = last_week_data['Close'].iloc[0]
    #         close_price_last_friday = last_week_data['Close'].iloc[-1]
    #         last_week_performance = (
    #                     (close_price_last_friday - close_price_last_monday) / close_price_last_monday * 100)
    #         stocks.append(
    #             f"{name} 上周一收：{close_price_last_monday:.2f} ,上周五收：{close_price_last_friday:.2f}, 上周涨幅：{last_week_performance:.2f}%")
    #     else:
    #         # 获取最近两天的数据
    #         data = ticker.history(period='2d')
    #         close_price_today = data['Close'].iloc[-1]
    #         close_price_yesterday = data['Close'].iloc[-2]
    #         stocks.append(
    #             f"{name} 昨收：{close_price_yesterday:.2f} ,今收：{close_price_today:.2f}, 涨幅：{((close_price_today - close_price_yesterday) / close_price_yesterday * 100):.2f}%")

    # 使用Blockchain API获取比特币价格
    url = 'https://api.blockchain.com/v3/exchange/tickers/BTC-USD'
    response = requests.get(url)
    btc_data = response.json()
    btc_price = btc_data['last_trade_price']
    coins = [f"BTC ${btc_price}"]

    # 财经信息（示例数据）
    # events = ["美联储维持利率不变", "中东局势影响油价波动", "A股纳入MSCI比例上调"]
    db_helper = DatabaseHelper()
    df_im = db_helper.read_feature_data("IM")
    df_if = db_helper.read_feature_data("IF")

    # 获取最后一条数据
    last_im_close = df_im['close'].iloc[-1] if not df_im.empty else None
    last_if_close = df_if['close'].iloc[-1] if not df_if.empty else None

    # 计算收盘价的比值
    if last_im_close is not None and last_if_close is not None:
        close_ratio = last_im_close / last_if_close
        percentile = (close_ratio - 1.2) / (1.8 - 1.2) * 100  # 假设1.2到1.8是0%到100%
        if close_ratio > 1.6:
            rt_msg = f" IM高估，建议置换 IF，目前处于{percentile:.2f}百分位。"
        elif 1.6 > close_ratio > 1.5:
            rt_msg = f" IM有些高估了，看情况可以置换 IF，目前处于{percentile:.2f}百分位。"
        elif 1.5 > close_ratio > 1.4:
            rt_msg = f" IM不高估，可以持有，目前处于{percentile:.2f}百分位。"
        elif 1.4 > close_ratio > 1.3:
            rt_msg = f" IM相对低估，开仓！目前处于{percentile:.2f}百分位。"
        else:
            rt_msg = f" IM低估太多了，加仓！目前处于{percentile:.2f}百分位。"

        ratio_im_if = f"IM昨日收盘价：{last_im_close}, IF昨日收盘价：{last_if_close}，比值: {close_ratio:.2f}。" + rt_msg
    else:
        ratio_im_if = ""
        logging.warning("无法计算IM/IF收盘价比值，数据可能为空")

    return coins + [ratio_im_if]


def news_report():
    msg = "早安啊，新的一天又开始了，让我们看看昨天有什么值得关注的吧！\n" + "\n".join(get_news())
    wechat_helper = WeChatHelper()
    wechat_helper.send_message(msg, group_chat_name_vip)

def schedule_task():
    # 设置下次运行时间
    now = DateUtils.now()
    next_run = now.replace(hour=8, minute=5, second=0, microsecond=0)
    if now >= next_run:
        next_run += timedelta(days=1)
    delay = (next_run - now).total_seconds()

    # 如果是 debug 模式，则立刻执行
    if os.getenv('DEBUG_MODE') == '1':
        delay = 3

    logging.info(f"早间新闻播报即将在{delay}秒后执行，请等待...")
    Timer(delay, news_report).start()


if __name__ == '__main__':
    schedule_task()