import environment
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import pandas as pd
import threading
import time
import requests
import logging
from date_utils import DateUtils
import base64
from layouts import get_dashboard_layout, get_index_dashboard_layout
from stock_filter_page import get_stock_filter_layout, register_callbacks
from mini_stock.market_data_client import MarketDataClient


class Dashboard:
    def __init__(self, market_data_url=None):
        self.client = MarketDataClient(market_data_url)
        self.latest_df = pd.DataFrame(columns=pd.Index(['股票名', '最新价', '涨幅', '涨跌额']))
        self.alerts_data = []
        self.alert_stats = {}
        self.futures_alerts_data = []  # 股指期货异常数据
        self.futures_alert_stats = {}  # 股指期货异常统计
        self.running = True
        
        # 启动数据更新线程
        self.update_thread = threading.Thread(target=self._update_data, daemon=True)
        self.update_thread.start()
        
    def _update_data(self):
        """后台更新数据"""
        while self.running:
            try:
                # 获取数据
                kline_data = self.client.fetch_data()
                preclose_dict = self.client.fetch_preclose()
                code_list = self.client.fetch_stock_list()
                alerts_data = self.client.fetch_alerts()
                alert_stats = self.client.fetch_alert_stats()
                
                # 获取股指期货异常数据
                futures_alerts_data = self.client.fetch_futures_alerts()
                futures_alert_stats = self.client.fetch_futures_alert_stats()
                
                # 处理股票数据
                snap_list = []
                for idx, code in enumerate(code_list, 1):
                    kline = kline_data.get(code)
                    if not kline:  # 判断list是否为空
                        continue
                    k = kline[-1]
                    lastPrice = k.get("lastPrice", None)
                    # 非交易时段，上层service调用的接口不同，返回的字段略有不同，这里做个处理，后期如果发现问题再说
                    if lastPrice is None:
                        lastPrice = k.get("close", None)

                    preclose = preclose_dict.get(code)
                    if lastPrice is not None and preclose is not None:
                        chg = round(lastPrice - preclose, 2)
                        pct = round((lastPrice - preclose) / preclose * 100, 2)
                        pct_str = f"{pct}%"
                        snap_list.append({
                            '序号': idx,
                            '股票名': code,  # 你可以用真实名称替换
                            '最新价': round(lastPrice, 2),
                            '涨幅': pct,  # 用数字，便于排序筛选
                            '涨跌额': chg
                        })
                
                # 更新DataFrame
                self.latest_df = pd.DataFrame(snap_list)
                
                # 更新异常数据
                self.alerts_data = alerts_data
                self.alert_stats = alert_stats
                self.futures_alerts_data = futures_alerts_data
                self.futures_alert_stats = futures_alert_stats
                
                logging.info(f"[dash board]数据更新成功，共{len(snap_list)}条记录，{len(alerts_data)}条股票异常，{len(futures_alerts_data)}条股指异常")
                
            except Exception as e:
                logging.error(f"更新数据失败: {e}")
                
            time.sleep(3)  # 3秒更新一次
            
    def create_app(self):
        """创建Dash应用"""
        app = dash.Dash(__name__,
                       assets_folder='static',
                       serve_locally=True)

        # 使用外部HTML模板
        with open('templates/base.html', 'r', encoding='utf-8') as f:
            app.index_string = f.read()

        # 主应用布局
        app.layout = html.Div([
            # 左侧导航栏
            html.Div([
                html.H3("股票监控系统", className="text-center mb-4 text-white"),
                html.Div([
                    html.Button(
                        "📊 实时监控",
                        id="nav-dashboard",
                        className="nav-button active"
                    ),
                    html.Button(
                        "📈 股指监控",
                        id="nav-index-dashboard",
                        className="nav-button"
                    ),
                    html.Button(
                        "🔍 股票筛选",
                        id="nav-stock-filter",
                        className="nav-button"
                    )
                ], className="padding-20")
            ], className="sidebar"),

            # 右侧内容区域
            html.Div([
                html.Div(id="page-content", className="padding-20-content")
            ], className="content-area")
        ], className="flex-container")

        # 页面路由回调
        @app.callback(
            [Output("page-content", "children"),
             Output("nav-dashboard", "className"),
             Output("nav-index-dashboard", "className"),
             Output("nav-stock-filter", "className")],
            [Input("nav-dashboard", "n_clicks"),
             Input("nav-index-dashboard", "n_clicks"),
             Input("nav-stock-filter", "n_clicks")]
        )
        def render_page(dashboard_clicks, index_clicks, filter_clicks):
            ctx = dash.callback_context
            if not ctx.triggered:
                # 默认显示仪表板
                return get_dashboard_layout(), "nav-button active", "nav-button", "nav-button"

            button_id = ctx.triggered[0]['prop_id'].split('.')[0]

            if button_id == "nav-dashboard":
                return get_dashboard_layout(), "nav-button active", "nav-button", "nav-button"
            elif button_id == "nav-index-dashboard":
                return get_index_dashboard_layout(), "nav-button", "nav-button active", "nav-button"
            elif button_id == "nav-stock-filter":
                return get_stock_filter_layout(), "nav-button", "nav-button", "nav-button active"
            else:
                return get_dashboard_layout(), "nav-button active", "nav-button", "nav-button"

        # 仪表板回调
        @app.callback(
            [Output('live-table', 'data'),
             Output('last-update-time', 'children')],
            Input('interval', 'n_intervals')
        )
        def update_table(n):
            return self.latest_df.to_dict('records'), DateUtils.now().strftime("%Y-%m-%d %H:%M:%S")

        # 合并异常统计回调，避免重复 Output
        @app.callback(
            [Output('today-alerts-count', 'children'),
             Output('alert-type-stats', 'children')],
            [Input('interval', 'n_intervals'),
             Input('index-interval', 'n_intervals')]
        )
        def update_alert_stats(stock_n, index_n):
            ctx = dash.callback_context
            if not ctx.triggered:
                return 0, []
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
            if trigger_id == 'interval':
                today_count = self.alert_stats.get('today_alerts', 0)
                by_type = self.alert_stats.get('by_type', {})
                type_items = []
                for alert_type, count in by_type.items():
                    type_items.append(html.Div(f"{alert_type}: {count}", style={'margin': '2px 0'}))
                return today_count, type_items
            elif trigger_id == 'index-interval':
                # 股指异常统计逻辑
                today_count = self.futures_alert_stats.get('today_alerts', 0)
                by_type = self.futures_alert_stats.get('by_type', {})
                type_items = []
                for alert_type, count in by_type.items():
                    type_items.append(html.Div(f"{alert_type}: {count}", style={'margin': '2px 0'}))
                return today_count, type_items
            return 0, []

        # 合并异常提示回调，避免重复 Output
        @app.callback(
            Output('alerts-list', 'children'),
            [Input('interval', 'n_intervals'),
             Input('index-interval', 'n_intervals')]
        )
        def update_alerts_list(stock_n, index_n):
            ctx = dash.callback_context
            if not ctx.triggered:
                return html.Div("暂无异常提示", style={'color': '#666', 'textAlign': 'center'})
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
            if trigger_id == 'interval':
                # 股票异常提示逻辑
                if not self.alerts_data:
                    return html.Div("暂无异常提示", style={'color': '#666', 'textAlign': 'center'})
                sorted_alerts = sorted(self.alerts_data, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]
                alert_items = []
                for alert in sorted_alerts:
                    level_colors = {
                        '低': '#17a2b8',
                        '中': '#ffc107', 
                        '高': '#dc3545',
                        '紧急': '#dc3545'
                    }
                    color = level_colors.get(alert.get('level', '中'), '#17a2b8')
                    timestamp = alert.get('timestamp', '')
                    if timestamp:
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            time_str = dt.strftime('%H:%M:%S')
                        except:
                            time_str = timestamp
                    else:
                        time_str = '未知'
                    alert_div = html.Div([
                        html.Div(alert.get('message', ''), style={
                            'fontWeight': 'bold',
                            'color': color,
                            'marginBottom': '5px'
                        }),
                        html.Div([
                            f"类型: {alert.get('alert_type', '')} | ",
                            f"级别: {alert.get('level', '')} | ",
                            f"时间: {time_str}"
                        ], style={
                            'fontSize': '11px',
                            'color': '#666'
                        })
                    ], style={
                        'padding': '8px',
                        'margin': '5px 0',
                        'border': f'1px solid {color}',
                        'borderRadius': '3px',
                        'backgroundColor': '#fff'
                    })
                    alert_items.append(alert_div)
                return alert_items
            elif trigger_id == 'index-interval':
                # 股指异常提示逻辑
                if not self.futures_alerts_data:
                    return html.Div("暂无异常提示", style={'color': '#666', 'textAlign': 'center'})
                sorted_alerts = sorted(self.futures_alerts_data, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]
                alert_items = []
                for alert in sorted_alerts:
                    level_colors = {
                        '低': '#17a2b8',
                        '中': '#ffc107', 
                        '高': '#dc3545',
                        '紧急': '#dc3545'
                    }
                    color = level_colors.get(alert.get('level', '中'), '#17a2b8')
                    timestamp = alert.get('timestamp', '')
                    if timestamp:
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            time_str = dt.strftime('%H:%M:%S')
                        except:
                            time_str = timestamp
                    else:
                        time_str = '未知'
                    alert_div = html.Div([
                        html.Div(alert.get('message', ''), style={
                            'fontWeight': 'bold',
                            'color': color,
                            'marginBottom': '5px'
                        }),
                        html.Div([
                            f"类型: {alert.get('alert_type', '')} | ",
                            f"级别: {alert.get('level', '')} | ",
                            f"时间: {time_str}"
                        ], style={
                            'fontSize': '11px',
                            'color': '#666'
                        })
                    ], style={
                        'padding': '8px',
                        'margin': '5px 0',
                        'border': f'1px solid {color}',
                        'borderRadius': '3px',
                        'backgroundColor': '#fff'
                    })
                    alert_items.append(alert_div)
                return alert_items
            return html.Div("暂无异常提示", style={'color': '#666', 'textAlign': 'center'})

        # 导入数据处理模块
        from mini_stock.futures_data_processor import process_futures_market_data

        # 股指监控数据回调
        @app.callback(
            [Output('index-live-table', 'data'),
             Output('index-last-update-time', 'children')],
            Input('index-interval', 'n_intervals')
        )
        def update_index_table(n):
            # 使用专门的数据处理函数
            return process_futures_market_data()

        @app.callback(
            Output('upload-status', 'children'),
            Input('upload-stock-list', 'contents'),
            State('upload-stock-list', 'filename')
        )
        def update_stock_list(contents, filename):
            if contents is None:
                return ''
            
            try:
                # 解码文件内容
                content_type, content_string = contents.split(',')
                decoded = base64.b64decode(content_string)
                
                # 上传文件
                success, message = self.client.upload_stock_list(decoded, filename)
                
                if success:
                    return html.Div(message, className="status-success")
                else:
                    return html.Div(message, className="status-error")
                    
            except Exception as e:
                return html.Div(f'处理文件时出错: {str(e)}', className="status-error")

        # 注册股票筛选页面回调
        register_callbacks(app)

        return app
        
    def run(self, host='0.0.0.0', port=8051):
        """运行仪表板"""
        app = self.create_app()
        app.run(debug=False, host=host, port=port)
        
    def stop(self):
        """停止仪表板"""
        self.running = False
        self.update_thread.join()


if __name__ == "__main__":
    # 创建并运行仪表板
    dashboard = Dashboard()
    try:
        dashboard.run()
    except KeyboardInterrupt:
        dashboard.stop() 
