"""
期货数据增强器
用于为期货行情数据添加关键字段，如 ProductName, ExpireDate
"""

import logging
import pandas as pd
from mini_stock.futures_instrument_model import FuturesInstrumentModel


class FuturesDataEnhancer:
    """期货数据增强器，为行情数据添加关键字段"""
    
    @staticmethod
    def enhance_kline_data(kline_data, futures_list):
        """
        为行情数据添加关键字段
        
        Args:
            kline_data (dict): 原始行情数据，格式为 {code: [columns, dataframe]}
            futures_list (list): FuturesInstrumentModel 列表
            
        Returns:
            dict: 添加了关键字段的增强行情数据
        """
        enhanced_kline_data = {}
        
        # 构建代码到模型的映射字典
        code_to_model_map = FuturesDataEnhancer._build_code_to_model_map(futures_list)
        
        for code, data in kline_data.items():
            # 移除后缀获取原始代码
            original_code = FuturesDataEnhancer._extract_original_code(code)
            
            # 查找对应的 FuturesInstrumentModel
            feature_model = code_to_model_map.get(original_code)
            
            # 处理数据并添加关键字段
            enhanced_kline_data[code] = FuturesDataEnhancer._add_key_fields_to_data_item(data, feature_model)
        
        return enhanced_kline_data
    
    @staticmethod
    def _build_code_to_model_map(futures_list):
        """构建代码到模型的映射字典，提高查找效率"""
        code_to_model_map = {}
        for model in futures_list:
            if isinstance(model, FuturesInstrumentModel):
                instrument_id = getattr(model, 'InstrumentID', None)
                if instrument_id:
                    code_to_model_map[instrument_id] = model
        return code_to_model_map
    
    @staticmethod
    def _extract_original_code(code):
        """
        从带后缀的代码中提取原始代码
        
        Args:
            code (str): 带后缀的代码，如 "IF2401.IF"
            
        Returns:
            str: 原始代码，如 "IF2401"
        """
        # 移除常见的后缀
        suffixes = [".IF", ".IC", ".IH", ".IM", ".AU", ".AG", ".CU", ".AL", ".ZN", ".PB", 
                   ".NI", ".SN", ".RB", ".HC", ".SS", ".I", ".J", ".JM", ".ZC", ".MA", 
                   ".TA", ".EG", ".PF", ".SA", ".FG", ".UR", ".SR", ".CF", ".CY", ".AP", 
                   ".CJ", ".OI", ".RM", ".SF", ".SM", ".PK", ".TS", ".TF", ".T"]
        
        for suffix in suffixes:
            if code.endswith(suffix):
                return code[:-len(suffix)]
        
        return code
    
    @staticmethod
    def _add_key_fields_to_data_item(data, feature_model):
        """
        为单个数据项添加关键字段
        
        Args:
            data: 原始数据项，格式为 [columns, dataframe]
            feature_model: FuturesInstrumentModel 实例
            
        Returns:
            添加了关键字段的数据项
        """
        # 如果没有找到对应的模型，直接返回原数据
        if not feature_model:
            return data
        
        # 提取关键字段
        key_fields = {
            'ProductName': getattr(feature_model, 'ProductName', None),
            'ExpireDate': getattr(feature_model, 'ExpireDate', None)
        }
        
        # 检查 dataframe 是否为 pandas DataFrame
        if isinstance(data, pd.DataFrame):
            # 使用 DataFrame 的 assign 方法一次性添加所有新列
            enhanced_dataframe = data.assign(**key_fields)

            # 返回增强后的数据，保持原有格式
            return enhanced_dataframe
        else:
            # 如果不是 DataFrame，保持原样
            return data

    @staticmethod
    def get_model_by_code(code, futures_list):
        """
        根据代码获取模型
        
        Args:
            code (str): 期货代码
            futures_list (list): FuturesInstrumentModel 列表
            
        Returns:
            FuturesInstrumentModel or None: 找到的模型或None
        """
        code_to_model_map = FuturesDataEnhancer._build_code_to_model_map(futures_list)
        return code_to_model_map.get(code)
    
    @staticmethod
    def get_all_codes(futures_list):
        """
        获取所有支持的期货代码
        
        Args:
            futures_list (list): FuturesInstrumentModel 列表
            
        Returns:
            list: 期货代码列表
        """
        code_to_model_map = FuturesDataEnhancer._build_code_to_model_map(futures_list)
        return list(code_to_model_map.keys()) 