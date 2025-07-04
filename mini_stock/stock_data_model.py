from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


@dataclass
class StockTickData:
    """
    股票tick数据模型
    根据迅投API文档：https://dict.thinktrader.net/dictionary/stock.html?id=7zqjlm#%E5%86%85%E7%BD%AEpython-2
    """
    
    # 基础时间价格信息
    time: str  # 时间，格式：YYYYMMDDHHMMSS
    lastPrice: float  # 最新价
    open: float  # 开盘价
    high: float  # 最高价
    low: float  # 最低价
    lastClose: float  # 昨收价
    
    # 成交量和金额
    amount: float  # 成交额（元）
    volume: float  # 成交量（手）
    pvolume: float  # 盘口成交量
    tickvol: float  # 逐笔成交量
    
    # 状态和持仓信息
    stockStatus: int  # 股票状态
    openInt: int  # 持仓量（期货）
    lastSettlementPrice: float  # 昨结算价
    
    # 盘口信息
    askPrice: List[float]  # 卖价数组[卖一价, 卖二价, 卖三价, 卖四价, 卖五价]
    bidPrice: List[float]  # 买价数组[买一价, 买二价, 买三价, 买四价, 买五价]
    askVol: List[int]  # 卖量数组[卖一量, 卖二量, 卖三量, 卖四量, 卖五量]
    bidVol: List[int]  # 买量数组[买一量, 买二量, 买三量, 买四量, 买五量]
    
    # 其他信息
    settlementPrice: float  # 结算价
    transactionNum: int  # 成交笔数
    pe: float  # 市盈率
    
    # 缓存相关字段
    timestamp: Optional[str] = None  # 数据缓存时间戳
    
    def __post_init__(self):
        """初始化后处理"""
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StockTickData':
        """从字典创建实例"""
        # 创建数据副本避免修改原始数据
        data_copy = data.copy()
        
        # 数据类型转换已经在_validate_data_dict中处理
        # 这里只需要处理可能的字符串格式的列表字段
        list_fields = ['askPrice', 'bidPrice', 'askVol', 'bidVol']
        for field in list_fields:
            if isinstance(data_copy.get(field), str):
                data_copy[field] = StockDataFactory._safe_convert_to_list(data_copy[field])
        
        # 验证和补充缺失字段
        data_copy = StockDataFactory._validate_data_dict(data_copy)
        
        return cls(**data_copy)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'StockTickData':
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def get_essential_fields(self) -> Dict[str, Any]:
        """
        获取核心字段（用于缓存优化）
        只包含最重要的字段：time, lastPrice, open, high, low, lastClose, amount, volume
        """
        return {
            'time': self.time,
            'lastPrice': self.lastPrice,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'lastClose': self.lastClose,
            'amount': self.amount,
            'volume': self.volume,
            'timestamp': self.timestamp
        }
    
    def get_full_fields(self) -> Dict[str, Any]:
        """获取完整字段（包含所有信息）"""
        return self.to_dict()
    
    @property
    def price_change(self) -> float:
        """价格变动"""
        return self.lastPrice - self.lastClose
    
    @property
    def price_change_pct(self) -> float:
        """价格变动百分比"""
        if self.lastClose == 0:
            return 0.0
        return (self.price_change / self.lastClose) * 100
    
    @property
    def amplitude(self) -> float:
        """振幅"""
        if self.lastClose == 0:
            return 0.0
        return ((self.high - self.low) / self.lastClose) * 100
    
    @property
    def turnover_rate(self) -> float:
        """换手率（需要总股本信息，这里返回0）"""
        return 0.0
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"StockTickData({self.time}, 价格:{self.lastPrice}, 涨跌幅:{self.price_change_pct:.2f}%)"


class StockDataFactory:
    """
    股票数据工厂类，用于创建和解析股票数据
    
    主要功能：
    1. 从迅投API数据创建StockTickData实例
    2. 支持多种数据格式：字典、DataFrame、字符串、列表等
    3. 批量处理股票数据
    4. 数据验证和类型转换
    
    使用示例：
        # 从字典创建
        data_dict = {'time': '20250701105100', 'lastPrice': 8.48, ...}
        stock_data = StockDataFactory.create_from_xtquant_data(data_dict)
        
        # 从DataFrame创建
        import pandas as pd
        df = pd.DataFrame([...])
        stock_data = StockDataFactory.create_from_xtquant_data(df)
        
        # 批量处理
        batch_data = {'000001': data1, '000002': data2}
        result = StockDataFactory.create_batch_from_xtquant_data(batch_data)
    """
    
    @staticmethod
    def _safe_convert_to_list(value: Any) -> List:
        """安全地将值转换为列表"""
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            try:
                if value.startswith('[') and value.endswith(']'):
                    import ast
                    result = ast.literal_eval(value)
                    return result if isinstance(result, list) else []
                else:
                    return []
            except Exception:
                return []
        else:
            return []
    
    @staticmethod
    def _safe_convert_to_float(value: Any) -> float:
        """安全地将值转换为浮点数"""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    @staticmethod
    def _safe_convert_to_int(value: Any) -> int:
        """安全地将值转换为整数"""
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    
    @staticmethod
    def _validate_data_dict(data_dict: Dict[str, Any]) -> Dict[str, Any]:
        """验证和清理数据字典"""
        # 确保所有必需字段都存在
        required_fields = [
            'time', 'lastPrice', 'open', 'high', 'low', 'lastClose',
            'amount', 'volume', 'pvolume', 'tickvol', 'stockStatus',
            'openInt', 'lastSettlementPrice', 'askPrice', 'bidPrice',
            'askVol', 'bidVol', 'settlementPrice', 'transactionNum', 'pe'
        ]
        
        # 为缺失字段设置默认值
        float_fields = ['lastPrice', 'open', 'high', 'low', 'lastClose', 'amount', 'volume', 'pvolume', 'tickvol', 'lastSettlementPrice', 'settlementPrice', 'pe']
        int_fields = ['stockStatus', 'openInt', 'transactionNum']
        list_fields = ['askPrice', 'bidPrice', 'askVol', 'bidVol']
        
        # 创建新的字典，确保所有字段都存在
        validated_dict = {}
        
        for field in required_fields:
            if field in data_dict:
                validated_dict[field] = data_dict[field]
            else:
                # 设置默认值
                if field in float_fields:
                    validated_dict[field] = 0.0
                elif field in int_fields:
                    validated_dict[field] = 0
                elif field in list_fields:
                    validated_dict[field] = []
                else:
                    validated_dict[field] = ""
        
        # 确保数据类型正确
        for field in float_fields:
            if field in validated_dict:
                validated_dict[field] = StockDataFactory._safe_convert_to_float(validated_dict[field])
        
        for field in int_fields:
            if field in validated_dict:
                validated_dict[field] = StockDataFactory._safe_convert_to_int(validated_dict[field])
        
        for field in list_fields:
            if field in validated_dict:
                validated_dict[field] = StockDataFactory._safe_convert_to_list(validated_dict[field])
        
        # 确保time字段是字符串
        if 'time' in validated_dict:
            validated_dict['time'] = str(validated_dict['time'])
        
        return validated_dict
    
    @staticmethod
    def create_from_xtquant_data(data: Any, stock_code: str = "") -> StockTickData:
        """
        从迅投API数据创建StockTickData实例
        
        Args:
            data: 迅投API返回的数据
            stock_code: 股票代码（用于日志）
            
        Returns:
            StockTickData: 股票数据实例
        """
        try:
            # 处理不同的数据格式
            # data 数据样板：（data frame 格式）
            #time,lastPrice,open,high,low,lastClose,amount,volume,pvolume,tickvol,stockStatus,openInt,lastSettlementPrice,askPrice,bidPrice,askVol,bidVol,settlementPrice,transactionNum,pe
            #20250701105100,1751338260000,8.48,8.31,8.68,8.23,8.24,23538925.000000004,27810,2781033,4,3,13,0.0,"[8.48, 8.51, 8.52, 8.53, 8.59]","[8.47, 8.450000000000001, 8.440000000000001, 8.430000000000001, 8.420000000000002]","[1, 8, 46, 25, 28]","[14, 76, 76, 129, 160]",0.0,2368,0.0

            data_dict: Dict[str, Any] = {}
            
            # 处理pandas DataFrame
            if hasattr(data, 'to_dict') and hasattr(data, 'columns'):
                # 可能是pandas DataFrame
                try:
                    if len(data) > 0:
                        # 获取第一行数据
                        first_row = data.iloc[0]
                        data_dict = first_row.to_dict()
                except Exception:
                    # 如果不是DataFrame，尝试其他方法
                    data_dict = data.to_dict()
            elif hasattr(data, 'to_dict'):
                data_dict = data.to_dict()
            elif isinstance(data, dict):
                data_dict = data.copy()  # 创建副本避免修改原始数据
            elif hasattr(data, '__dict__'):
                data_dict = data.__dict__.copy()
            elif isinstance(data, str):
                # 处理CSV字符串格式
                if data.startswith('[') and data.endswith(']'):
                    # 列表格式的字符串
                    import ast
                    try:
                        data_list = ast.literal_eval(data)
                        if len(data_list) >= 20:  # 确保有足够的字段
                            data_dict = {
                                'time': str(data_list[0]),
                                'lastPrice': float(data_list[1]),
                                'open': float(data_list[2]),
                                'high': float(data_list[3]),
                                'low': float(data_list[4]),
                                'lastClose': float(data_list[5]),
                                'amount': float(data_list[6]),
                                'volume': float(data_list[7]),
                                'pvolume': float(data_list[8]),
                                'tickvol': float(data_list[9]),
                                'stockStatus': int(data_list[10]),
                                'openInt': int(data_list[11]),
                                'lastSettlementPrice': float(data_list[12]),
                                'askPrice': data_list[13] if isinstance(data_list[13], list) else [],
                                'bidPrice': data_list[14] if isinstance(data_list[14], list) else [],
                                'askVol': data_list[15] if isinstance(data_list[15], list) else [],
                                'bidVol': data_list[16] if isinstance(data_list[16], list) else [],
                                'settlementPrice': float(data_list[17]),
                                'transactionNum': int(data_list[18]),
                                'pe': float(data_list[19])
                            }
                    except Exception as parse_error:
                        raise ValueError(f"无法解析列表格式数据: {data}, 错误: {parse_error}")
                else:
                    # 尝试解析CSV格式
                    try:
                        import csv
                        from io import StringIO
                        csv_reader = csv.reader(StringIO(data))
                        data_list = next(csv_reader)  # 获取第一行数据
                        if len(data_list) >= 20:
                            data_dict = {
                                'time': str(data_list[0]),
                                'lastPrice': float(data_list[1]),
                                'open': float(data_list[2]),
                                'high': float(data_list[3]),
                                'low': float(data_list[4]),
                                'lastClose': float(data_list[5]),
                                'amount': float(data_list[6]),
                                'volume': float(data_list[7]),
                                'pvolume': float(data_list[8]),
                                'tickvol': float(data_list[9]),
                                'stockStatus': int(data_list[10]),
                                'openInt': int(data_list[11]),
                                'lastSettlementPrice': float(data_list[12]),
                                'askPrice': eval(data_list[13]) if data_list[13].startswith('[') else [],
                                'bidPrice': eval(data_list[14]) if data_list[14].startswith('[') else [],
                                'askVol': eval(data_list[15]) if data_list[15].startswith('[') else [],
                                'bidVol': eval(data_list[16]) if data_list[16].startswith('[') else [],
                                'settlementPrice': float(data_list[17]),
                                'transactionNum': int(data_list[18]),
                                'pe': float(data_list[19])
                            }
                    except Exception as csv_error:
                        raise ValueError(f"无法解析CSV格式数据: {data}, 错误: {csv_error}")
            elif hasattr(data, '__iter__') and not isinstance(data, (str, bytes)):
                # 处理可迭代对象（如列表、元组等）
                try:
                    data_list = list(data)
                    if len(data_list) >= 20:
                        data_dict = {
                            'time': str(data_list[0]),
                            'lastPrice': float(data_list[1]),
                            'open': float(data_list[2]),
                            'high': float(data_list[3]),
                            'low': float(data_list[4]),
                            'lastClose': float(data_list[5]),
                            'amount': float(data_list[6]),
                            'volume': float(data_list[7]),
                            'pvolume': float(data_list[8]),
                            'tickvol': float(data_list[9]),
                            'stockStatus': int(data_list[10]),
                            'openInt': int(data_list[11]),
                            'lastSettlementPrice': float(data_list[12]),
                            'askPrice': data_list[13] if isinstance(data_list[13], list) else [],
                            'bidPrice': data_list[14] if isinstance(data_list[14], list) else [],
                            'askVol': data_list[15] if isinstance(data_list[15], list) else [],
                            'bidVol': data_list[16] if isinstance(data_list[16], list) else [],
                            'settlementPrice': float(data_list[17]),
                            'transactionNum': int(data_list[18]),
                            'pe': float(data_list[19])
                        }
                except Exception as iter_error:
                    raise ValueError(f"无法处理可迭代对象: {data}, 错误: {iter_error}")
            else:
                raise ValueError(f"不支持的数据格式: {type(data)}")
            
            # 验证和清理数据字典
            data_dict = StockDataFactory._validate_data_dict(data_dict)
            
            return StockTickData.from_dict(data_dict)
            
        except Exception as e:
            import logging
            logging.error(f"创建股票数据失败 {stock_code}: {e}, 原始数据: {data}")
            # 返回默认数据
            return StockTickData(
                time=datetime.now().strftime('%Y%m%d%H%M%S'),
                lastPrice=0.0,
                open=0.0,
                high=0.0,
                low=0.0,
                lastClose=0.0,
                amount=0.0,
                volume=0.0,
                pvolume=0.0,
                tickvol=0.0,
                stockStatus=0,
                openInt=0,
                lastSettlementPrice=0.0,
                askPrice=[],
                bidPrice=[],
                askVol=[],
                bidVol=[],
                settlementPrice=0.0,
                transactionNum=0,
                pe=0.0
            )
    
    @staticmethod
    def create_batch_from_xtquant_data(data_dict: Dict[str, Any]) -> Dict[str, StockTickData]:
        """
        批量从迅投API数据创建StockTickData实例
        
        Args:
            data_dict: 股票代码到数据的映射
            
        Returns:
            Dict[str, StockTickData]: 股票代码到StockTickData实例的映射
        """
        result = {}
        for stock_code, data in data_dict.items():
            try:
                result[stock_code] = StockDataFactory.create_from_xtquant_data(data, stock_code)
            except Exception as e:
                import logging
                logging.error(f"批量创建股票数据失败 {stock_code}: {e}")
                continue
        return result 