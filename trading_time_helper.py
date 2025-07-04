import logging
from datetime import datetime, time, timedelta
import chinese_calendar as calendar

from date_utils import DateUtils

class IntervalUtils:
    @staticmethod
    def convert_interval_to_minutes(interval_str):
        """
        将表示时间间隔的字符串转换为整数。
        例如：'14min' -> 14

        :param interval_str: 表示时间间隔的字符串
        :return: 转换后的整数
        """
        # 使用正则表达式提取数字部分
        match = re.match(r"(\d+)", interval_str)
        if match:
            return int(match.group(1))
        else:
            raise ValueError(f"Invalid interval format: {interval_str}")

class TradingTimeHelper:
    def __init__(self, product_type, country='CN'):
        self.product_type = product_type

    def trading_time(self):
        if self.product_type in ['AU', 'AG', 'SC']:
            trade_hours = [
                # 夜盘拆分为当日和次日两部分
                ('21:00', '02:30'),  # 次日凌晨夜盘
                # 日盘修正为实际时段
                ('09:00', '10:15'),
                ('10:30', '11:30'),
                ('13:30', '15:00')
            ]
            return trade_hours

        if self.product_type in ['CU', 'AL', 'ZN', 'NI', 'SS', 'SN', 'AL', 'AO','PB']:
            trade_hours = [
                # 夜盘拆分为当日和次日两部分
                ('21:00', '01:00'),  # 次日凌晨夜盘
                # 日盘修正为实际时段
                ('09:00', '10:15'),
                ('10:30', '11:30'),
                ('13:30', '15:00')
            ]
            return trade_hours

        if self.product_type in ['RB', 'I', 'HC', 'JM', 'J', 'M', 'Y', 'FG', 'SA', 'CF', 'RU', 'P', 'JM', 'C', 'V',
                                 'TA', 'SH', 'MA', 'OI', 'EG', 'SR', 'FU', 'RM', 'BU','EB','PG','SP','NR','PP','PX','PR','A','B']:
            trade_hours = [
                # 夜盘拆分为当日和次日两部分
                ('21:00', '23:00'),  # 当日夜盘
                # 日盘修正为实际时段
                ('09:00', '10:15'),
                ('10:30', '11:30'),
                ('13:30', '15:00')
            ]
            return trade_hours

        if self.product_type in ['IF', 'IH', 'IM', 'IC']:
            trade_hours = [
                # 日盘修正为实际时段
                ('09:30', '11:30'),
                ('13:00', '15:00')
            ]
            return trade_hours

        if self.product_type in ['TL', 'T', 'TF','TS']:
            trade_hours = [
                # 日盘修正为实际时段
                ('09:30', '11:30'),
                ('13:00', '15:15')
            ]
            return trade_hours

        if self.product_type in ['SF', 'SM', 'SI', 'LC', 'AP', 'LH', 'UR', 'JD', 'CJ', 'PS','EC']:
            trade_hours = [
                # 日盘修正为实际时段
                ('09:00', '10:15'),
                ('10:30', '11:30'),
                ('13:30', '15:00')
            ]
            return trade_hours
        return None

    def calculate_daily_trading_hours(self):
        trade_hours = self.trading_time()
        total_hours = 0

        for start, end in trade_hours:
            start_time = datetime.strptime(start, '%H:%M').time()
            end_time = datetime.strptime(end, '%H:%M').time()

            # 计算每个交易时段的时长
            if start_time < end_time:
                duration = (datetime.combine(datetime.min, end_time) - datetime.combine(datetime.min, start_time)).seconds / 3600
            else:
                # 处理跨午夜的交易时段
                duration = ((datetime.combine(datetime.min, end_time) + timedelta(days=1)) - datetime.combine(datetime.min, start_time)).seconds / 3600

            total_hours += duration

        return total_hours

    def is_trading_time(self, check_time=None):
        if check_time is None:
            check_time = DateUtils.now()
        current_time = check_time.time()
        today = check_time.date()
        weekday = check_time.weekday()

        # 检查是否为节假日
        if calendar.is_holiday(check_time):
            h_detail = calendar.get_holiday_detail(check_time)
            if h_detail[1] is not None:
                logging.debug(f"{check_time} 是 holiday:{h_detail}，滚粗")
                return False

        # 检查是否为周六夜盘
        if weekday == 5:  # 周六
            trade_hours = self.trading_time()
            for start, end in trade_hours:
                start_time = datetime.strptime(start, '%H:%M').time()
                end_time = datetime.strptime(end, '%H:%M').time()
                if start_time < end_time:
                    if start_time <= current_time <= end_time:
                        return True
                else:
                    if current_time >= start_time or current_time <= end_time:
                        return True
            return False

        # 检查是否为正常交易日
        if weekday >= 6:  # 周日
            return False

        # 获取当前品种的交易时段
        trade_hours = self.trading_time()

        # 检查当前时间是否在交易时段内
        for start, end in trade_hours:
            # 由于是一分钟线，因此开盘时候拉到的数据都是上一个交易时段的最后一条数据，收盘后也拉不到最后一条数据，无意义，因此都延后一分钟
            start_time = (datetime.strptime(start, '%H:%M') + timedelta(minutes=1)).time()
            end_time = (datetime.strptime(end, '%H:%M') + timedelta(minutes=1)).time()

            # 处理跨午夜的交易时段
            if start_time < end_time:
                if start_time <= current_time <= end_time:
                    return True
            else:
                if current_time >= start_time or current_time <= end_time:
                    return True

        return False

    def all_products_out_of_trading_time(self):
        # 定义所有商品类型
        all_product_types = ['AU', 'AG', 'CU', 'AL', 'ZN', 'NI', 'SS', 'SN', 'AL', 'AO',
                             'RB', 'I', 'HC', 'JM', 'J', 'M', 'Y', 'FG', 'SA', 'CF', 'RU',
                             'P', 'JM', 'C', 'V', 'TA', 'SH', 'MA', 'OI', 'EG', 'SR', 'FU',
                             'RM', 'BU', 'IF', 'IH', 'IM', 'IC', 'TL', 'T', 'TF', 'SF', 'SM',
                             'SI', 'LC', 'AP', 'LH', 'UR', 'PS','SP','EB','SC','NR','PP','JD','CJ','PX','PR','PB','A','B','EC']

        # 遍历所有商品类型，检查是否在交易时间内
        for product_type in all_product_types:
            self.product_type = product_type
            if self.is_trading_time():
                return False  # 如果有一个商品在交易时间内，返回False

        return True  # 如果所有商品都不在交易时间内，返回True

    def is_just_opened(self, delta_minutes='5min') -> bool:
        if delta_minutes == '1d':
            return False

        dm = IntervalUtils.convert_interval_to_minutes(delta_minutes)
        """
        判断当前是否在开盘后的指定时间窗口内（例如开盘前5分钟）
        :param delta_minutes: 时间窗口（分钟），默认5分钟
        :return: bool
        """
        now = DateUtils.now()
        current_time = now.time()
        today = now.date()

        # 1. 排除非交易日
        if calendar.is_holiday(today) or not self.is_trading_time():
            return False

        # 2. 遍历所有交易时段，检查是否在开盘窗口内
        for start_str, end_str in self.trading_time():
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()

            # 处理跨午夜时段（例如00:00-01:00）
            if start_time > end_time:
                # 拆分为当日和次日两个时段
                if current_time >= start_time:
                    # 当日时段的开盘时间
                    session_start = datetime.combine(today, start_time)
                elif current_time <= end_time:
                    # 次日时段的开盘时间
                    session_start = datetime.combine(today + timedelta(days=1), start_time)
                else:
                    continue  # 不在当前时段
            else:
                if not (start_time <= current_time <= end_time):
                    continue  # 不在当前时段
                session_start = datetime.combine(today, start_time)

            # 计算时间差
            time_diff = now - session_start
            if 0 <= time_diff.total_seconds() <= dm * 60:
                return True
        return False

    def is_trading_day(self, check_date=None):
        if check_date is None:
            check_date = DateUtils.now().date()

        # 检查是否为节假日
        if calendar.is_holiday(check_date):
            h_detail = calendar.get_holiday_detail(check_date)
            if h_detail[1] is not None:
                logging.debug(f"{check_date} 是 holiday:{h_detail}，滚粗")
                return False

        # 检查是否为周末
        weekday = check_date.weekday()
        if weekday > 5:  # 周六和周日
            return False

        return True

    def get_current_session_end_time(self, check_time):
        """
        获取当前K线属于的交易时段的收盘时间（datetime对象）。
        """
        trade_hours = self.trading_time()
        for start_str, end_str in trade_hours[::-1]:  # 逆序，优先找日盘
            start_dt = check_time.replace(hour=int(start_str.split(":")[0]), minute=int(start_str.split(":")[1]),
                                        second=0, microsecond=0)
            end_dt = check_time.replace(hour=int(end_str.split(":")[0]), minute=int(end_str.split(":")[1]), second=0,
                                      microsecond=0)

            # 处理跨午夜的情况
            if end_dt <= start_dt:
                # 如果当前时间已经过了当天的收盘时间，返回第二天的收盘时间
                if check_time > end_dt:
                    end_dt = end_dt + timedelta(days=1)
                # 如果当前时间在当天的交易时段内，返回当天的收盘时间
                else:
                    end_dt = end_dt.replace(day=check_time.day)

                return end_dt
            if start_dt <= check_time <= end_dt:
                return end_dt
        return None

    def get_current_session_start_time(self, check_time):
        """
        获取当前K线所属交易时段的开盘时间（datetime对象）。
        """
        trade_hours = self.trading_time()
        for start_str, end_str in trade_hours:
            start_dt = check_time.replace(hour=int(start_str.split(":")[0]), minute=int(start_str.split(":")[1]),
                                        second=0, microsecond=0)
            end_dt = check_time.replace(hour=int(end_str.split(":")[0]), minute=int(end_str.split(":")[1]), second=0,
                                      microsecond=0)

            # 处理跨午夜的情况
            if end_dt <= start_dt:
                # 如果当前时间已经过了当天的收盘时间，返回当天的开盘时间
                if check_time > end_dt:
                    return start_dt
                # 如果当前时间在当天的交易时段内，返回当天的开盘时间
                else:
                    return start_dt
            if start_dt <= check_time <= end_dt:
                return start_dt
        return None