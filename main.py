#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
主启动文件
启动共享的Flask服务，提供股票和期货服务
"""

import os
import sys
from datetime import datetime
import environment

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from app import get_app, register_blueprint, run_app
from mini_stock.stock_blueprint import stock_blueprint, init_market_service
from features.futures_blueprint import futures_blueprint
from features.index_futures_market_service import init_index_futures_service


def main():
    """主函数"""
    print("正在启动市场数据服务...")
    
    # 获取Flask应用实例
    app = get_app()
    
    # 初始化股票服务
    print("初始化股票服务...")
    report_date = datetime(2025, 6, 12)  # 可以根据需要修改日期
    init_market_service(report_date=report_date)
    
    # 初始化股指期货服务
    print("初始化股指期货服务...")
    init_index_futures_service(report_date=report_date)
    
    # 注册蓝图
    print("注册服务蓝图...")
    register_blueprint(stock_blueprint)
    register_blueprint(futures_blueprint)
    
    # 添加根路径健康检查
    @app.route('/')
    def health_check():
        return {
            "service": "stock_market_service",
            "status": "running",
            "services": {
                "stock": "/stock",
                "index_futures": "/futures"
            },
            "timestamp": datetime.now().isoformat()
        }
    
    # 启动服务
    host = getattr(environment, 'STOCK_MARKET_SERVICE_HOST', '0.0.0.0')
    port = getattr(environment, 'STOCK_MARKET_SERVICE_PORT', 5000)
    debug = getattr(environment, 'DEBUG', False)
    
    print(f"服务启动在 http://{host}:{port}")
    print("股票服务API: /stock/*")
    print("股指期货服务API: /futures/*")
    
    run_app(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
