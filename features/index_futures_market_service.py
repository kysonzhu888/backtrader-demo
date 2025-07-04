import os
import time
import logging
import threading
from datetime import datetime
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename
import pandas as pd

import environment
from mini_stock.redis_cache_manager import init_cache_manager
from mini_stock.stock_data_model import StockDataFactory
# 使用导入工具设置项目路径
from utils.import_utils import setup_project_path
setup_project_path()

from app import UPLOAD_FOLDER, allowed_file
from xtquant import xtdata
from mini_stock.futures_instrument_model import FuturesInstrumentModel
from mini_stock.utils.trading_time_utils import TradingTimeUtils
from date_utils import DateUtils
from mini_stock.utils.stock_price_utils import StockPriceUtils
from mini_stock.futures_data_enhancer import FuturesDataEnhancer
from features.index_futures_alert_detector import get_index_futures_alert_detector


# 全局变量存储期货服务实例
futures_service = None

class IndexFuturesMarketService:
    """股指期货市场数据服务（线程安全，自动后台更新，xtquant行情）"""
    
    def __init__(self, report_dir=None, report_date=None, sector_name="IF"):
        self.report_dir = report_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
        self.report_date = report_date if report_date else datetime.now()
        self.sector_name = sector_name
        self.futures_list = self.load_futures_list()

        # 初始化Redis缓存管理器
        self.cache_manager = init_cache_manager(
            host=getattr(environment, 'REDIS_HOST', 'localhost'),
            port=getattr(environment, 'REDIS_PORT', 6379),
            db=getattr(environment, 'REDIS_DB', 0),
            password=getattr(environment, 'REDIS_PASSWORD', None)
        )

        # 初始化股指期货异常检测器
        self.alert_detector = get_index_futures_alert_detector()

        self.preclose_dict = self.get_all_preclose()  # 完全复用上一日收盘价逻辑
        self.last_data = {}
        self.data_lock = threading.Lock()
        self.running = True
        self.update_thread = threading.Thread(target=self._update_data, daemon=True)
        self.update_thread.start()

    def load_futures_list(self):
        """只获取期货合约详细信息列表，不包含期权且只保留正在交易且主力合约(MainContract=1或2)"""
        try:
            codes = xtdata.get_stock_list_in_sector(self.sector_name)
            # 只保留不包含 '-C-' 和 '-P-' 的合约（即期货）
            filtered = [c for c in codes if '-C-' not in c and '-P-' not in c]
            result = []
            for code in filtered:
                info = xtdata.get_instrument_detail(code)
                if info:
                    model = FuturesInstrumentModel(**info)
                    if getattr(model, 'IsTrading', True) and getattr(model, 'MainContract', 0) in (1, 2, 3):
                        result.append(model)
            if not result:
                logging.warning(f"未获取到期货合约详细信息: 板块={self.sector_name}")
                return []
            return result
        except Exception as e:
            logging.error(f"获取期货合约详细信息失败: {e}")
            return []
    
    def subscribe_all(self):
        """订阅所有期货行情"""
        for model in self.futures_list:
            try:
                code = getattr(model, 'InstrumentID', None)
                if code:
                    code = code + ".IF"
                if code:
                    xtdata.subscribe_quote(code, period='tick', count=-1)
                    logging.debug(f"已订阅 {code} tick")
            except Exception as e:
                logging.error(f"订阅{getattr(model, 'InstrumentID', None)}失败: {e}")
        logging.info(f"已订阅 {len(self.futures_list)} 条期货代码")

    def _update_data(self):
        """后台定时批量拉取期货行情数据，完全对齐 StockMarketService 的 _update_market_data"""
        self.subscribe_all()
        time.sleep(5)

        while self.running:
            try:
                code_list = []
                for model in self.futures_list:
                    if isinstance(model, FuturesInstrumentModel):
                        instrument_id = getattr(model, 'InstrumentID', None)
                        if instrument_id:
                            code_list.append(instrument_id + ".IF")
                if not code_list:
                    time.sleep(10)
                    continue
                kline_data = TradingTimeUtils.get_latest_trading_data(code_list, DateUtils.now())
                
                # 使用数据增强器为行情数据添加 feature 字段
                enhanced_kline_data = FuturesDataEnhancer.enhance_kline_data(kline_data, self.futures_list)
                
                with self.data_lock:
                    self.last_data = enhanced_kline_data

                # 缓存数据到Redis
                if self.cache_manager and kline_data and TradingTimeUtils.is_trading_time():
                    # 使用StockDataFactory转换数据格式
                    try:
                        if not self.cache_manager.get_preclose_data():
                            self.preclose_dict = self.get_all_preclose()
                            # 使用专门的方法缓存前收盘价
                            self.cache_preclose_if_needed()

                        # 将原始数据转换为StockTickData实例
                        stock_data_dict = StockDataFactory.create_batch_from_xtquant_data(kline_data)

                        # 批量缓存到Redis - 修复类型问题
                        # 直接转换为字典格式，避免类型不匹配
                        cache_data = {}
                        for code, stock_data in stock_data_dict.items():
                            if hasattr(stock_data, 'to_dict'):
                                cache_data[code] = stock_data.to_dict()
                            else:
                                cache_data[code] = stock_data
                        self.cache_manager.cache_stocks_batch(cache_data)
                    except Exception as e:
                        logging.error(f"转换和缓存期货数据失败: {e}")

                # 根据是否在交易时间决定日志级别和更新频率
                if TradingTimeUtils.is_trading_time():
                    logging.info(f"[futures market]行情数据更新成功，共{len(kline_data)}条")
                    time.sleep(3)
                else:
                    logging.info(f"[futures market]非交易时段，使用最近收盘价数据，共{len(kline_data)}条")
                    time.sleep(60)
            except Exception as e:
                logging.error(f"期货数据更新失败: {e}")
                time.sleep(5)

    def cache_preclose_if_needed(self):
        """只在需要时缓存前收盘价数据"""
        if not self.cache_manager or not self.preclose_dict:
            return

        try:
            # 使用智能缓存方法，只在Redis中不存在时才缓存
            self.cache_manager.cache_preclose_data_if_not_exists(self.preclose_dict)
        except Exception as e:
            logging.error(f"缓存前收盘价数据失败: {e}")

    def _convert_to_json_serializable(self, data):
        """将数据转换为JSON可序列化格式"""
        if isinstance(data, pd.DataFrame):
            return data.to_dict(orient='records')
        elif isinstance(data, dict):
            return {k: self._convert_to_json_serializable(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_to_json_serializable(item) for item in data]
        elif isinstance(data, (int, float, str, bool, type(None))):
            return data
        else:
            return str(data)

    def get_futures_data(self):
        """获取最新期货市场数据"""
        with self.data_lock:
            return self._convert_to_json_serializable(self.last_data)
    
    def get_futures_list(self):
        """获取期货列表"""
        return self.futures_list.copy()
    
    def set_futures_list_from_file(self, file_path):
        """从文件设置期货列表"""
        try:
            ext = os.path.splitext(file_path)[1].lower()
            codes = []
            if ext == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    codes = [line.strip() for line in f if line.strip()]
            elif ext == '.csv':
                df = pd.read_csv(file_path)
                codes = df.iloc[:, 0].astype(str).tolist()
            elif ext in ['.xls', '.xlsx']:
                df = pd.read_excel(file_path)
                codes = df.iloc[:, 0].astype(str).tolist()
            else:
                raise ValueError(f"不支持的文件格式: {ext}")
            if not codes:
                raise ValueError("文件中没有有效的期货代码")
            with self.data_lock:
                self.futures_list = codes
            logging.info(f"成功从文件更新期货列表，共{len(codes)}个期货")
            return True, f"成功更新期货列表，共{len(codes)}个期货"
        except Exception as e:
            error_msg = f"更新期货列表失败: {str(e)}"
            logging.error(error_msg)
            return False, error_msg
    
    def get_futures_info(self, futures_code):
        """获取期货详细信息（xtdata）"""
        try:
            info = xtdata.get_instrument_detail(futures_code)
            if not info:
                return {"code": futures_code, "error": "未找到合约信息"}
            return info
        except Exception as e:
            return {"code": futures_code, "error": str(e)}

    def stop(self):
        self.running = False
        self.update_thread.join()

    def get_all_preclose(self):
        """获取所有期货的前收盘价，复用 StockPriceUtils 工具"""
        code_list = []
        for model in self.futures_list:
            if isinstance(model, FuturesInstrumentModel):
                instrument_id = getattr(model, 'InstrumentID', None)
                if instrument_id:
                    code_list.append(instrument_id + ".IF")
        return StockPriceUtils.get_all_preclose(code_list)

    def get_futures_alerts(self, minutes: int = 30):
        """获取股指期货异常提示"""
        try:
            if self.alert_detector:
                alerts = self.alert_detector.get_recent_alerts(minutes)
                return [alert.to_dict() for alert in alerts]
            return []
        except Exception as e:
            logging.error(f"获取股指期货异常提示失败: {e}")
            return []

    def get_futures_alerts_by_type(self, alert_type: str, minutes: int = 30):
        """获取指定类型的股指期货异常提示"""
        try:
            if self.alert_detector:
                from features.index_futures_alert_detector import IndexFuturesAlertType
                alert_enum = None
                for at in IndexFuturesAlertType:
                    if at.value == alert_type:
                        alert_enum = at
                        break
                
                if alert_enum:
                    alerts = self.alert_detector.get_alerts_by_type(alert_enum, minutes)
                    return [alert.to_dict() for alert in alerts]
            return []
        except Exception as e:
            logging.error(f"获取指定类型股指期货异常提示失败: {e}")
            return []

    def get_futures_alert_stats(self):
        """获取股指期货异常提示统计信息"""
        try:
            if self.alert_detector:
                return self.alert_detector.get_alert_stats()
            return {}
        except Exception as e:
            logging.error(f"获取股指期货异常提示统计失败: {e}")
            return {}

def init_index_futures_service(report_date=None, sector_name="IF"):
    """初始化股指期货服务"""
    global futures_service
    futures_service = IndexFuturesMarketService(report_date=report_date, sector_name=sector_name)
