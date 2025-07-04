import os
import pandas as pd
from dash import Input, Output, State, callback_context, dcc, html, dash_table
from dash.exceptions import PreventUpdate
import requests
import environment
import json
from datetime import datetime
import base64
import io


def get_stock_filter_layout():
    """股票筛选页面布局"""
    return html.Div([
        html.H1("股票筛选器", className="text-center mb-4"),

        html.Div([
            # 左侧筛选条件
            html.Div([
                html.Div([
                    html.Label("筛选个数", className="form-label"),
                    dcc.Input(
                        id="count-input",
                        type="number",
                        min=1,
                        max=300,
                        value=20,
                        className="form-control"
                    )
                ], className="mb-3"),

                html.Div([
                    html.Label("筛选条件", className="form-label"),
                    dcc.Checklist(
                        id="conditions-checklist",
                        options=[
                            {"label": "按市值升序", "value": "按市值升序"},
                            {"label": "按市值降序", "value": "按市值降序"},
                            {"label": "排除ST", "value": "排除ST"},
                            {"label": "排除退市", "value": "排除退市"},
                            {"label": "上交所", "value": "上交所"},
                            {"label": "深交所", "value": "深交所"},
                            {"label": "创业板", "value": "创业板"},
                            {"label": "科创板", "value": "科创板"}
                        ],
                        value=["按市值降序", "排除ST", "排除退市"],
                        className="form-check"
                    )
                ], className="mb-3"),

                html.Button("筛选股票", id="filter-button", className="btn btn-primary"),

                html.Div([
                    html.Button("导出CSV", id="export-csv-button", className="btn btn-success me-2"),
                    html.Button("导出Excel", id="export-excel-button", className="btn btn-warning")
                ], className="mt-3")

            ], className="col-md-6"),

            # 右侧结果显示
            html.Div([
                html.Div(id="loading-div", style={"display": "none"}, children=[
                    html.Div(className="spinner-border text-primary", role="status"),
                    html.Span("正在筛选股票...", className="ms-2")
                ]),

                html.Div(id="result-info", className="alert alert-info", style={"display": "none"}),
                html.Div(id="error-info", className="alert alert-danger", style={"display": "none"})

            ], className="col-md-6")

        ], className="row"),

        # 结果表格
        html.Div(id="result-table-container", style={"display": "none"}, children=[
            dash_table.DataTable(
                id="result-table",
                columns=[],
                data=[],
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "center"},
                style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"}
            )
        ]),

        # 隐藏的存储组件
        dcc.Store(id="filtered-data-store"),
        dcc.Store(id="export-data-store")

    ], className="container mt-4")


def get_stocks_from_service(min_listed_days=90, exclude_st=True, exclude_delisted=True,
                            exclude_limit_up=True, exclude_suspended=True):
    """从市场数据服务获取股票列表"""
    try:
        market_data_url = f"http://{environment.STOCK_MARKET_SERVICE_HOST}:5000"
        params = {
            'min_listed_days': min_listed_days,
            'exclude_st': str(exclude_st).lower(),
            'exclude_delisted': str(exclude_delisted).lower(),
            'exclude_limit_up': str(exclude_limit_up).lower(),
            'exclude_suspended': str(exclude_suspended).lower()
        }
        response = requests.get(f"{market_data_url}/filtered_stocks", params=params)
        if response.status_code == 200:
            data = response.json()
            return pd.DataFrame(data)
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"连接市场数据服务失败: {str(e)}")
        return pd.DataFrame()


def register_callbacks(app):
    """注册回调函数"""

    @app.callback(
        [Output("result-table", "columns"),
         Output("result-table", "data"),
         Output("result-info", "children"),
         Output("result-info", "style"),
         Output("error-info", "children"),
         Output("error-info", "style"),
         Output("result-table-container", "style"),
         Output("filtered-data-store", "data"),
         Output("loading-div", "style")],
        [Input("filter-button", "n_clicks")],
        [State("count-input", "value"),
         State("conditions-checklist", "value")]
    )
    def filter_stocks(n_clicks, count, conditions):
        if n_clicks is None:
            return [], [], "", {"display": "none"}, "", {"display": "none"}, {"display": "none"}, None, {
                "display": "none"}

        # 显示加载状态
        loading_style = {"display": "block"}

        try:
            # 筛选条件
            exclude_st = "排除ST" in conditions
            exclude_delisted = "排除退市" in conditions

            # 获取股票数据
            all_stocks = get_stocks_from_service(
                exclude_st=exclude_st,
                exclude_delisted=exclude_delisted
            )

            if all_stocks.empty:
                return [], [], "", {"display": "none"}, "没有获取到股票数据，请检查市场数据服务是否正在运行", {
                    "display": "block"}, {"display": "none"}, None, {"display": "none"}

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

            # 准备表格数据
            columns = [{"name": col, "id": col} for col in filtered.columns]
            data = filtered.to_dict('records')

            # 存储数据用于导出
            store_data = filtered.to_dict('records')

            return (columns, data,
                    f"找到 {len(filtered)} 只符合条件的股票",
                    {"display": "block"},
                    "", {"display": "none"},
                    {"display": "block"},
                    store_data,
                    {"display": "none"})

        except Exception as e:
            return [], [], "", {"display": "none"}, f"筛选失败: {str(e)}", {"display": "block"}, {
                "display": "none"}, None, {"display": "none"}

    @app.callback(
        Output("export-data-store", "data"),
        [Input("export-csv-button", "n_clicks"),
         Input("export-excel-button", "n_clicks")],
        [State("filtered-data-store", "data")]
    )
    def export_data(csv_clicks, excel_clicks, filtered_data):
        if not filtered_data:
            return None

        ctx = callback_context
        if not ctx.triggered:
            return None

        button_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if button_id == "export-csv-button":
            # 导出CSV
            df = pd.DataFrame(filtered_data)
            csv_string = df.to_csv(index=False, encoding='utf-8-sig')
            return {
                'type': 'csv',
                'data': csv_string,
                'filename': f"filtered_stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        elif button_id == "export-excel-button":
            # 导出Excel
            df = pd.DataFrame(filtered_data)
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False)
            excel_data = excel_buffer.getvalue()
            return {
                'type': 'excel',
                'data': base64.b64encode(excel_data).decode(),
                'filename': f"filtered_stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            }

        return None
