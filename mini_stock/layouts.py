from dash import dcc, html, dash_table

# 样式常量
UPLOAD_STYLE = {
    'width': '100%',
    'height': '60px',
    'lineHeight': '60px',
    'borderWidth': '1px',
    'borderStyle': 'dashed',
    'borderRadius': '5px',
    'textAlign': 'center',
    'margin': '10px 0'
}
CONTAINER_STYLE = {'maxWidth': '900px', 'margin': '0 auto'}
HEADER_STYLE = {'fontWeight': 'bold', 'fontSize': 18}
CELL_STYLE = {'fontSize': 16, 'textAlign': 'center'}


def get_header():
    return html.H2("小市值成分股实时监控")


def get_last_update_info():
    return html.Div([
        html.Span("最后更新: "),
        html.Span(id='last-update-time')
    ], style={'marginBottom': '10px'})


def get_upload_area():
    return html.Div([
        dcc.Upload(
            id='upload-stock-list',
            children=html.Div(['拖放或 ', html.A('选择股票列表文件')]),
            style=UPLOAD_STYLE,
            multiple=False
        ),
        html.Div(id='upload-status', style={'margin': '10px 0'})
    ], style=CONTAINER_STYLE)


def get_data_table():
    return html.Div([
        dash_table.DataTable(
            id='live-table',
            columns=[
                {'name': '序号', 'id': '序号', 'type': 'numeric'},
                {'name': '股票名', 'id': '股票名'},
                {'name': '最新价', 'id': '最新价', 'type': 'numeric'},
                {'name': '涨幅', 'id': '涨幅', 'type': 'numeric',
                 'format': {'specifier': '.2f', 'locale': {'symbol': ['', '%']}}},
                {'name': '涨跌额', 'id': '涨跌额', 'type': 'numeric'},
            ],
            style_data_conditional=[
                {'if': {'filter_query': '{涨跌额} > 0', 'column_id': '涨跌额'}, 'color': 'red'},
                {'if': {'filter_query': '{涨跌额} < 0', 'column_id': '涨跌额'}, 'color': 'green'},
                {'if': {'filter_query': '{涨幅} > 0', 'column_id': '涨幅'}, 'color': 'red'},
                {'if': {'filter_query': '{涨幅} < 0', 'column_id': '涨幅'}, 'color': 'green'},
            ],
            style_cell=CELL_STYLE,
            style_header=HEADER_STYLE,
            sort_action='native',
            filter_action='native',
        )
    ], style=CONTAINER_STYLE)


def get_alert_stats():
    """获取异常统计区域"""
    return html.Div([
        html.H4("异常统计", style={'marginBottom': '10px', 'color': '#333'}),
        html.Div([
            html.Div([
                html.H5(id='today-alerts-count', style={'color': '#dc3545', 'margin': '0'}),
                html.P("今日异常", style={'margin': '0', 'fontSize': '12px'})
            ], style={'textAlign': 'center', 'padding': '10px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px'})
        ], style={'marginBottom': '15px'}),
        html.Div(id='alert-type-stats', style={'fontSize': '12px'})
    ])


def get_alerts_panel():
    """获取异常提示面板"""
    return html.Div([
        html.H4("实时提示", style={'marginBottom': '10px', 'color': '#333'}),
        html.Div(id='alerts-list', style={
            'maxHeight': '400px', 
            'overflowY': 'auto',
            'border': '1px solid #ddd',
            'borderRadius': '5px',
            'padding': '10px',
            'backgroundColor': '#f8f9fa'
        })
    ])


def get_dashboard_layout():
    return html.Div([
        get_header(),
        get_last_update_info(),
        get_upload_area(),
        dcc.Interval(id='interval', interval=3 * 1000, n_intervals=0),
        
        # 主要内容区域 - 左右分栏
        html.Div([
            # 左侧：小市值成分股实时监控
            html.Div([
                html.H3("股票数据", style={'marginBottom': '15px', 'color': '#333'}),
                get_data_table()
            ], style={'width': '65%', 'verticalAlign': 'top', 'paddingRight': '20px'}),
            
            # 右侧：实时提示
            html.Div([
                get_alert_stats(),
                html.Hr(style={'margin': '20px 0'}),
                get_alerts_panel()
            ], style={'width': '35%', 'verticalAlign': 'top'})
        ], style={'marginTop': '20px', 'display': 'flex'})
    ])


# 股票筛选器页面布局

def get_stock_filter_layout():
    return html.Div([
        html.H2("股票筛选器"),
        html.Div([
            html.Label("筛选个数："),
            dcc.Input(id='filter-count', type='number', min=1, step=1, value=20, style={'width': '100px'}),
        ], style={'margin': '10px 0'}),
        html.Div([
            html.Label("筛选条件："),
            dcc.Checklist(
                id='filter-conditions',
                options=[
                    {'label': '按市值升序', 'value': 'marketcap_asc'},
                    {'label': '按市值降序', 'value': 'marketcap_desc'},
                    {'label': '排除ST', 'value': 'no_st'},
                    {'label': '排除退市', 'value': 'no_delist'},
                    {'label': '上交所', 'value': 'sh'},
                    {'label': '深交所', 'value': 'sz'},
                    {'label': '创业板', 'value': 'cyb'},
                    {'label': '科创板', 'value': 'kcb'},
                ],
                value=['marketcap_desc', 'no_st', 'no_delist'],
                inline=True
            ),
        ], style={'margin': '10px 0'}),
        html.Button('筛选', id='do-filter', n_clicks=0, style={'marginRight': '20px'}),
        html.Button('导出为TXT', id='export-txt', n_clicks=0, style={'marginRight': '10px'}),
        html.Button('导出为CSV', id='export-csv', n_clicks=0, style={'marginRight': '10px'}),
        html.Button('导出为XLS', id='export-xls', n_clicks=0),
        html.Div(id='filter-export-status', style={'margin': '10px 0', 'color': 'green'}),
        dash_table.DataTable(
            id='filter-result-table',
            columns=[
                {'name': '股票代码', 'id': 'code'},
                {'name': '股票名称', 'id': 'name'},
                {'name': '市值(亿)', 'id': 'marketcap'},
                {'name': '是否ST', 'id': 'is_st'},
                {'name': '是否退市', 'id': 'is_delist'},
                {'name': '市场', 'id': 'market'},
            ],
            data=[],
            page_size=20,
            style_cell={'fontSize': 16, 'textAlign': 'center'},
            style_header={'fontWeight': 'bold', 'fontSize': 18},
        )
    ], style={'maxWidth': '1000px', 'margin': '0 auto'})


def get_index_data_table():
    """获取股指数据表格"""
    return html.Div([
        dash_table.DataTable(
            id='index-live-table',
            columns=[
                {'name': '序号', 'id': '序号', 'type': 'numeric'},
                {'name': '合约代码', 'id': '合约代码'},
                {'name': '名称', 'id': '名称'},
                {'name': '最新价', 'id': '最新价', 'type': 'numeric',
                 'format': {'specifier': '.2f'}},
                {'name': '涨幅', 'id': '涨幅', 'type': 'numeric',
                 'format': {'specifier': '.2f', 'locale': {'symbol': ['', '%']}}},
                {'name': '涨跌额', 'id': '涨跌额', 'type': 'numeric',
                 'format': {'specifier': '.2f'}},
                {'name': '成交量', 'id': '成交量', 'type': 'numeric',
                 'format': {'specifier': '.0f'}},
                {'name': '持仓量', 'id': '持仓量', 'type': 'numeric',
                 'format': {'specifier': '.0f'}},
            ],
            style_data_conditional=[
                {'if': {'filter_query': '{涨跌额} > 0', 'column_id': '涨跌额'}, 'color': 'red'},
                {'if': {'filter_query': '{涨跌额} < 0', 'column_id': '涨跌额'}, 'color': 'green'},
                {'if': {'filter_query': '{涨幅} > 0', 'column_id': '涨幅'}, 'color': 'red'},
                {'if': {'filter_query': '{涨幅} < 0', 'column_id': '涨幅'}, 'color': 'green'},
            ],
            style_cell=CELL_STYLE,
            style_header=HEADER_STYLE,
            sort_action='native',
            filter_action='native',
        )
    ], style=CONTAINER_STYLE)


def get_index_header():
    return html.H2("股指实时监控")


def get_index_last_update_info():
    return html.Div([
        html.Span("最后更新: "),
        html.Span(id='index-last-update-time')
    ], style={'marginBottom': '10px'})


def get_index_dashboard_layout():
    return html.Div([
        get_index_header(),
        get_index_last_update_info(),
        dcc.Interval(id='index-interval', interval=3 * 1000, n_intervals=0),
        
        # 主要内容区域 - 左右分栏
        html.Div([
            # 左侧：股指实时监控
            html.Div([
                html.H3("股指数据", style={'marginBottom': '15px', 'color': '#333'}),
                get_index_data_table()
            ], style={'width': '65%', 'verticalAlign': 'top', 'paddingRight': '20px'}),
            
            # 右侧：实时提示
            html.Div([
                get_alert_stats(),
                html.Hr(style={'margin': '20px 0'}),
                get_alerts_panel()
            ], style={'width': '35%', 'verticalAlign': 'top'})
        ], style={'marginTop': '20px', 'display': 'flex'})
    ])
