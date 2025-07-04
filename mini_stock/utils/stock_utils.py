import re

class StockUtils:
    """股票工具类，用于处理股票相关的验证和转换"""
    
    # 股票代码前缀映射
    MARKET_PREFIXES = {
        '0': 'SZ',  # 深交所主板
        '3': 'SZ',  # 创业板
        '6': 'SH',  # 上交所主板
        '8': 'BJ',  # 北交所
        '4': 'BJ',  # 老三板
    }
    
    # 特殊标记
    SPECIAL_MARKS = {
        'ST': 'ST',
        'ST*': 'ST*',
        '退': '退',
        '退市': '退市',
        '退市整理': '退市整理'
    }
    
    @staticmethod
    def is_valid_stock_code(code):
        """
        验证股票代码是否合法
        规则：
        1. 基本格式：6位数字
        2. 第一位必须是0、3、4、6、8
        3. 可能包含市场后缀（.SH/.SZ/.BJ）
        4. 可能包含特殊标记（ST/退市等）
        """
        if not isinstance(code, str):
            return False
            
        # 移除可能的空格
        code = code.strip()
        
        # 分离基本代码和特殊标记
        base_code = code
        special_mark = None
        
        # 检查是否包含市场后缀
        if '.' in code:
            base_code, market = code.split('.')
            if market not in ['SH', 'SZ', 'BJ']:
                return False
        
        # 检查是否包含特殊标记
        for mark in StockUtils.SPECIAL_MARKS.keys():
            if mark in base_code:
                base_code = base_code.replace(mark, '')
                special_mark = mark
                break
        
        # 检查基本代码格式
        if not re.match(r'^[03468]\d{5}$', base_code):
            return False
            
        return True
    
    @staticmethod
    def normalize_stock_code(code):
        """
        标准化股票代码
        1. 移除空格
        2. 转换为字符串
        3. 补齐前导零
        4. 添加市场后缀
        5. 保留特殊标记
        """
        if not code:
            return None
            
        # 转换为字符串并移除空格
        code = str(code).strip()
        
        # 分离基本代码和特殊标记
        base_code = code
        special_mark = None
        market_suffix = None
        
        # 检查是否包含市场后缀
        if '.' in code:
            base_code, market = code.split('.')
            market_suffix = market
        
        # 检查是否包含特殊标记
        for mark in StockUtils.SPECIAL_MARKS.keys():
            if mark in base_code:
                base_code = base_code.replace(mark, '')
                special_mark = mark
                break
        
        # 如果是数字，补齐前导零
        if base_code.isdigit():
            base_code = base_code.zfill(6)
        
        # 验证基本代码格式
        if not re.match(r'^[03468]\d{5}$', base_code):
            return None
            
        # 构建标准化的股票代码
        normalized_code = base_code
        
        # 添加特殊标记
        if special_mark:
            normalized_code = f"{special_mark}{normalized_code}"
            
        # 添加市场后缀
        if not market_suffix:
            market_suffix = StockUtils.MARKET_PREFIXES.get(base_code[0])
        if market_suffix:
            normalized_code = f"{normalized_code}.{market_suffix}"
            
        return normalized_code
    
    @staticmethod
    def filter_valid_stock_codes(codes):
        """
        过滤并返回有效的股票代码列表
        """
        if not codes:
            return []
            
        valid_codes = []
        for code in codes:
            normalized_code = StockUtils.normalize_stock_code(code)
            if normalized_code:
                valid_codes.append(normalized_code)
                
        return valid_codes
        
    @staticmethod
    def get_market(code):
        """
        获取股票所属市场
        """
        if not code:
            return None
            
        code = str(code).strip()
        
        # 如果包含市场后缀，直接返回
        if '.' in code:
            return code.split('.')[-1]
            
        # 根据前缀判断市场
        if len(code) >= 1:
            return StockUtils.MARKET_PREFIXES.get(code[0])
            
        return None
        
    @staticmethod
    def has_special_mark(code):
        """
        检查股票是否包含特殊标记（ST/退市等）
        """
        if not code:
            return False
            
        code = str(code).strip()
        
        # 移除市场后缀
        if '.' in code:
            code = code.split('.')[0]
            
        # 检查是否包含特殊标记
        for mark in StockUtils.SPECIAL_MARKS.keys():
            if mark in code:
                return True
                
        return False 