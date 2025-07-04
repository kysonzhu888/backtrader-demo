import environment
from environment import tushare_token
import os
import json
import logging
from typing import Dict, List

import tushare as ts
from xtquant import xtdata

def initialize_tushare():
    # 设置 tushare token
    ts.set_token(tushare_token)
    # 初始化 pro 接口
    return ts.pro_api()

class StockCacheManager:
    """股票代码缓存管理器"""
    
    def __init__(self, cache_file: str = 'stock_cache.json'):
        self.cache_file = cache_file
        
    def load_cache(self) -> Dict[str, str]:
        """加载股票代码缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"加载股票缓存失败: {str(e)}")
        return {}
        
    def save_cache(self, cache: Dict[str, str]):
        """保存股票代码缓存"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存股票缓存失败: {str(e)}")
            
    def update_cache(self, ts_codes: List[str]) -> Dict[str, str]:
        """更新股票代码缓存"""
        cache = self.load_cache()
        missing_codes = [code for code in ts_codes if code not in cache]
        
        if missing_codes:
            try:
                pro = initialize_tushare()
                company_df = pro.stock_basic(ts_code=','.join(missing_codes), fields='ts_code,name')
                new_cache = dict(zip(company_df['ts_code'], company_df['name']))
                cache.update(new_cache)
                self.save_cache(cache)
            except Exception as e:
                logging.error(f"更新股票缓存失败: {str(e)}")
                
        return cache 

    def get_stock_name(self, code: str) -> str:
        """获取股票名称"""
        cache = self.load_cache()
        return cache.get(code, "")

    def update_stock_name(self, code: str, name: str):
        """更新股票名称"""
        cache = self.load_cache()
        cache[code] = name
        self.save_cache(cache)

    def update_stock_names(self, codes: List[str]):
        """更新股票名称列表"""
        cache = self.load_cache()
        for code in codes:
            if code not in cache:
                # 实时查xtdata
                try:
                    detail = xtdata.get_instrument_detail(code)
                    name = detail.get('InstrumentName', '') if detail else ''
                    if name:
                        cache[code] = name
                        self.save_cache(cache)
                except Exception as e:
                    logging.error(f"获取股票{code}名称失败: {str(e)}")

    def get_stock_names(self, codes: List[str]) -> Dict[str, str]:
        """获取股票名称列表"""
        cache = self.load_cache()
        return {code: self.get_stock_name(code) for code in codes} 