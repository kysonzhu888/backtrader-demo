import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import os
import time
from datetime import datetime, timedelta
from flask_caching import Cache
import pytz
import numpy as np

# 创建Dash应用
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
server = app.server
app.title = "黄金期货数据可视化"

# 配置缓存 - 文件系统缓存
cache = Cache(
    app.server,
    config={
        'CACHE_TYPE': 'filesystem',
        'CACHE_DIR': './app_cache',  # 创建新目录避免冲突
        'CACHE_THRESHOLD': 1000
    }
)

# 缓存超时时间 (秒)
CACHE_TIMEOUT = 60 * 10  # 10分钟

# 统一的时间列名
TIME_COLUMN = 'datetime'

# 应用布局
app.layout = dbc.Container([
    # 标题
    dbc.Row(
        dbc.Col(
            html.H1("黄金期货数据分析", className="text-center my-4"),
            width=12
        )
    ),

    # 控制面板
    dbc.Row([
        # 时间周期选择
        dbc.Col(
            dcc.RadioItems(
                id='resolution-selector',
                options=[
                    {'label': '1分钟', 'value': '1min'},
                    {'label': '5分钟', 'value': '5min'},
                    {'label': '15分钟', 'value': '15min'},
                    {'label': '30分钟', 'value': '30min'},
                    {'label': '1小时', 'value': '1H'},
                    {'label': '4小时', 'value': '4H'},
                    {'label': '日线', 'value': '1D'}
                ],
                value='30min',
                inline=True,
                className="mb-3"
            ),
            width=8
        ),

        # 显示范围控制
        dbc.Col(
            dcc.Dropdown(
                id='time-range',
                options=[
                    {'label': '最近1天', 'value': '1D'},
                    {'label': '最近1周', 'value': '7D'},
                    {'label': '最近1月', 'value': '30D'},
                    {'label': '最近3月', 'value': '90D'},
                    {'label': '最近1年', 'value': '365D'},
                    {'label': '自定义', 'value': 'custom'}
                ],
                value='90D',
                clearable=False,
                className="mb-3"
            ),
            width=4
        ),
    ]),

    # 自定义日期范围选择器 (默认隐藏)
    dbc.Row(
        dbc.Col(
            dcc.DatePickerRange(
                id='date-range-picker',
                min_date_allowed=datetime(2013, 1, 1),
                max_date_allowed=datetime.today(),
                start_date=datetime.today() - timedelta(days=90),
                end_date=datetime.today(),
                display_format='YYYY-MM-DD',
                className="mb-3",
                style={'display': 'none'}  # 默认隐藏
            ),
            width=12
        ),
        id='custom-date-row',
        style={'display': 'none'}  # 默认隐藏
    ),

    # 图表区域
    dbc.Row(
        dbc.Col(
            dcc.Graph(
                id='candle-chart',
                config={'scrollZoom': True},
                style={'height': '70vh'}
            ),
            width=12
        )
    ),

    # 性能信息
    dbc.Row(
        dbc.Col(
            html.Div(id='performance-info', className="text-center mt-2 text-muted"),
            width=12
        )
    ),

    # 调试信息
    dbc.Row(
        dbc.Col(
            html.Div(id='debug-info', style={'whiteSpace': 'pre-line'}),
            width=12
        )
    ),

    # 隐藏的存储组件
    dcc.Store(id='last-resolution'),
    dcc.Interval(id='update-interval', interval=60000, n_intervals=0)  # 每分钟检查更新
], fluid=True)


# 显示/隐藏自定义日期选择器
@app.callback(
    Output('custom-date-row', 'style'),
    Input('time-range', 'value')
)
def show_custom_date_selector(selected_range):
    """当选择自定义范围时显示日期选择器"""
    if selected_range == 'custom':
        return {'display': 'block'}
    return {'display': 'none'}


# 加载数据函数 - 带缓存
@cache.memoize(timeout=CACHE_TIMEOUT)
def load_data(resolution, start_date, end_date):
    """按需加载特定范围的数据"""
    debug_info = []
    start_time = time.time()

    debug_info.append(f"加载数据 - 分辨率: {resolution}, 开始日期: {start_date}, 结束日期: {end_date}")

    # 确定年份范围
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    start_year = start_dt.year
    end_year = end_dt.year

    # 加载所有相关年份数据
    dfs = []
    for year in range(start_year, end_year + 1):
        file_path = f"cache/{resolution}/{year}.parquet"
        if os.path.exists(file_path):
            try:
                year_df = pd.read_parquet(file_path)

                # 统一列名 - 确保datetime列存在
                if 'datetime' not in year_df.columns and 'date' in year_df.columns:
                    year_df.rename(columns={'date': 'datetime'}, inplace=True)

                dfs.append(year_df)
                debug_info.append(f"从 {file_path} 加载 {len(year_df)} 条记录")
            except Exception as e:
                debug_info.append(f"加载 {file_path} 出错: {str(e)}")

    if not dfs:
        debug_info.append(f"未找到数据: cache/{resolution}/ 中没有 {start_year}-{end_year} 年的数据")
        return pd.DataFrame(), "\n".join(debug_info)

    # 合并数据
    df = pd.concat(dfs, ignore_index=True)
    debug_info.append(f"合并后数据总数: {len(df)} 条记录")

    # 确保时间列存在并处理
    if TIME_COLUMN not in df.columns:
        debug_info.append(f"错误: 数据中缺少时间列。现有列: {df.columns.tolist()}")
        return pd.DataFrame(), "\n".join(debug_info)

    # 时间列转换
    if not pd.api.types.is_datetime64_any_dtype(df[TIME_COLUMN]):
        try:
            df[TIME_COLUMN] = pd.to_datetime(df[TIME_COLUMN])
            debug_info.append("时间列已转换为datetime类型")
        except Exception as e:
            debug_info.append(f"时间列转换失败: {str(e)}")
            return pd.DataFrame(), "\n".join(debug_info)

    # 筛选日期范围
    df = df[(df[TIME_COLUMN] >= start_dt) & (df[TIME_COLUMN] <= end_dt)]
    debug_info.append(f"筛选后数据: {len(df)} 条记录")

    # 如果数据量太大，自动降采样
    if len(df) > 5000:
        factor = max(1, int(len(df) / 5000))
        df = df.iloc[::factor, :]
        debug_info.append(f"自动降采样: 保留 {len(df)} 条记录 (因子: {factor})")

    # 性能信息
    load_time = time.time() - start_time
    debug_info.append(f"数据加载耗时: {load_time:.3f}秒")

    return df, "\n".join(debug_info)


# 主回调函数 - 更新图表
@app.callback(
    [Output('candle-chart', 'figure'),
     Output('performance-info', 'children'),
     Output('debug-info', 'children'),
     Output('date-range-picker', 'start_date'),
     Output('date-range-picker', 'end_date'),
     Output('date-range-picker', 'min_date_allowed'),
     Output('date-range-picker', 'max_date_allowed')],
    [Input('resolution-selector', 'value'),
     Input('time-range', 'value'),
     Input('date-range-picker', 'start_date'),
     Input('date-range-picker', 'end_date'),
     Input('update-interval', 'n_intervals')],
    prevent_initial_call=False
)
def update_candle_chart(resolution, time_range, start_date, end_date, n_intervals):
    debug_info = ["开始更新图表..."]

    # 根据显示范围选项确定日期范围
    today = datetime.now(pytz.timezone('Asia/Shanghai'))
    end_date_actual = today

    if time_range == 'custom':
        start_date_actual = start_date
    else:
        days = int(time_range.replace('D', ''))
        start_date_actual = (today - timedelta(days=days)).isoformat()
        end_date_actual = today.isoformat()

    # 加载数据
    debug_info.append(f"加载数据: resolution={resolution}, start={start_date_actual}, end={end_date_actual}")

    try:
        df, load_debug = load_data(resolution, start_date_actual, end_date_actual)
        debug_info.append(load_debug)
    except Exception as e:
        debug_info.append(f"加载数据出错: {str(e)}")
        return (
            go.Figure(),
            "数据加载失败",
            "\n".join(debug_info),
            start_date_actual,
            end_date_actual,
            datetime(2013, 1, 1),
            today
        )

    if df.empty:
        debug_info.append("数据为空")
        return (
            go.Figure(),
            "没有数据",
            "\n".join(debug_info),
            start_date_actual,
            end_date_actual,
            datetime(2013, 1, 1),
            today
        )

    # 创建K线图
    debug_info.append("创建蜡烛图...")
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df[TIME_COLUMN],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='K线',
                increasing_line_color='#2ECC71',
                decreasing_line_color='#E74C3C'
            )
        ]
    )

    # 添加简单移动平均线
    debug_info.append("添加技术指标...")
    if 'MA20' in df.columns:
        fig.add_trace(go.Scatter(
            x=df[TIME_COLUMN],
            y=df['MA20'],
            mode='lines',
            name='MA20',
            line=dict(color='#F1C40F', width=1.5)
        ))

    if 'MA50' in df.columns:
        fig.add_trace(go.Scatter(
            x=df[TIME_COLUMN],
            y=df['MA50'],
            mode='lines',
            name='MA50',
            line=dict(color='#3498DB', width=1.5)
        ))

    # 图表布局设置
    debug_info.append("设置图表布局...")
    fig.update_layout(
        title=f'黄金期货 {resolution} K线图',
        xaxis_title='时间',
        yaxis_title='价格',
        template='plotly_dark',
        height=700,
        xaxis_rangeslider_visible=True,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=40, r=40, t=60, b=40),
        hovermode="x unified"
    )

    # 日期范围控件设置
    min_date_allowed = df[TIME_COLUMN].min().to_pydatetime()
    max_date_allowed = df[TIME_COLUMN].max().to_pydatetime()

    # 性能信息
    info = f"显示 {len(df)} 条记录 | 时间范围: {min_date_allowed.strftime('%Y-%m-%d')} 至 {max_date_allowed.strftime('%Y-%m-%d')} | 分辨率: {resolution}"

    debug_info.append("图表更新完成")
    return (
        fig,
        info,
        "\n".join(debug_info),
        start_date_actual,
        end_date_actual,
        min_date_allowed,
        max_date_allowed
    )


# 运行应用
if __name__ == '__main__':
    # 创建本地目录（如果不存在）
    os.makedirs("app_cache", exist_ok=True)
    os.makedirs("cache", exist_ok=True)

    print("启动Dash应用...")
    print("访问地址: http://localhost:8050")
    app.run(debug=True, port=8050, threaded=True)