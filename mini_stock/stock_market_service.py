import os
import time
import logging
import threading

from mini_stock.utils.stock_price_utils import StockPriceUtils
# 使用导入工具设置项目路径
from utils.import_utils import setup_project_path
setup_project_path()

from xtquant import xtdata
from date_utils import DateUtils
from mini_stock.mini_stock_report_reader import MiniStockReportReader
import pandas as pd
import environment
from mini_stock.utils.stock_utils import StockUtils
from mini_stock.utils.trading_time_utils import TradingTimeUtils
from mini_stock.stock_data_manager import StockDataManager, StockFilter
from mini_stock.redis_cache_manager import init_cache_manager, get_cache_manager
from mini_stock.alert_detector import get_alert_detector
from mini_stock.stock_data_model import StockTickData, StockDataFactory


class StockMarketService:
    def __init__(self, report_dir=None, report_date=None):
        # 如果没有指定report_dir，则使用相对于当前文件的默认路径
        if report_dir is None:
            # 获取当前文件所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 构建reports目录路径
            report_dir = os.path.join(current_dir, "reports")
        
        # 确保reports目录存在
        if not os.path.exists(report_dir):
            try:
                os.makedirs(report_dir, exist_ok=True)
                logging.info(f"创建reports目录: {report_dir}")
            except Exception as e:
                logging.error(f"创建reports目录失败: {e}")
                # 如果创建失败，使用当前工作目录下的reports
                report_dir = os.path.join(os.getcwd(), "reports")
                os.makedirs(report_dir, exist_ok=True)
                logging.info(f"使用备用reports目录: {report_dir}")
        
        self.report_dir = report_dir
        self.period = "tick"
        self.report_date = report_date if report_date else DateUtils.now()
        self.code_list = self.load_stock_list()
        self.last_data = {}  # 缓存最新的行情数据
        self.data_lock = threading.Lock()  # 数据锁

        # 初始化Redis缓存管理器
        self.cache_manager = init_cache_manager(
            host=getattr(environment, 'REDIS_HOST', 'localhost'),
            port=getattr(environment, 'REDIS_PORT', 6379),
            db=getattr(environment, 'REDIS_DB', 0),
            password=getattr(environment, 'REDIS_PASSWORD', None)
        )
        self.preclose_dict = StockPriceUtils.get_all_preclose(self.code_list)

        # 启动数据更新线程
        self.running = True
        self.update_thread = threading.Thread(target=self._update_market_data, daemon=True)
        self.update_thread.start()

    def load_stock_list(self):
        """加载股票列表（用调仓日期）"""
        date_str = self.report_date.strftime("%Y%m%d")
        codes = MiniStockReportReader.read_stock_codes(self.report_dir, date_str)
        if not codes:
            logging.warning(f"持仓文件不存在或无股票代码，检查路径: {self.report_dir}")
            return []
        return codes

    def subscribe_all(self):
        """订阅所有股票行情（用监控日期）"""
        for code in self.code_list:
            try:
                xtdata.subscribe_quote(code, period=self.period, count=-1)
                logging.debug(f"已订阅 {code} {self.period}")
            except Exception as e:
                logging.error(f"订阅{code}失败: {e}")
        logging.info(f"已订阅 {len(self.code_list)} 条代码")

    def cache_preclose_if_needed(self):
        """只在需要时缓存前收盘价数据"""
        if not self.cache_manager or not self.preclose_dict:
            return
        
        try:
            # 使用智能缓存方法，只在Redis中不存在时才缓存
            self.cache_manager.cache_preclose_data_if_not_exists(self.preclose_dict)
        except Exception as e:
            logging.error(f"缓存前收盘价数据失败: {e}")

    def _update_market_data(self):
        """更新市场数据的后台线程（用监控日期）"""
        # 使用 TradingTimeUtils 获取最新数据
        if TradingTimeUtils.is_trading_time():
            self.subscribe_all()
            time.sleep(5)

        while self.running:
            try:
                kline_data = TradingTimeUtils.get_latest_trading_data(self.code_list, DateUtils.now())

                with self.data_lock:
                    self.last_data = kline_data

                # 缓存数据到Redis
                if self.cache_manager and kline_data and TradingTimeUtils.is_trading_time():
                    # 使用StockDataFactory转换数据格式
                    try:

                        if not self.cache_manager.get_preclose_data():
                            self.preclose_dict = StockPriceUtils.get_all_preclose(self.code_list)
                            # 使用专门的方法缓存前收盘价
                            self.cache_preclose_if_needed()

                        # 将原始数据转换为StockTickData实例
                        stock_data_dict = StockDataFactory.create_batch_from_xtquant_data(kline_data)
                        
                        # 批量缓存到Redis - 修复类型问题
                        self.cache_manager.cache_stocks_batch(stock_data_dict)
                        
                    except Exception as e:
                        logging.error(f"转换和缓存股票数据失败: {e}")
                        # 如果转换失败，使用原始数据缓存
                        cache_data = {}
                        for code, data in kline_data.items():
                            if isinstance(data, dict):
                                cache_data[code] = data
                            elif hasattr(data, 'to_dict'):
                                cache_data[code] = data.to_dict()
                            else:
                                cache_data[code] = str(data)
                        
                        if cache_data:
                            self.cache_manager.cache_stocks_batch(cache_data)

                # 根据是否在交易时间决定日志级别和更新频率
                if TradingTimeUtils.is_trading_time():
                    logging.info(f"[market data]行情数据更新成功，共{len(kline_data)}条")
                    time.sleep(3)  # 交易时间内3秒更新一次
                else:
                    logging.info(f"[market data]非交易时段，使用最近收盘价数据，共{len(kline_data)}条")
                    time.sleep(60)  # 非交易时间60秒更新一次

            except Exception as e:
                logging.error(f"更新行情数据失败: {e}")
                time.sleep(5)  # 发生错误时5秒后重试

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

    def get_market_data(self):
        """获取最新的市场数据"""
        with self.data_lock:
            return self._convert_to_json_serializable(self.last_data)

    def get_preclose_prices(self):
        """获取所有股票的前收盘价"""
        return self.preclose_dict.copy()

    def get_stock_list(self):
        """获取股票列表"""
        return self.code_list.copy()

    def stop(self):
        """停止服务"""
        self.running = False
        self.update_thread.join()

    def set_stock_list_from_file(self, file_path):
        """从文件设置股票列表"""
        try:
            ext = os.path.splitext(file_path)[1].lower()
            codes = []

            if ext == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    codes = [line.strip() for line in f if line.strip()]
            elif ext == '.csv':
                df = pd.read_csv(file_path)
                # 假设第一列是股票代码
                codes = df.iloc[:, 0].astype(str).tolist()
            elif ext in ['.xls', '.xlsx']:
                df = pd.read_excel(file_path)
                # 假设第一列是股票代码
                codes = df.iloc[:, 0].astype(str).tolist()
            else:
                raise ValueError(f"不支持的文件格式: {ext}")

            # 使用StockUtils验证和过滤股票代码
            codes = StockUtils.filter_valid_stock_codes(codes)

            if not codes:
                raise ValueError("文件中没有有效的股票代码")

            # 更新股票列表
            with self.data_lock:
                self.code_list = codes
                # 重新获取前收盘价
                self.preclose_dict = StockPriceUtils.get_all_preclose(self.code_list)

            logging.info(f"成功从文件更新股票列表，共{len(codes)}只股票")
            return True, f"成功更新股票列表，共{len(codes)}只股票"

        except Exception as e:
            error_msg = f"更新股票列表失败: {str(e)}"
            logging.error(error_msg)
            return False, error_msg

    def get_filtered_stocks(self, min_listed_days=90, exclude_st=True, exclude_delisted=True,
                            exclude_limit_up=True, exclude_suspended=True):
        """获取筛选后的股票列表"""
        try:
            filter_condition = StockFilter(
                min_listed_days=min_listed_days,
                exclude_st=exclude_st,
                exclude_delisted=exclude_delisted,
                exclude_limit_up=exclude_limit_up,
                exclude_suspended=exclude_suspended
            )

            stocks_dict = StockDataManager.filter_stocks(filter_condition, DateUtils.now())

            # 转换为前端友好的格式
            stocks_list = []
            for code, info in stocks_dict.items():
                stocks_list.append({
                    "股票代码": code,
                    "股票名称": info.name,
                    "市值(亿)": round(info.market_value_in_yi, 2),
                    "是否ST": "ST" in info.name,
                    "是否退市": "退" in info.name or "退市" in info.name,
                    "市场": code.split(".")[-1]
                })

            return stocks_list
        except Exception as e:
            logging.error(f"获取筛选股票列表失败: {str(e)}")
            return []

    def get_stock_data_today(self, stock_code: str, limit: int | None = None, return_stock_data: bool = False):
        """获取某只股票当天的所有数据"""
        if not self.cache_manager:
            return []
        
        try:
            data = self.cache_manager.get_stock_data_today(stock_code, limit, return_stock_data)
            if return_stock_data:
                # 如果返回StockTickData实例，直接返回
                return data
            else:
                # 如果返回dict，转换为JSON可序列化格式
                return self._convert_to_json_serializable(data)
        except Exception as e:
            logging.error(f"获取股票当天数据失败 {stock_code}: {e}")
            return []

    def get_cache_stats(self):
        """获取缓存统计信息"""
        if not self.cache_manager:
            return {}
        
        try:
            return self.cache_manager.get_cache_stats()
        except Exception as e:
            logging.error(f"获取缓存统计失败: {e}")
            return {}

    def clear_cache(self):
        """清空缓存"""
        if not self.cache_manager:
            return False
        
        try:
            return self.cache_manager.clear_today_data()
        except Exception as e:
            logging.error(f"清空缓存失败: {e}")
            return False

    def get_recent_alerts(self, minutes: int = 30):
        """获取最近的异常提示"""
        try:
            detector = get_alert_detector()
            alerts = detector.get_recent_alerts(minutes)
            return [alert.to_dict() for alert in alerts]
        except Exception as e:
            logging.error(f"获取异常提示失败: {e}")
            return []

    def get_alerts_by_type(self, alert_type: str, minutes: int = 30):
        """获取指定类型的异常提示"""
        try:
            from alert_detector import AlertType
            alert_enum = None
            for at in AlertType:
                if at.value == alert_type:
                    alert_enum = at
                    break
            
            if alert_enum:
                detector = get_alert_detector()
                alerts = detector.get_alerts_by_type(alert_enum, minutes)
                return [alert.to_dict() for alert in alerts]
            return []
        except Exception as e:
            logging.error(f"获取指定类型异常提示失败: {e}")
            return []

    def get_alert_stats(self):
        """获取异常提示统计信息"""
        try:
            detector = get_alert_detector()
            return detector.get_alert_stats()
        except Exception as e:
            logging.error(f"获取异常提示统计失败: {e}")
            return {}
