import logging

import environment
import os

from dash import Dash, dcc, html, Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import pandas as pd
import numpy as np
from power_wave import PowerWave

from back_trace_paradigm import HistoricalDataLoader

app = Dash(external_stylesheets=[dbc.themes.CYBORG])


def create_dropdown(option, id_value):
    return html.Div(
        [
            html.H4(id_value),
            dcc.Dropdown(option,
                         id=id_value,
                         value=option[0],
                         style={
                             "width": "200px",
                             "margin": "auto",
                             "padding": "10px, 30px, 10px, 30px"
                            }
                         )
        ]
    )

if os.getenv('DEBUG_MODE') == '1':
    fresh_interval = 2000
else:
    fresh_interval = 20000

app.layout = html.Div([

    html.Div([
        create_dropdown(["AU"], "feature-select"),
        create_dropdown(["200","500","1000"], "num-bars-select"),
        ], style={"display": "flex",
              "margin": "auto",
              "width": "50%",
              "justify-content": "space-around"
            }
    ),

    dcc.Graph(id="candles"),
    dcc.Graph(id="powerwave", style={"height": "250px"}),

    # 创建一个定时器组件，用于定期触发数据更新
    # - id="interval"：组件的唯一标识符，供Dash回调引用
    # - interval=20000：设置定时器间隔为20000毫秒（即20秒），每20秒自动触发一次回调
    # 这个组件的主要作用是实现数据的自动刷新，让图表能够定期更新最新数据
    # 在回调函数中，可以通过Input("interval", "n_intervals")来获取定时器触发的次数

    dcc.Interval(id="interval", interval=fresh_interval),
])


@app.callback(
    Output("candles", "figure"),
    Input("interval", "n_intervals"),
    Input("feature-select", "value"),
    Input("num-bars-select", "value"),
)
def update_figure(n_intervals, feature_type, num_bars):
    end_time = environment.debug_latest_candle_time if os.getenv('DEBUG_MODE') == '1' else None
    data_window = HistoricalDataLoader.load_historical_data(product_type=feature_type,
                                                           interval=n_intervals, end_time=end_time)
    # 去重，保留最新一条
    data_window = data_window[~data_window.index.duplicated(keep='last')]

    # 取最新num_bars根K线
    if num_bars is None:
        num_bars = 100
    m_data = data_window.iloc[-int(num_bars):]

    # 统一x轴
    data = m_data.iloc[34:]
    data = data[~data.index.duplicated(keep='last')]
    data = data.sort_index()
    x = data.index.astype(str)  # 主副图都用这个x

    # 计算动力波相关数据
    pw = PowerWave()
    pw.update(m_data)
    vard = pw.vard.loc[data.index]
    vare = pw.vare.loc[data.index]
    life = vare.ewm(span=10, adjust=False).mean()
    diff = vard - vare
    bar_colors = np.where(diff > 0, "red", "#00FF0F")
    bar_base = np.minimum(vard, vare)
    bar_height = np.abs(diff)
    valid_mask = ~np.isnan(bar_height)
    filtered_x = x[valid_mask]
    filtered_bar_height = bar_height[valid_mask]
    filtered_bar_base = bar_base[valid_mask]
    filtered_bar_colors = bar_colors[valid_mask]

    # 构建主副图
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.5, 0.35,0.15],  # 副图更大
        vertical_spacing=0.05,
    )

    # 主图K线
    fig.add_trace(
        go.Candlestick(
            x=x,
            open=data.Open,
            high=data.High,
            low=data.Low,
            close=data.Close,
            name="K线"
        ),
        row=1, col=1
    )

    # 添加现价注释
    if not data.empty:
        ATM = data.Close.iloc[-1]
        last_time = data.index[-1]
        last_time_str = str(last_time)  # 关键：转为字符串，与x轴一致
        fig.add_annotation(
            x=last_time_str,
            y=ATM,
            text=f"现价 {ATM:.2f}",
            showarrow=True,
            yshift=10,
            font=dict(size=16, color="#F1C40F"),
            bgcolor="rgba(0,0,0,0.7)",
            arrowcolor="#F1C40F",
            xref="x1",
            yref="y1",
        )

    # 副图动力波高低柱
    fig.add_trace(
        go.Bar(
            x=filtered_x,
            y=filtered_bar_height,
            base=filtered_bar_base,
            marker_color=filtered_bar_colors,
            name="动力波",
        ),
        row=2, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=x,
            y=life,
            mode='lines',
            line=dict(color='gray', width=2, dash='solid'),
            name='生命线'
        ),
        row=2, col=1
    )

    # 副图三条水平线
    for yval, name, color in [(50, '强弱分界线', 'white'), (80, '顶', 'magenta'), (20, '底', 'lime')]:
        fig.add_trace(go.Scatter(
            x=[x[0], x[-1]],
            y=[yval, yval],
            mode='lines',
            line=dict(color=color, width=1, dash='dash'),
            name=name,
            showlegend=False
        ), row=2, col=1)

    # 副图2：MACD
    # 计算MACD
    def calc_macd(close, fast=12, slow=26, signal=9):
        """
        计算MACD指标
        :param close: pd.Series 收盘价
        :return: DataFrame，包含macd_diff(DIF)、macd_signal(DEA)、macd_hist(柱)
        """
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_diff = ema_fast - ema_slow  # DIF线
        macd_signal = macd_diff.ewm(span=signal, adjust=False).mean()  # DEA线
        macd_hist = macd_diff - macd_signal  # 柱状图
        return pd.DataFrame({
            "macd_diff": macd_diff,
            "macd_signal": macd_signal,
            "macd_hist": macd_hist
        })

    macd_df = calc_macd(data.Close)
    macd_diff = macd_df["macd_diff"]
    macd_signal = macd_df["macd_signal"]
    macd_hist = macd_df["macd_hist"]

    # MACD柱状图
    fig.add_trace(
        go.Bar(
            x=x,
            y=macd_hist,
            marker_color=["red" if v > 0 else "#00FF0F" for v in macd_hist],
            name="MACD柱",
        ),
        row=3, col=1
    )
    # DIF线
    fig.add_trace(
        go.Scatter(
            x=x,
            y=macd_diff,
            mode='lines',
            line=dict(color='orange', width=2),
            name='DIF'
        ),
        row=3, col=1
    )
    # DEA线
    fig.add_trace(
        go.Scatter(
            x=x,
            y=macd_signal,
            mode='lines',
            line=dict(color='white', width=2, dash='dot'),
            name='DEA'
        ),
        row=3, col=1
    )



    fig.update_layout(
        height=1200,
        template="plotly_dark",
        xaxis=dict(
            rangeslider=dict(
                visible=False
            ),
            showgrid=True,
            showline=True,
            type="category",
        ),
        xaxis2=dict(
            showgrid=True,
            showline=True,
            type="category",
        ),
        xaxis3=dict(
            showgrid=True,
            showline=True,
            type="category",
        ),
        transition_duration=500,

    )



    # fig.update_yaxes(
    #     showgrid=True,  # 显示网格线
    #     showline=True,  # 显示轴线
    #     linewidth=2,  # 轴线宽度
    #     range=[-50, 50],  # Y轴范围设置为-50到50
    #     row=3,  # 应用于第3行
    #     col=1  # 应用于第1列
    # )

    return fig


if __name__ == '__main__':
    app.run(debug=False)




