"""
缓存配置文件
用于管理Redis缓存的配置选项
"""

from enum import Enum
from typing import Dict, Any


class CacheMode(Enum):
    """缓存模式枚举"""
    ESSENTIAL = "essential"  # 只缓存核心字段
    FULL = "full"  # 缓存完整字段


class CacheConfig:
    """缓存配置类"""
    
    # 默认配置
    DEFAULT_CONFIG = {
        'cache_mode': CacheMode.ESSENTIAL.value,
        'essential_fields': [
            'time', 'lastPrice', 'open', 'high', 'low', 'lastClose', 
            'amount', 'volume', 'timestamp'
        ],
        'full_fields': [
            'time', 'lastPrice', 'open', 'high', 'low', 'lastClose',
            'amount', 'volume', 'pvolume', 'tickvol', 'stockStatus',
            'openInt', 'lastSettlementPrice', 'askPrice', 'bidPrice',
            'askVol', 'bidVol', 'settlementPrice', 'transactionNum', 'pe',
            'timestamp'
        ],
        'cache_expire_seconds': {
            'latest_data': 300,  # 最新数据5分钟过期
            'daily_data': 86400,  # 日数据24小时过期
            'preclose_data': 86400,  # 前收盘价24小时过期
            'filter_cache': 300,  # 筛选结果5分钟过期
        },
        'max_cache_size': {
            'daily_records_per_stock': 1000,  # 每只股票每天最多缓存1000条记录
            'total_stocks': 5000,  # 最多缓存5000只股票
        }
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化缓存配置
        
        Args:
            config: 自定义配置字典，如果为None则使用默认配置
        """
        self.config = config or self.DEFAULT_CONFIG.copy()
    
    @property
    def cache_mode(self) -> str:
        """获取缓存模式"""
        return self.config.get('cache_mode', CacheMode.ESSENTIAL.value)
    
    @property
    def essential_fields(self) -> list:
        """获取核心字段列表"""
        return self.config.get('essential_fields', self.DEFAULT_CONFIG['essential_fields'])
    
    @property
    def full_fields(self) -> list:
        """获取完整字段列表"""
        return self.config.get('full_fields', self.DEFAULT_CONFIG['full_fields'])
    
    @property
    def cache_expire_seconds(self) -> Dict[str, int]:
        """获取缓存过期时间配置"""
        return self.config.get('cache_expire_seconds', self.DEFAULT_CONFIG['cache_expire_seconds'])
    
    @property
    def max_cache_size(self) -> Dict[str, int]:
        """获取最大缓存大小配置"""
        return self.config.get('max_cache_size', self.DEFAULT_CONFIG['max_cache_size'])
    
    def get_expire_seconds(self, cache_type: str) -> int:
        """
        获取指定类型的缓存过期时间
        
        Args:
            cache_type: 缓存类型
            
        Returns:
            int: 过期时间（秒）
        """
        return self.cache_expire_seconds.get(cache_type, 300)
    
    def get_max_records_per_stock(self) -> int:
        """获取每只股票的最大记录数"""
        return self.max_cache_size.get('daily_records_per_stock', 1000)
    
    def get_max_total_stocks(self) -> int:
        """获取最大股票总数"""
        return self.max_cache_size.get('total_stocks', 5000)
    
    def is_essential_mode(self) -> bool:
        """是否为核心字段模式"""
        return self.cache_mode == CacheMode.ESSENTIAL.value
    
    def is_full_mode(self) -> bool:
        """是否为完整字段模式"""
        return self.cache_mode == CacheMode.FULL.value
    
    def get_fields_for_mode(self, mode: str = None) -> list:
        """
        根据模式获取字段列表
        
        Args:
            mode: 缓存模式，如果为None则使用当前配置的模式
            
        Returns:
            list: 字段列表
        """
        if mode is None:
            mode = self.cache_mode
        
        if mode == CacheMode.ESSENTIAL.value:
            return self.essential_fields
        elif mode == CacheMode.FULL.value:
            return self.full_fields
        else:
            return self.essential_fields  # 默认返回核心字段
    
    def update_config(self, new_config: Dict[str, Any]):
        """
        更新配置
        
        Args:
            new_config: 新的配置字典
        """
        self.config.update(new_config)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.config.copy()


# 全局配置实例
global_cache_config = CacheConfig()


def get_cache_config() -> CacheConfig:
    """获取全局缓存配置"""
    return global_cache_config


def set_cache_config(config: Dict[str, Any]):
    """设置全局缓存配置"""
    global global_cache_config
    global_cache_config = CacheConfig(config)


def create_essential_config() -> CacheConfig:
    """创建核心字段模式的配置"""
    config = CacheConfig.DEFAULT_CONFIG.copy()
    config['cache_mode'] = CacheMode.ESSENTIAL.value
    return CacheConfig(config)


def create_full_config() -> CacheConfig:
    """创建完整字段模式的配置"""
    config = CacheConfig.DEFAULT_CONFIG.copy()
    config['cache_mode'] = CacheMode.FULL.value
    return CacheConfig(config)


def create_custom_config(cache_mode: str, custom_fields: list = None, 
                        expire_seconds: Dict[str, int] = None) -> CacheConfig:
    """
    创建自定义配置
    
    Args:
        cache_mode: 缓存模式
        custom_fields: 自定义字段列表
        expire_seconds: 自定义过期时间配置
        
    Returns:
        CacheConfig: 自定义配置实例
    """
    config = CacheConfig.DEFAULT_CONFIG.copy()
    config['cache_mode'] = cache_mode
    
    if custom_fields:
        if cache_mode == CacheMode.ESSENTIAL.value:
            config['essential_fields'] = custom_fields
        elif cache_mode == CacheMode.FULL.value:
            config['full_fields'] = custom_fields
    
    if expire_seconds:
        config['cache_expire_seconds'].update(expire_seconds)
    
    return CacheConfig(config) 