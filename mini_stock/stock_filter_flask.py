from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import requests
import environment
import json
import os
from datetime import datetime

app = Flask(__name__)

# 配置市场数据服务地址
STOCK_MARKET_SERVICE_URL = f"http://{environment.STOCK_MARKET_SERVICE_HOST}:5000"


def get_stocks_from_service(min_listed_days=90, exclude_st=True, exclude_delisted=True,
                            exclude_limit_up=True, exclude_suspended=True):
    """从市场数据服务获取股票列表"""
    try:
        params = {
            'min_listed_days': min_listed_days,
            'exclude_st': str(exclude_st).lower(),
            'exclude_delisted': str(exclude_delisted).lower(),
            'exclude_limit_up': str(exclude_limit_up).lower(),
            'exclude_suspended': str(exclude_suspended).lower()
        }
        response = requests.get(f"{STOCK_MARKET_SERVICE_URL}/filtered_stocks", params=params)
        if response.status_code == 200:
            data = response.json()
            return pd.DataFrame(data)
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"连接市场数据服务失败: {str(e)}")
        return pd.DataFrame()


@app.route('/')
def index():
    """主页面"""
    return render_template('stock_filter.html')


@app.route('/filter', methods=['POST'])
def filter_stocks():
    """处理股票筛选请求"""
    try:
        # 获取表单数据
        count = int(request.form.get('count', 20))
        conditions = request.form.getlist('conditions')

        # 筛选条件
        exclude_st = "排除ST" in conditions
        exclude_delisted = "排除退市" in conditions

        # 获取股票数据
        all_stocks = get_stocks_from_service(
            exclude_st=exclude_st,
            exclude_delisted=exclude_delisted
        )

        if all_stocks.empty:
            return jsonify({'error': '没有获取到股票数据，请检查市场数据服务是否正在运行'})

        # 筛选逻辑
        filtered = all_stocks.copy()

        # 按交易所筛选
        if "上交所" in conditions:
            filtered = filtered[filtered["市场"] == "SH"]
        if "深交所" in conditions:
            filtered = filtered[filtered["市场"] == "SZ"]
        if "创业板" in conditions:
            filtered = filtered[filtered["股票代码"].str.startswith("300")]
        if "科创板" in conditions:
            filtered = filtered[filtered["股票代码"].str.startswith("688")]

        # 按市值排序
        if "市值(亿)" in filtered.columns:
            if "按市值升序" in conditions:
                filtered = filtered.sort_values("市值(亿)", ascending=True)
            elif "按市值降序" in conditions:
                filtered = filtered.sort_values("市值(亿)", ascending=False)

        # 限制数量
        filtered = filtered.head(count)

        # 转换为HTML表格
        table_html = filtered.to_html(classes='table table-striped', index=False)

        return jsonify({
            'success': True,
            'table_html': table_html,
            'count': len(filtered)
        })

    except Exception as e:
        return jsonify({'error': f'筛选失败: {str(e)}'})


@app.route('/export_csv')
def export_csv():
    """导出CSV文件"""
    try:
        # 这里需要从session或缓存中获取筛选后的数据
        # 简化处理，重新获取数据
        all_stocks = get_stocks_from_service()
        if not all_stocks.empty:
            filename = f"filtered_stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join('output', filename)
            os.makedirs('output', exist_ok=True)
            all_stocks.to_csv(filepath, index=False)
            return send_file(filepath, as_attachment=True, download_name=filename)
        else:
            return jsonify({'error': '没有数据可导出'})
    except Exception as e:
        return jsonify({'error': f'导出失败: {str(e)}'})


@app.route('/export_excel')
def export_excel():
    """导出Excel文件"""
    try:
        all_stocks = get_stocks_from_service()
        if not all_stocks.empty:
            filename = f"filtered_stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = os.path.join('output', filename)
            os.makedirs('output', exist_ok=True)
            all_stocks.to_excel(filepath, index=False)
            return send_file(filepath, as_attachment=True, download_name=filename)
        else:
            return jsonify({'error': '没有数据可导出'})
    except Exception as e:
        return jsonify({'error': f'导出失败: {str(e)}'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8501)
