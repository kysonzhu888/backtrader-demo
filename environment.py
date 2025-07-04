import logging
import os

# 配置全局日志级别和格式
logging.basicConfig(
    level=logging.INFO,  # 设置全局日志级别
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# os.environ['DEBUG_MODE'] = '1'

# debug 模式下，伪装当前的时间，需要注意 debug_latest_candle_time 是最近的一根 k 线的时间
# debug_current_time 是当前系统时间，所以后者要比前者时间靠后
debug_latest_candle_time = '2025-05-21 09:29:01'
debug_current_os_time = '2025-05-21 09:29:07'

tushare_token = '5f2376e3343270c38ce57eb1353ed7ed6c1d3a8f6737f8dd247c2023'

group_chat_name_vip = "投资策略VIP群"
group_chat_name_dlb = "动力波策略群"
group_chat_name_monitor = "老公老婆"

# 特殊日期配置
special_days = {
    '2025-04-30': {'no_night_session': True}  # 该日期没有夜盘
}

STOCK_MARKET_SERVICE_HOST = "192.168.50.121"
STOCK_MARKET_SERVICE_PORT = 5000
# Redis配置
REDIS_HOST = '192.168.50.52'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = None  # 如果有密码，请设置

def atr_muliter_of(interval_num):
    if interval_num <= 10:
        atr_multiplier = 1.8
    elif 10 < interval_num <= 15:
        atr_multiplier = 1.2
    elif 15 < interval_num <= 60:
        atr_multiplier = 1.1
    else:
        atr_multiplier = 1.0
    return atr_multiplier
