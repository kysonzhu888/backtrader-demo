from datetime import datetime, timedelta
import logging


class TimeUtils:
    @staticmethod
    def ts_to_datestr(ts):
        try:
            # 如果是字符串，尝试解析为日期时间
            if isinstance(ts, str):
                if len(ts) == 14:  # 格式: %Y%m%d%H%M%S
                    dt = datetime.strptime(ts, '%Y%m%d%H%M%S')
                    return dt.strftime('%Y%m%d')
                elif len(ts) == 8:  # 格式: %Y%m%d
                    return ts  # 已经是所需格式
                else:
                    return None

            # 原始数值型时间戳处理
            if ts > 1e12:
                ts = ts // 1000
            if ts < 0 or ts > 4102444800:
                return None
            return datetime.fromtimestamp(ts).strftime('%Y%m%d')

        except Exception as e:
            logging.error(f"时间戳转换失败: {ts}, 错误: {e}")
            return None