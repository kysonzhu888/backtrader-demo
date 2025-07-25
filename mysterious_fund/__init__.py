"""
神秘资金监控模块

该模块提供对沪深300ETF（510300.SH）等ETF基金的异常成交量监控功能，
当一分钟成交量超过设定阈值时发出告警。

主要组件：
- MysteriousFundAlertDetector: 异常检测器
- MysteriousFundMarketService: 市场数据服务
- MysteriousFundBlueprint: Flask蓝图和API接口
"""

from .mysterious_fund_alert_detector import MysteriousFundAlertDetector
from .mysterious_fund_market_service import MysteriousFundMarketService
from .mysterious_fund_blueprint import mysterious_fund_blueprint

__version__ = "1.0.0"
__author__ = "Trading System"

__all__ = [
    'MysteriousFundAlertDetector',
    'MysteriousFundMarketService', 
    'mysterious_fund_blueprint'
] 