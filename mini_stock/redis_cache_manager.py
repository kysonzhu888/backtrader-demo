import redis
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import pandas as pd
from mini_stock.stock_data_model import StockTickData, StockDataFactory
from mini_stock.cache_config import get_cache_config, CacheMode
from utils.code_type_utils import CodeTypeRecognizer


class RedisCacheManager:
    """Redis缓存管理类，用于管理股票实时数据缓存"""

    def __init__(self, host='localhost', port=6379, db=0, password=None, cache_mode=None):
        """
        初始化Redis缓存管理器
        
        Args:
            host: Redis服务器地址
            port: Redis端口
            db: Redis数据库编号
            password: Redis密码
            cache_mode: 缓存模式，如果为None则使用全局配置
        """
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True  # 自动解码响应
            )
            # 测试连接
            self.redis_client.ping()
            logging.info("Redis连接成功")

            # 获取缓存配置
            self.config = get_cache_config()
            self.cache_mode = cache_mode or self.config.cache_mode
            
            # 启动定时清理任务
            self.running = True
            self.cleanup_thread = threading.Thread(target=self._cleanup_task, daemon=True)
            self.cleanup_thread.start()

        except Exception as e:
            logging.error(f"Redis连接失败: {e}")
            self.redis_client = None

    def _is_futures_code(self, code: str) -> bool:
        return CodeTypeRecognizer.is_futures_code(code)

    def _get_today_key(self, stock_code: str) -> str:
        """生成当天的数据key，区分股票和股指期货"""
        today = datetime.now().strftime('%Y%m%d')
        if self._is_futures_code(stock_code):
            return f"futures_data:{stock_code}:{today}"
        else:
            return f"stock_data:{stock_code}:{today}"

    def _get_latest_key(self, stock_code: str) -> str:
        """生成最新数据的key，区分股票和股指期货"""
        if self._is_futures_code(stock_code):
            return f"futures_latest:{stock_code}"
        else:
            return f"stock_latest:{stock_code}"

    def _get_filter_cache_key(self, conditions: Dict) -> str:
        """生成筛选结果缓存key"""
        import hashlib
        conditions_str = json.dumps(conditions, sort_keys=True)
        hash_value = hashlib.md5(conditions_str.encode()).hexdigest()
        return f"filter_cache:{hash_value}"

    def _get_preclose_key(self, code_type: str = "stock") -> str:
        """生成前收盘价缓存key，区分股票和股指期货"""
        today = datetime.now().strftime('%Y%m%d')
        if code_type == "futures":
            return f"futures_preclose:{today}"
        else:
            return f"preclose:{today}"

    def _prepare_data_for_cache(self, data: Union[Dict, StockTickData]) -> Dict[str, Any]:
        """
        准备缓存数据，根据缓存模式选择字段
        
        Args:
            data: 原始数据或StockTickData实例
            
        Returns:
            Dict: 准备缓存的数据
        """
        if isinstance(data, StockTickData):
            # 如果是StockTickData实例，根据缓存模式选择字段
            if self.cache_mode == CacheMode.ESSENTIAL.value:
                return data.get_essential_fields()
            else:
                return data.get_full_fields()
        elif isinstance(data, dict):
            # 如果是字典，尝试转换为StockTickData
            try:
                stock_data = StockTickData.from_dict(data)
                if self.cache_mode == CacheMode.ESSENTIAL.value:
                    return stock_data.get_essential_fields()
                else:
                    return stock_data.get_full_fields()
            except:
                # 如果转换失败，直接使用原始数据
                return data
        else:
            # 其他类型，尝试转换为StockTickData
            try:
                stock_data = StockDataFactory.create_from_xtquant_data(data)
                if self.cache_mode == CacheMode.ESSENTIAL.value:
                    return stock_data.get_essential_fields()
                else:
                    return stock_data.get_full_fields()
            except:
                # 如果转换失败，返回原始数据的字符串表示
                return {'raw_data': str(data), 'timestamp': datetime.now().isoformat()}

    def _limit_cache_size(self, stock_code: str):
        """
        限制缓存大小，防止内存溢出
        
        Args:
            stock_code: 股票代码
        """
        try:
            today_key = self._get_today_key(stock_code)
            max_records = self.config.get_max_records_per_stock()
            
            # 获取当前记录数
            current_count = self.redis_client.llen(today_key)
            
            # 如果超过最大记录数，删除最旧的记录
            if current_count > max_records:
                excess_count = current_count - max_records
                self.redis_client.ltrim(today_key, 0, max_records - 1)
                logging.debug(f"限制缓存大小 {stock_code}: 删除了 {excess_count} 条旧记录")
                
        except Exception as e:
            logging.error(f"限制缓存大小失败 {stock_code}: {e}")

    def cache_stock_data(self, stock_code: str, data: Union[Dict[str, Any], StockTickData]) -> bool:
        """
        缓存单只股票或股指期货的实时数据
        
        Args:
            stock_code: 股票代码或股指期货代码
            data: 数据字典或StockTickData实例
            
        Returns:
            bool: 是否成功缓存
        """
        if not self.redis_client:
            return False

        try:
            # 准备缓存数据
            cache_data = self._prepare_data_for_cache(data)
            
            # 确保有时间戳
            if 'timestamp' not in cache_data:
                cache_data['timestamp'] = datetime.now().isoformat()

            # 缓存到当天的历史数据列表
            today_key = self._get_today_key(stock_code)
            self.redis_client.lpush(today_key, json.dumps(cache_data, ensure_ascii=False))

            # 限制缓存大小
            self._limit_cache_size(stock_code)

            # 设置过期时间（第二天凌晨自动过期）
            expire_seconds = self.config.get_expire_seconds('daily_data')
            self.redis_client.expire(today_key, expire_seconds)

            # 更新最新数据
            latest_key = self._get_latest_key(stock_code)
            latest_expire = self.config.get_expire_seconds('latest_data')
            self.redis_client.setex(latest_key, latest_expire, json.dumps(cache_data, ensure_ascii=False))

            return True

        except Exception as e:
            logging.error(f"缓存数据失败 {stock_code}: {e}")
            return False

    def cache_stocks_batch(self, stocks_data: Dict[str, Union[Dict[str, Any], StockTickData]]) -> bool:
        """
        批量缓存多只股票或股指期货数据
        
        Args:
            stocks_data: 数据字典，key为股票代码或股指期货代码，value为数据或StockTickData实例
            
        Returns:
            bool: 是否成功缓存
        """
        if not self.redis_client:
            return False

        try:
            # 使用管道批量操作
            pipe = self.redis_client.pipeline()

            for stock_code, data in stocks_data.items():
                # 准备缓存数据
                cache_data = self._prepare_data_for_cache(data)
                
                # 确保有时间戳
                if 'timestamp' not in cache_data:
                    cache_data['timestamp'] = datetime.now().isoformat()

                # 缓存到当天的历史数据列表
                today_key = self._get_today_key(stock_code)
                pipe.lpush(today_key, json.dumps(cache_data, ensure_ascii=False))

                # 设置过期时间
                expire_seconds = self.config.get_expire_seconds('daily_data')
                pipe.expire(today_key, expire_seconds)

                # 更新最新数据
                latest_key = self._get_latest_key(stock_code)
                latest_expire = self.config.get_expire_seconds('latest_data')
                pipe.setex(latest_key, latest_expire, json.dumps(cache_data, ensure_ascii=False))

            # 执行批量操作
            pipe.execute()
            
            # 批量限制缓存大小
            for stock_code in stocks_data.keys():
                self._limit_cache_size(stock_code)
                
            return True

        except Exception as e:
            logging.error(f"批量缓存数据失败: {e}")
            return False

    def get_stock_data_today(self, stock_code: str, limit: Optional[int] = None, return_stock_data: bool = False) -> List[Union[Dict[str, Any], StockTickData]]:
        """
        获取某只股票或股指期货当天的所有数据
        
        Args:
            stock_code: 股票代码或股指期货代码
            limit: 限制返回的数据条数，None表示返回所有数据
            return_stock_data: 是否返回StockTickData实例，False返回dict
            
        Returns:
            List[Dict] 或 List[StockTickData]: 数据列表，按时间倒序排列
        """
        if not self.redis_client:
            return []

        try:
            today_key = self._get_today_key(stock_code)

            if limit:
                data_list = self.redis_client.lrange(today_key, 0, limit - 1)
            else:
                data_list = self.redis_client.lrange(today_key, 0, -1)

            # 解析JSON数据
            result = []
            for data_str in data_list:
                try:
                    data = json.loads(data_str)
                    if return_stock_data:
                        # 尝试转换为StockTickData实例
                        try:
                            stock_data = StockTickData.from_dict(data)
                            result.append(stock_data)
                        except Exception as e:
                            logging.debug(f"转换StockTickData失败，使用原始dict: {e}")
                            result.append(data)
                    else:
                        result.append(data)
                except json.JSONDecodeError:
                    continue

            return result

        except Exception as e:
            logging.error(f"获取当天数据失败 {stock_code}: {e}")
            return []

    def get_latest_stock_data(self, stock_code: str, return_stock_data: bool = False) -> Optional[Union[Dict[str, Any], StockTickData]]:
        """
        获取某只股票或股指期货的最新数据
        
        Args:
            stock_code: 股票代码或股指期货代码
            return_stock_data: 是否返回StockTickData实例，False返回dict
            
        Returns:
            Dict 或 StockTickData: 最新数据，如果不存在返回None
        """
        if not self.redis_client:
            return None

        try:
            latest_key = self._get_latest_key(stock_code)
            data_str = self.redis_client.get(latest_key)

            if data_str:
                data = json.loads(data_str)
                if return_stock_data:
                    try:
                        return StockTickData.from_dict(data)
                    except Exception as e:
                        logging.debug(f"转换StockTickData失败，使用原始dict: {e}")
                        return data
                else:
                    return data
            return None

        except Exception as e:
            logging.error(f"获取最新数据失败 {stock_code}: {e}")
            return None

    def get_multiple_latest_data(self, stock_codes: List[str], return_stock_data: bool = False) -> Dict[str, Union[Dict[str, Any], StockTickData]]:
        """
        批量获取多只股票或股指期货的最新数据
        
        Args:
            stock_codes: 股票代码或股指期货代码列表，如果为空则返回所有数据
            return_stock_data: 是否返回StockTickData实例，False返回dict
            
        Returns:
            Dict: 代码到最新数据的映射
        """
        if not self.redis_client:
            return {}

        try:
            # 如果传入空列表，获取所有股票和股指期货的最新数据
            if not stock_codes:
                stock_keys = self.redis_client.keys("stock_latest:*")
                futures_keys = self.redis_client.keys("futures_latest:*")
                # 由于设置了decode_responses=True，返回的已经是字符串，不需要decode
                stock_codes = [key.split(':', 1)[1] for key in stock_keys]
                futures_codes = [key.split(':', 1)[1] for key in futures_keys]
                stock_codes.extend(futures_codes)
            
            if not stock_codes:
                return {}

            # 使用管道批量获取
            pipe = self.redis_client.pipeline()
            for code in stock_codes:
                latest_key = self._get_latest_key(code)
                pipe.get(latest_key)

            results = pipe.execute()

            # 解析结果
            data_dict = {}
            for i, data_str in enumerate(results):
                if data_str:
                    try:
                        data = json.loads(data_str)
                        if return_stock_data:
                            try:
                                data_dict[stock_codes[i]] = StockTickData.from_dict(data)
                            except Exception as e:
                                logging.debug(f"转换StockTickData失败，使用原始dict: {e}")
                                data_dict[stock_codes[i]] = data
                        else:
                            data_dict[stock_codes[i]] = data
                    except json.JSONDecodeError:
                        continue

            return data_dict

        except Exception as e:
            logging.error(f"批量获取最新数据失败: {e}")
            return {}

    def cache_filter_result(self, conditions: Dict, result: List[Dict], expire_seconds: int = 300) -> bool:
        """
        缓存筛选结果
        
        Args:
            conditions: 筛选条件
            result: 筛选结果
            expire_seconds: 过期时间（秒）
            
        Returns:
            bool: 是否成功缓存
        """
        if not self.redis_client:
            return False

        try:
            cache_key = self._get_filter_cache_key(conditions)
            self.redis_client.setex(cache_key, expire_seconds, json.dumps(result))
            return True

        except Exception as e:
            logging.error(f"缓存筛选结果失败: {e}")
            return False

    def get_cached_filter_result(self, conditions: Dict) -> Optional[List[Dict]]:
        """
        获取缓存的筛选结果
        
        Args:
            conditions: 筛选条件
            
        Returns:
            List[Dict]: 筛选结果，如果不存在返回None
        """
        if not self.redis_client:
            return None

        try:
            cache_key = self._get_filter_cache_key(conditions)
            data_str = self.redis_client.get(cache_key)

            if data_str:
                return json.loads(data_str)
            return None

        except Exception as e:
            logging.error(f"获取缓存筛选结果失败: {e}")
            return None

    def clear_today_data(self, code_type: str = "all") -> bool:
        """
        清空当天的数据
        
        Args:
            code_type: 代码类型，"stock"、"futures" 或 "all"
            
        Returns:
            bool: 是否成功清空
        """
        if not self.redis_client:
            return False

        try:
            today = datetime.now().strftime('%Y%m%d')
            
            if code_type == "stock":
                pattern = f"stock_data:*:{today}"
            elif code_type == "futures":
                pattern = f"futures_data:*:{today}"
            else:  # "all"
                pattern = f"*_data:*:{today}"

            # 获取所有匹配的key
            keys = self.redis_client.keys(pattern)

            if keys:
                # 批量删除
                self.redis_client.delete(*keys)
                logging.info(f"清空当天{code_type}数据成功，共删除 {len(keys)} 个key")

            return True

        except Exception as e:
            logging.error(f"清空当天{code_type}数据失败: {e}")
            return False

    def clear_all_data(self, code_type: str = "all") -> bool:
        """
        清空所有数据（包括历史数据）
        
        Args:
            code_type: 代码类型，"stock"、"futures" 或 "all"
            
        Returns:
            bool: 是否成功清空
        """
        if not self.redis_client:
            return False

        try:
            if code_type == "stock":
                patterns = ["stock_data:*", "stock_latest:*"]
            elif code_type == "futures":
                patterns = ["futures_data:*", "futures_latest:*"]
            else:  # "all"
                patterns = ["stock_data:*", "stock_latest:*", "futures_data:*", "futures_latest:*", "filter_cache:*"]

            for pattern in patterns:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                    logging.info(f"清空 {pattern} 成功，共删除 {len(keys)} 个key")

            return True

        except Exception as e:
            logging.error(f"清空所有{code_type}数据失败: {e}")
            return False

    def _cleanup_task(self):
        """定时清理任务，每天凌晨清空前一天的数据"""
        while self.running:
            try:
                now = datetime.now()

                # 计算到下一个凌晨的时间
                tomorrow = now + timedelta(days=1)
                next_midnight = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
                sleep_seconds = (next_midnight - now).total_seconds()

                # 等待到凌晨
                time.sleep(sleep_seconds)

                # 清空前一天的数据
                yesterday = (now - timedelta(days=1)).strftime('%Y%m%d')
                
                # 清理股票数据
                stock_pattern = f"stock_data:*:{yesterday}"
                stock_keys = self.redis_client.keys(stock_pattern)
                if stock_keys:
                    self.redis_client.delete(*stock_keys)
                    logging.info(f"定时清理完成，删除前一天股票数据 {len(stock_keys)} 个key")
                
                # 清理股指期货数据
                futures_pattern = f"futures_data:*:{yesterday}"
                futures_keys = self.redis_client.keys(futures_pattern)
                if futures_keys:
                    self.redis_client.delete(*futures_keys)
                    logging.info(f"定时清理完成，删除前一天股指期货数据 {len(futures_keys)} 个key")

            except Exception as e:
                logging.error(f"定时清理任务失败: {e}")
                time.sleep(60)  # 出错后等待1分钟再重试

    def get_cache_stats(self, code_type: str = "all") -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Args:
            code_type: 代码类型，"stock"、"futures" 或 "all"
            
        Returns:
            Dict: 缓存统计信息
        """
        if not self.redis_client:
            return {}

        try:
            today = datetime.now().strftime('%Y%m%d')

            if code_type == "stock":
                # 统计当天股票数据
                today_pattern = f"stock_data:*:{today}"
                today_keys = self.redis_client.keys(today_pattern)
                # 统计最新股票数据
                latest_keys = self.redis_client.keys("stock_latest:*")
                # 统计筛选缓存
                filter_keys = self.redis_client.keys("filter_cache:*")
            elif code_type == "futures":
                # 统计当天股指期货数据
                today_pattern = f"futures_data:*:{today}"
                today_keys = self.redis_client.keys(today_pattern)
                # 统计最新股指期货数据
                latest_keys = self.redis_client.keys("futures_latest:*")
                # 股指期货没有筛选缓存
                filter_keys = []
            else:  # "all"
                # 统计当天所有数据
                stock_today_pattern = f"stock_data:*:{today}"
                futures_today_pattern = f"futures_data:*:{today}"
                stock_today_keys = self.redis_client.keys(stock_today_pattern)
                futures_today_keys = self.redis_client.keys(futures_today_pattern)
                today_keys = stock_today_keys + futures_today_keys
                
                # 统计最新所有数据
                stock_latest_keys = self.redis_client.keys("stock_latest:*")
                futures_latest_keys = self.redis_client.keys("futures_latest:*")
                latest_keys = stock_latest_keys + futures_latest_keys
                
                # 统计筛选缓存
                filter_keys = self.redis_client.keys("filter_cache:*")

            # 计算总数据量
            total_records = 0
            for key in today_keys:
                total_records += self.redis_client.llen(key)

            return {
                "today_stocks": len(today_keys),
                "latest_stocks": len(latest_keys),
                "filter_caches": len(filter_keys),
                "total_records": total_records,
                "date": today,
                "code_type": code_type
            }

        except Exception as e:
            logging.error(f"获取{code_type}缓存统计失败: {e}")
            return {}

    def stop(self):
        """停止缓存管理器"""
        self.running = False
        if hasattr(self, 'cleanup_thread'):
            self.cleanup_thread.join(timeout=5)
        if self.redis_client:
            self.redis_client.close()

    def cache_preclose_data(self, preclose_dict: Dict[str, float], code_type: str = "stock") -> bool:
        """
        缓存前收盘价数据
        
        Args:
            preclose_dict: 前收盘价字典，key为股票代码或股指期货代码，value为前收盘价
            code_type: 代码类型，"stock" 或 "futures"
            
        Returns:
            bool: 是否成功缓存
        """
        if not self.redis_client:
            return False

        try:
            preclose_key = self._get_preclose_key(code_type)
            
            # 缓存前收盘价数据
            self.redis_client.setex(preclose_key, 28800, json.dumps(preclose_dict))  # 8小时过期
            
            logging.info(f"成功缓存{code_type}前收盘价数据，共{len(preclose_dict)}个")
            return True

        except Exception as e:
            logging.error(f"缓存{code_type}前收盘价数据失败: {e}")
            return False

    def get_preclose_data(self, key_prefix="", code_type: str = "stock") -> Dict[str, float]:
        """
        获取前收盘价数据
        
        Args:
            key_prefix: 键前缀
            code_type: 代码类型，"stock" 或 "futures"
            
        Returns:
            Dict[str, float]: 前收盘价字典，key为股票代码或股指期货代码，value为前收盘价
        """
        if not self.redis_client:
            return {}

        try:
            preclose_key = key_prefix + self._get_preclose_key(code_type)
            data_str = self.redis_client.get(preclose_key)

            if data_str:
                return json.loads(data_str)
            return {}

        except Exception as e:
            logging.error(f"获取{code_type}前收盘价数据失败: {e}")
            return {}

    def get_stock_preclose(self, stock_code: str) -> float:
        """
        获取单只股票或股指期货的前收盘价
        
        Args:
            stock_code: 股票代码或股指期货代码
            
        Returns:
            float: 前收盘价，如果不存在返回0
        """
        code_type = "futures" if self._is_futures_code(stock_code) else "stock"
        preclose_dict = self.get_preclose_data(code_type=code_type)
        return preclose_dict.get(stock_code, 0)

    def cache_preclose_data_if_not_exists(self, preclose_dict: Dict[str, float], code_type: str = "stock") -> bool:
        """
        只在Redis中不存在preclose数据时才缓存
        
        Args:
            preclose_dict: 前收盘价字典，key为股票代码或股指期货代码，value为前收盘价
            code_type: 代码类型，"stock" 或 "futures"
            
        Returns:
            bool: 是否成功缓存（包括已存在的情况）
        """
        if not self.redis_client:
            return False

        try:
            preclose_key = self._get_preclose_key(code_type)
            
            # 检查是否已存在数据
            if self.redis_client.exists(preclose_key):
                logging.debug(f"Redis中已存在{code_type} preclose数据，跳过缓存")
                return True
            
            # 缓存前收盘价数据
            self.redis_client.setex(preclose_key, 28800, json.dumps(preclose_dict))  # 8小时过期
            
            logging.info(f"成功缓存{code_type}前收盘价数据，共{len(preclose_dict)}个")
            return True

        except Exception as e:
            logging.error(f"缓存{code_type}前收盘价数据失败: {e}")
            return False


# 全局缓存管理器实例
cache_manager = None


def init_cache_manager(host='localhost', port=6379, db=0, password=None):
    """初始化全局缓存管理器"""
    global cache_manager
    cache_manager = RedisCacheManager(host, port, db, password)
    return cache_manager


def get_cache_manager():
    """获取全局缓存管理器实例"""
    return cache_manager
 