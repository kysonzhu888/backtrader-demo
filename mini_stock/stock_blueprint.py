from flask import Blueprint, jsonify, request
import os
from werkzeug.utils import secure_filename

# 使用导入工具设置项目路径
from utils.import_utils import setup_project_path
setup_project_path()

from app import UPLOAD_FOLDER, allowed_file
from mini_stock.stock_market_service import StockMarketService

# 创建股票服务蓝图
stock_blueprint = Blueprint('stock', __name__, url_prefix='/stock')

# 全局变量存储StockMarketService实例
market_service = None

def init_market_service(report_date=None):
    """初始化StockMarketService"""
    global market_service
    market_service = StockMarketService(report_date=report_date)

@stock_blueprint.route('/market_data', methods=['GET'])
def get_market_data():
    """获取市场数据接口"""
    if market_service:
        return jsonify(market_service.get_market_data())
    return jsonify({"error": "服务未启动"}), 503

@stock_blueprint.route('/preclose', methods=['GET'])
def get_preclose():
    """获取前收盘价接口"""
    if market_service:
        return jsonify(market_service.get_preclose_prices())
    return jsonify({"error": "服务未启动"}), 503

@stock_blueprint.route('/stock_list', methods=['GET'])
def get_stock_list():
    """获取股票列表接口"""
    if market_service:
        return jsonify(market_service.get_stock_list())
    return jsonify({"error": "服务未启动"}), 503

@stock_blueprint.route('/set_stock_list', methods=['POST'])
def set_stock_list():
    """设置股票列表接口"""
    if not market_service:
        return jsonify({"error": "服务未启动"}), 503

    if 'file' not in request.files:
        return jsonify({"error": "没有上传文件"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "没有选择文件"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "不支持的文件格式"}), 400

    try:
        # 安全地保存文件
        filename = secure_filename(file.filename or "unknown")
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        # 处理文件
        success, message = market_service.set_stock_list_from_file(file_path)

        # 删除临时文件
        os.remove(file_path)

        if success:
            return jsonify({"message": message}), 200
        else:
            return jsonify({"error": message}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stock_blueprint.route('/filtered_stocks', methods=['GET'])
def get_filtered_stocks():
    """获取筛选后的股票列表接口"""
    if not market_service:
        return jsonify({"error": "服务未启动"}), 503

    try:
        # 从查询参数中获取筛选条件
        min_listed_days = request.args.get('min_listed_days', 90, type=int)
        exclude_st = request.args.get('exclude_st', 'true').lower() == 'true'
        exclude_delisted = request.args.get('exclude_delisted', 'true').lower() == 'true'
        exclude_limit_up = request.args.get('exclude_limit_up', 'true').lower() == 'true'
        exclude_suspended = request.args.get('exclude_suspended', 'true').lower() == 'true'

        stocks = market_service.get_filtered_stocks(
            min_listed_days=min_listed_days,
            exclude_st=exclude_st,
            exclude_delisted=exclude_delisted,
            exclude_limit_up=exclude_limit_up,
            exclude_suspended=exclude_suspended
        )

        return jsonify(stocks)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stock_blueprint.route('/stock_data_today/<stock_code>', methods=['GET'])
def get_stock_data_today(stock_code):
    """获取某只股票当天的所有数据接口"""
    if not market_service:
        return jsonify({"error": "服务未启动"}), 503

    try:
        limit = request.args.get('limit', type=int)
        data = market_service.get_stock_data_today(stock_code, limit)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stock_blueprint.route('/cache_stats', methods=['GET'])
def get_cache_stats():
    """获取缓存统计信息接口"""
    if not market_service:
        return jsonify({"error": "服务未启动"}), 503

    try:
        stats = market_service.get_cache_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stock_blueprint.route('/clear_cache', methods=['POST'])
def clear_cache():
    """清空缓存接口"""
    if not market_service:
        return jsonify({"error": "服务未启动"}), 503

    try:
        success = market_service.clear_cache()
        if success:
            return jsonify({"message": "缓存清空成功"}), 200
        else:
            return jsonify({"error": "缓存清空失败"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stock_blueprint.route('/alerts/recent', methods=['GET'])
def get_recent_alerts():
    """获取最近的异常提示接口"""
    if not market_service:
        return jsonify({"error": "服务未启动"}), 503

    try:
        minutes = request.args.get('minutes', 30, type=int)
        alerts = market_service.get_recent_alerts(minutes)
        return jsonify(alerts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stock_blueprint.route('/alerts/type/<alert_type>', methods=['GET'])
def get_alerts_by_type(alert_type):
    """获取指定类型的异常提示接口"""
    if not market_service:
        return jsonify({"error": "服务未启动"}), 503

    try:
        minutes = request.args.get('minutes', 30, type=int)
        alerts = market_service.get_alerts_by_type(alert_type, minutes)
        return jsonify(alerts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stock_blueprint.route('/alerts/stats', methods=['GET'])
def get_alert_stats():
    """获取异常提示统计信息接口"""
    if not market_service:
        return jsonify({"error": "服务未启动"}), 503

    try:
        stats = market_service.get_alert_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500 