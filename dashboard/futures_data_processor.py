import logging
import requests
from date_utils import DateUtils
import environment


def get_futures_market_url():
    """获取期货行情数据URL"""
    host = getattr(environment, 'STOCK_MARKET_SERVICE_HOST', 'localhost')
    port = getattr(environment, 'STOCK_MARKET_SERVICE_PORT', 5000)
    return f"http://{host}:{port}/futures/market_data"


def extract_futures_data_from_kline(kline):
    """
    从kline数据中提取期货行情信息

    Args:
        kline: 期货行情数据，可能是字典、DataFrame或列表格式

    Returns:
        dict: 包含 last, last_close, volume, open_interest 的字典
    """
    last = None
    last_close = None
    volume = None
    open_interest = None
    product_name = None

    # 统一处理不同数据格式
    if isinstance(kline, dict):
        # 如果是字典格式，直接使用
        last = kline.get('lastPrice') or kline.get('close')
        last_close = kline.get('lastClose') or kline.get('preClose')
        volume = kline.get('volume')
        open_interest = kline.get('openInterest')
        product_name = kline.get('ProductName')
    elif hasattr(kline, 'iloc'):
        # 如果是 DataFrame，取最后一行
        if not kline.empty:
            last = kline.iloc[-1].get('lastPrice') or kline.iloc[-1].get('close')
            last_close = kline.iloc[-1].get('lastClose') or kline.iloc[-1].get('preClose')
            volume = kline.iloc[-1].get('volume')
            open_interest = kline.iloc[-1].get('openInterest')
            product_name = kline.iloc[-1].get('ProductName')
    elif isinstance(kline, list) and len(kline) > 0:
        #kine 样板数据：[{'amount': 28984287200.0, 'close': 5876.400000000001, 'high': 5888.0, 'low': 5839.8, 'open': 5877.6, 'openInterest': 68707, 'preClose': 5856.6, 'settelementPrice': 0.0, 'suspendFlag': 0, 'time': 1751472000000, 'volume': 24709}]
        # 如果是列表，取最后一个元素
        last = kline[-1].get('lastPrice') or kline[-1].get('close')
        last_close = kline[-1].get('lastClose') or kline[-1].get('preClose')
        volume = kline[-1].get('volume')
        open_interest = kline[-1].get('openInterest')
        product_name = kline[-1].get('ProductName')

    return {
        'last': last,
        'last_close': last_close,
        'volume': volume,
        'open_interest': open_interest,
        'product_name': product_name
    }


def calculate_futures_changes(last, last_close):
    """
    计算期货涨跌幅和涨跌额

    Args:
        last: 最新价
        last_close: 前收盘价

    Returns:
        tuple: (change, change_pct) 涨跌额和涨跌幅
    """
    change = None
    change_pct = None
    if last is not None and last_close is not None and last_close != 0:
        change = round(last - last_close, 2)
        change_pct = round((last - last_close) / last_close * 100, 2)

    return change, change_pct


def format_futures_values(last, volume, open_interest):
    """
    格式化期货数值，保留2位小数

    Args:
        last: 最新价
        volume: 成交量
        open_interest: 持仓量

    Returns:
        tuple: (formatted_last, formatted_volume, formatted_open_interest)
    """
    formatted_last = round(last, 2) if last is not None else None
    formatted_volume = round(volume, 2) if volume is not None else None
    formatted_open_interest = round(open_interest, 2) if open_interest is not None else None

    return formatted_last, formatted_volume, formatted_open_interest


def process_futures_market_data():
    """
    处理期货市场数据，获取并格式化期货行情
    
    Returns:
        tuple: (snap_list, update_time) 期货数据列表和更新时间
    """
    try:
        response = requests.get(get_futures_market_url())
        if response.status_code == 200:
            data = response.json()
            snap_list = []
            
            for idx, (code, kline) in enumerate(data.items(), 1):
                # 提取数据
                futures_data = extract_futures_data_from_kline(kline)
                last = futures_data['last']
                last_close = futures_data['last_close']
                volume = futures_data['volume']
                open_interest = futures_data['open_interest']
                product_name = futures_data['product_name']

                # 计算涨跌幅和涨跌额
                change, change_pct = calculate_futures_changes(last, last_close)
                
                # 格式化数值，保留2位小数
                formatted_last, formatted_volume, formatted_open_interest = format_futures_values(
                    last, volume, open_interest
                )
                
                snap_list.append({
                    '序号': idx,
                    '合约代码': code,
                    '名称': product_name,
                    '最新价': formatted_last,
                    '涨幅': change_pct,
                    '涨跌额': change,
                    '成交量': formatted_volume,
                    '持仓量': formatted_open_interest,
                })
            
            return snap_list, DateUtils.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            return [], DateUtils.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logging.error(f"获取股指行情失败: {e}")
        return [], DateUtils.now().strftime("%Y-%m-%d %H:%M:%S") 