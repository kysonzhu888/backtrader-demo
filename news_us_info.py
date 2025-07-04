import time
from datetime import timedelta

import environment
import tushare as ts

from date_utils import DateUtils


class NewsUSInfo:
    def __init__(self, t_api_key):
        self.pro = ts.pro_api(t_api_key)

    def get_previous_day_index_data(self, s_codes):
        # 获取前一日的日期
        previous_day = (DateUtils.now() - timedelta(days=1)).strftime('%Y%m%d')
        s_data_list = {}
        for code_item in s_codes:
            # 使用 us_daily 接口获取前一日的指数数据
            us_data = self.pro.us_daily(ts_code=code_item, trade_date=previous_day)
            s_data_list[code] = us_data
            time.sleep(60)
        return s_data_list


# 示例调用
if __name__ == "__main__":
    api_key = environment.tushare_token  # 替换为你的API密钥
    fetcher = NewsUSInfo(api_key)

    # 三大指数代码（假设代码为：道琼斯DJI，纳斯达克IXIC，标普500SPX）
    # index_codes = ['DJI', 'IXIC', 'SPX']
    index_codes = ['DJI']
    index_data = fetcher.get_previous_day_index_data(index_codes)

    for code, data in index_data.items():
        print(f"{code}指数前一日的行情数据：")
        print(data)
