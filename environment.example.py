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

# 请将此文件复制为 environment.py 并填入实际的API密钥
tushare_token = 'YOUR_TUSHARE_API_TOKEN_HERE'

# 微信群名称配置
group_chat_name_vip = "投资策略VIP群"
group_chat_name_dlb = "动力波策略群"