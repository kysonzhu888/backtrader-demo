# coding:utf-8
import time
from datetime import datetime
from xtquant import xtdata

code = '510300.SH'

day = "20250611"

#订阅最新行情
def callback_func(data):
    #{'600000.SH': [{'time': 1749623580000, 'open': 12.35, 'high': 12.36, 'low': 12.34, 'close': 12.35, 'volume': 3367, 'amount': 4156590.0, 'settlementPrice': 0.0, 'openInterest': 13, 'dr': 1.0, 'totaldr': 16.11206719610875, 'preClose': 6.95251579475095e-310, 'suspendFlag': 791273896}]}
    print('回调触发', data)

def format_time(timestamp):
    # 将时间戳转换为datetime对象
    dt = datetime.strptime(str(timestamp), '%Y%m%d%H%M%S')
    # 返回格式化的时间字符串
    return dt.strftime('%Y-%m-%d %H:%M:%S')

try:
    # 获取市场数据
    result = xtdata.get_market_data(['close','amount'], [code], period='1m', start_time=day,end_time=day,)
    
    if result is not None:
        # 获取成交额数据
        amount_df = result['amount']
        close_df = result['close']
        
        # 遍历每个时间点的成交额
        for timestamp in amount_df.columns:
            amount = amount_df.loc[code, timestamp]
            if amount > 100000000:  # 1亿
                close_price = close_df.loc[code, timestamp]
                # 将成交额转换为亿元单位
                amount_in_yi = amount / 100000000
                print(f'时间: {format_time(timestamp)}, 成交额: {amount_in_yi:.2f}亿, 收盘价: {close_price:.3f}')
    else:
        print('获取数据失败，请检查网络连接和参数设置')

except Exception as e:
    print(f'发生错误：{str(e)}')
    import traceback
    print("详细错误信息:", traceback.format_exc())

#死循环 阻塞主线程退出
# xtdata.run()


