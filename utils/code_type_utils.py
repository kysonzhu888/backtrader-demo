class CodeTypeRecognizer:
    """股票/期货代码类型识别工具"""
    #https://dict.thinktrader.net/dictionary/future.html?id=7zqjlm
    FUTURES_EXCHANGES = {'IF', 'SF', 'DF', 'ZF', 'INE', 'GF'}
    STOCK_EXCHANGES = {'SZ', 'SH'}

    @staticmethod
    def is_futures_code(code: str) -> bool:
        """判断是否为期货（含股指期货）代码"""
        if '.' in code:
            code_part, exchange_part = code.split('.', 1)
            if exchange_part in CodeTypeRecognizer.FUTURES_EXCHANGES:
                return True
            elif exchange_part in CodeTypeRecognizer.STOCK_EXCHANGES:
                return False
            else:
                return CodeTypeRecognizer.is_futures_code_by_pattern(code_part)
        else:
            return CodeTypeRecognizer.is_futures_code_by_pattern(code)

    @staticmethod
    def is_futures_code_by_pattern(code: str) -> bool:
        """根据代码模式判断是否为期货代码（不含交易所后缀）"""
        if len(code) == 6 and code.isdigit():
            return False  # 股票代码
        if len(code) >= 4:
            has_letters = any(c.isalpha() for c in code[:3])
            has_digits = any(c.isdigit() for c in code)
            if has_letters and has_digits:
                return True  # 期货代码
        return False 