import os
import sys
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename
from datetime import datetime
import pandas as pd

# 使用导入工具设置项目路径
from utils.import_utils import setup_project_path
setup_project_path()

from app import UPLOAD_FOLDER, allowed_file

from features.index_futures_market_service import IndexFuturesMarketService, init_index_futures_service

# 创建股指期货服务蓝图
futures_blueprint = Blueprint('futures', __name__, url_prefix='/futures')

def get_index_futures_service():
    """获取股指期货服务实例"""
    from features.index_futures_market_service import futures_service
    return futures_service

@futures_blueprint.route('/market_data', methods=['GET'])
def get_futures_market_data():
    """获取股指期货市场数据接口"""
    futures_service = get_index_futures_service()
    if futures_service:
        return jsonify(futures_service.get_futures_data())
    return jsonify({"error": "股指期货服务未启动"}), 503

@futures_blueprint.route('/futures_list', methods=['GET'])
def get_futures_list():
    """获取股指期货列表接口"""
    futures_service = get_index_futures_service()
    if futures_service:
        return jsonify(futures_service.get_futures_list())
    return jsonify({"error": "股指期货服务未启动"}), 503

@futures_blueprint.route('/set_futures_list', methods=['POST'])
def set_futures_list():
    """设置股指期货列表接口"""
    futures_service = get_index_futures_service()
    if not futures_service:
        return jsonify({"error": "股指期货服务未启动"}), 503

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
        futures_service = get_index_futures_service()
        success, message = futures_service.set_futures_list_from_file(file_path)

        # 删除临时文件
        os.remove(file_path)

        if success:
            return jsonify({"message": message}), 200
        else:
            return jsonify({"error": message}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@futures_blueprint.route('/futures_info/<futures_code>', methods=['GET'])
def get_futures_info(futures_code):
    """获取股指期货详细信息接口"""
    futures_service = get_index_futures_service()
    if not futures_service:
        return jsonify({"error": "股指期货服务未启动"}), 503

    try:
        info = futures_service.get_futures_info(futures_code)
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@futures_blueprint.route('/health', methods=['GET'])
def health_check():
    """股指期货服务健康检查"""
    return jsonify({
        "service": "index_futures_market_service",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    })

@futures_blueprint.route('/alerts/recent', methods=['GET'])
def get_futures_alerts():
    """获取股指期货异常提示接口"""
    futures_service = get_index_futures_service()
    if not futures_service:
        return jsonify({"error": "股指期货服务未启动"}), 503

    try:
        minutes = request.args.get('minutes', 30, type=int)
        alerts = futures_service.get_futures_alerts(minutes)
        return jsonify(alerts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@futures_blueprint.route('/alerts/by_type', methods=['GET'])
def get_futures_alerts_by_type():
    """获取指定类型的股指期货异常提示接口"""
    futures_service = get_index_futures_service()
    if not futures_service:
        return jsonify({"error": "股指期货服务未启动"}), 503

    try:
        alert_type = request.args.get('type', '')
        minutes = request.args.get('minutes', 30, type=int)
        
        if not alert_type:
            return jsonify({"error": "缺少异常类型参数"}), 400
            
        alerts = futures_service.get_futures_alerts_by_type(alert_type, minutes)
        return jsonify(alerts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@futures_blueprint.route('/alerts/stats', methods=['GET'])
def get_futures_alert_stats():
    """获取股指期货异常提示统计接口"""
    futures_service = get_index_futures_service()
    if not futures_service:
        return jsonify({"error": "股指期货服务未启动"}), 503

    try:
        stats = futures_service.get_futures_alert_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500 