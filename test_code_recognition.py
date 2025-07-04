#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试代码识别功能
"""

import logging
from datetime import datetime

def test_code_recognition():
    """测试代码识别功能"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info("开始测试代码识别功能...")

    def _is_futures_code(code: str) -> bool:
        """判断是否为股指期货代码"""
        # 期货交易所后缀映射
        FUTURES_EXCHANGES = {
            'IF': 'CFFEX',   # 中金所
            'SF': 'SHFE',    # 上期所
            'DF': 'DCE',     # 大商所
            'ZF': 'CZCE',    # 郑商所
            'INE': 'INE',    # 能源中心
            'GF': 'GFEX',    # 广期所
        }
        
        # 股票交易所后缀
        STOCK_EXCHANGES = {
            'SZ',  # 深圳
            'SH',  # 上海
        }
        
        # 如果代码包含点号，说明有交易所后缀
        if '.' in code:
            code_part, exchange_part = code.split('.', 1)
            
            # 检查是否为期货交易所后缀
            if exchange_part in FUTURES_EXCHANGES:
                return True
            # 检查是否为股票交易所后缀
            elif exchange_part in STOCK_EXCHANGES:
                return False
            else:
                # 未知交易所后缀，根据代码部分判断
                return _is_futures_code_by_pattern(code_part)
        else:
            # 没有交易所后缀，根据代码模式判断
            return _is_futures_code_by_pattern(code)
    
    def _is_futures_code_by_pattern(code: str) -> bool:
        """根据代码模式判断是否为期货代码（不含交易所后缀）"""
        # 股指期货代码通常是 2-3 位字母 + 4 位数字，如 IF2403、IH2403、IC2403 等
        # 商品期货代码通常是 1-2 位字母 + 数字，如 AU2403、AG2403、RB2403 等
        # 股票代码通常是 6 位数字，如 000001、600000 等
        
        if len(code) == 6 and code.isdigit():
            return False  # 股票代码
        
        # 期货代码模式：字母开头，包含数字
        if len(code) >= 4:
            # 检查前2-3位是否包含字母
            has_letters = any(c.isalpha() for c in code[:3])
            # 检查是否包含数字
            has_digits = any(c.isdigit() for c in code)
            
            if has_letters and has_digits:
                return True  # 期货代码
        
        # 默认按股票处理
        return False

    # 测试代码识别
    test_codes = [
        # 股票代码（带交易所后缀）
        "000001.SZ",  # 深圳股票
        "600000.SH",  # 上海股票
        "002072.SZ",  # 深圳股票
        "300001.SZ",  # 深圳创业板
        "688001.SH",  # 上海科创板
        
        # 股票代码（不带交易所后缀）
        "000001",     # 深圳股票
        "600000",     # 上海股票
        "002072",     # 深圳股票
        
        # 股指期货代码（带交易所后缀）
        "IF2403.IF",  # 中金所股指期货
        "IH2403.IF",  # 中金所股指期货
        "IC2403.IF",  # 中金所股指期货
        "IM2512.IF",  # 中金所股指期货
        
        # 商品期货代码（带交易所后缀）
        "AU2403.SF",  # 上期所黄金期货
        "AG2403.SF",  # 上期所白银期货
        "RB2403.SF",  # 上期所螺纹钢期货
        "I2403.DF",   # 大商所铁矿石期货
        "M2403.DF",   # 大商所豆粕期货
        "SR2403.ZF",  # 郑商所白糖期货
        "TA2403.ZF",  # 郑商所PTA期货
        "SC2403.INE", # 能源中心原油期货
        "NR2403.INE", # 能源中心橡胶期货
        "SI2403.GF",  # 广期所工业硅期货
        
        # 期货代码（不带交易所后缀）
        "IF2403",     # 股指期货
        "IH2403",     # 股指期货
        "IC2403",     # 股指期货
        "IM2512",     # 股指期货
        "AU2403",     # 商品期货
        "AG2403",     # 商品期货
        "RB2403",     # 商品期货
        
        # 边界情况
        "IF",         # 简化期货代码
        "IH",         # 简化期货代码
        "IC",         # 简化期货代码
        "AU",         # 简化期货代码
        "AG",         # 简化期货代码
    ]

    logger.info("代码识别测试结果:")
    for code in test_codes:
        is_futures = _is_futures_code(code)
        logger.info(f"  {code}: {'股指期货' if is_futures else '股票'}")

    # 测试 key 生成
    def _get_today_key(code: str) -> str:
        """生成当天的数据key，区分股票和股指期货"""
        today = datetime.now().strftime('%Y%m%d')
        if _is_futures_code(code):
            return f"futures_data:{code}:{today}"
        else:
            return f"stock_data:{code}:{today}"

    def _get_latest_key(code: str) -> str:
        """生成最新数据的key，区分股票和股指期货"""
        if _is_futures_code(code):
            return f"futures_latest:{code}"
        else:
            return f"stock_latest:{code}"

    logger.info("\nKey 生成测试结果:")
    sample_codes = ["000001.SZ", "600000.SH", "002072.SZ", "IF2403.IF", "IM2512.IF", "AU2403.SF"]
    for code in sample_codes:
        today_key = _get_today_key(code)
        latest_key = _get_latest_key(code)
        logger.info(f"  {code}:")
        logger.info(f"    today_key: {today_key}")
        logger.info(f"    latest_key: {latest_key}")

    logger.info("测试完成")

if __name__ == "__main__":
    test_code_recognition() 