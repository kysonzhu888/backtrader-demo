from flask import Blueprint, jsonify, request
from datetime import datetime
import logging

# 使用导入工具设置项目路径
from utils.import_utils import setup_project_path
setup_project_path()

from .mysterious_fund_market_service import get_mysterious_fund_service, init_mysterious_fund_service

# 创建神秘资金服务蓝图
mysterious_fund_blueprint = Blueprint('mysterious_fund', __name__, url_prefix='/mysterious_fund')

def get_mysterious_fund_service_instance():
    """获取神秘资金服务实例"""
    return get_mysterious_fund_service()

@mysterious_fund_blueprint.route('/market_data', methods=['GET'])
def get_mysterious_fund_market_data():
    """获取神秘资金市场数据接口"""
    mysterious_fund_service = get_mysterious_fund_service_instance()
    if mysterious_fund_service:
        return jsonify(mysterious_fund_service.get_fund_data())
    return jsonify({"error": "神秘资金服务未启动"}), 503

@mysterious_fund_blueprint.route('/fund_list', methods=['GET'])
def get_mysterious_fund_list():
    """获取神秘资金列表接口"""
    mysterious_fund_service = get_mysterious_fund_service_instance()
    if mysterious_fund_service:
        return jsonify(mysterious_fund_service.get_fund_list())
    return jsonify({"error": "神秘资金服务未启动"}), 503

@mysterious_fund_blueprint.route('/health', methods=['GET'])
def health_check():
    """神秘资金服务健康检查"""
    return jsonify({
        "service": "mysterious_fund_market_service",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    })

@mysterious_fund_blueprint.route('/alerts/recent', methods=['GET'])
def get_mysterious_fund_alerts():
    """获取神秘资金异常提示接口"""
    mysterious_fund_service = get_mysterious_fund_service_instance()
    if not mysterious_fund_service:
        return jsonify({"error": "神秘资金服务未启动"}), 503

    try:
        minutes = request.args.get('minutes', 30, type=int)
        alerts = mysterious_fund_service.get_mysterious_fund_alerts(minutes)
        return jsonify(alerts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@mysterious_fund_blueprint.route('/alerts/by_type', methods=['GET'])
def get_mysterious_fund_alerts_by_type():
    """获取指定类型的神秘资金异常提示接口"""
    mysterious_fund_service = get_mysterious_fund_service_instance()
    if not mysterious_fund_service:
        return jsonify({"error": "神秘资金服务未启动"}), 503

    try:
        alert_type = request.args.get('type', '')
        minutes = request.args.get('minutes', 30, type=int)
        
        if not alert_type:
            return jsonify({"error": "缺少异常类型参数"}), 400
            
        alerts = mysterious_fund_service.get_mysterious_fund_alerts_by_type(alert_type, minutes)
        return jsonify(alerts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@mysterious_fund_blueprint.route('/alerts/stats', methods=['GET'])
def get_mysterious_fund_alert_stats():
    """获取神秘资金异常提示统计接口"""
    mysterious_fund_service = get_mysterious_fund_service_instance()
    if not mysterious_fund_service:
        return jsonify({"error": "神秘资金服务未启动"}), 503

    try:
        stats = mysterious_fund_service.get_mysterious_fund_alert_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@mysterious_fund_blueprint.route('/service_stats', methods=['GET'])
def get_mysterious_fund_service_stats():
    """获取神秘资金服务统计信息接口"""
    mysterious_fund_service = get_mysterious_fund_service_instance()
    if not mysterious_fund_service:
        return jsonify({"error": "神秘资金服务未启动"}), 503

    try:
        stats = mysterious_fund_service.get_service_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500 