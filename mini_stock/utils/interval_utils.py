import re


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
