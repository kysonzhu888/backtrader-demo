import os
import logging
from typing import List, Optional

class MiniStockReportReader:
    @staticmethod
    def read_stock_codes(report_dir: str, date_str: str) -> Optional[List[str]]:
        """
        读取指定日期的小市值持仓股票代码列表
        支持格式如：1. 卓锦股份(688701.SH) 市值: 10.02亿 现价: 7.46 买一手需: 746.00元

        Args:
            report_dir: 报告文件夹
            date_str: 日期字符串，格式为YYYYMMDD

        Returns:
            Optional[List[str]]: 股票代码列表
        """
        report_file = os.path.join(report_dir, f"ministock_report_{date_str}.txt")
        if not os.path.exists(report_file):
            logging.error(f"报告文件不存在: {report_file}")
            return None

        codes = []
        with open(report_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        # 找到持仓明细部分
        start_index = -1
        for i, line in enumerate(lines):
            if "持仓明细:" in line:
                start_index = i + 1
                break
        if start_index == -1:
            # 兼容无"持仓明细:"的情况，直接找形如"1."开头的行
            start_index = 0
        for line in lines[start_index:]:
            line = line.strip()
            if not line or not line[0].isdigit():
                continue
            # 解析股票代码
            left = line.find('(')
            right = line.find(')', left)
            if left != -1 and right != -1:
                code = line[left+1:right]
                codes.append(code)
        return codes 