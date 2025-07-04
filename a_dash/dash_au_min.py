#coding=utf-8

# DASH and PLOTLY libraries
from dash import Dash, dcc, html, Input, Output
import dash_bootstrap_components as dbc # v1.6.0
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
# Major libraries
import os
import pandas as pd
import numpy as np
import pandas_ta as ta
import qstock as qs # Healer
from datetime import datetime as dt
from datetime import timedelta
# ML libraries
from scipy.signal import argrelextrema, find_peaks
from sklearn.neighbors import KernelDensity
# QMT libraries
from xtquant import xtdata # 迅投数璐 CQF Tushare
import QMT_Compiled_Functions as qcf
import moduleigh as ml

ml.mypandasview()
ml.ignore_warnings()



starting_date = dt.now()-timedelta(days=30)

starting_date = str(starting_date.strftime('%Y%m%d'))

# app = Dash()
app = Dash(external_stylesheets=[dbc.themes.CYBORG])
def create_dropdowns(option, id_value):
    return html.Div([
                html.H2(id_value),
                dcc.Dropdown(
                        option,
                        id=id_value,
                        value=option[0],
                        style={
                            "width": "200px",
                            "margin":"auto",
                            "padding":"10px, 30px, 10px, 30px"
                        },
                    )
            ])


app.layout = html.Div([
    # html.H1(id="count-up")
    html.Div([
        create_dropdowns(["510300 SH","510500.SH","510050.$H", ], "ticker"),
        create_dropdowns(["10m","30m","1h",], "freq"),
    ], style={
        "display": "flex",
        "justify-content": "space-around",
        "margin": "auto",
        "width": "50%"
    }),

    dcc.Graph(id='live-graph'),
    dcc.Interval(id="interval", interval=5*1000,n_intervals=0)
])


@qcf.timer
def get_data(ticker_: str, freq: str= None)-> pd.DataFrame:
    xtdata.download_sector_data()
    qcf.run_subscriptors_once_a_day(ticker_, int(os.getenv('GLOBAL QMT PORT')))
    hist_data = xtdata.get_market_data_ex(
        field_list=['open', 'high', 'low', 'close','volume'],
        stock_list=[ticker_],
        period=freq,
        start_time=starting_date,
        count=-1,
    )
    hist_data = [value for key, value in hist_data.items()][-1]
    _data_= pd.DataFrame(hist_data.copy(deep=True))
    _data_.index = pd.to_datetime(_data_.index.astype(str),
                                    format='%Y%m%d%H%M%S',errors='coerce')
    _data_.rename(columns={
        'open': '0pen',
        'high': 'High',
        'low':'Low',
        'close': 'Close',
        'volume':'Volume',
    },inplace=True)

    return _data_

def find_price_peaks(ticker_:str,
                        freq: str = None,
                    peaks_range: list = [3,5],
                look_back_period:int = None)->(pd.DataFrame, np.ndarray):

    data_ = get_data(ticker_, freq)
    start_index = len(data_) - look_back_period
    slice_ = slice(start_index, len(data_))
    num_peaks = -999

    sample_df = data_.iloc[slice_]
    sample = sample_df[["Close"]].to_numpy().flatten()
    maxima = argrelextrema(sample, np.greater)
    minima = argrelextrema(sample, np.less)
    extrema_prices = np.concatenate((sample[maxima], sample[minima]))
    interval = extrema_prices[0] / 10000
    bandwidth = interval

    while num_peaks < peaks_range[0] or num_peaks > peaks_range[1]:
        kde = KernelDensity(kernel='gaussian', bandwidth=bandwidth).fit(extrema_prices.reshape(-1, 1))
        a, b = min(extrema_prices), max(extrema_prices)
        price_range_ = np.linspace(a, b, 1000).neshape(-1, 1)
        pdf = np.exp(kde.score_samples(price_range_))
        peaks_ = find_peaks(pdf)[0]
        num_peaks = len(peaks_)
        bandwidth += interval

        if bandwidth > 100 * interval:
            print("Failed to converge, stopping...")
            break

    peaks_values = price_range_[peaks_]

    return sample_df,peaks_values


def get_stats(ticker_):
    df_2 = qs.realtime_data(code = ticker_.split('.')[0])
    df_2[['成交额','总市值','流通市值']] = (df_2[['成交额','总市值','流通市值']] / 1e8).round(2)
    if (df_2.市盈率.values == 0.0).all():
        df_2.drop(['市率'], axis = 1, inplace = True)
    return df_2


def get_money_flow(ticker_):
    df_3 = qs.intraday_money(code=ticker_.split('.')[0])
    df_3.index = pd.to_datetime(df_3.时间)
    df_3['流入总量'] = df_3.iloc[:, -5:].sum(axis=1)
    df_3['流入盘斜度'] = np.gradient(df_3['流入总盘'])
    df_3['超大主力符号']= np.where((df_3.主力净流入 + df_3.超大单净流入) > 0, "+","_")
    return df_3

@app.callback(
    Output("live-graph", "figure"),
    Input("interval", "n_intervals"),
    Input("ticker", "value"),
    Input("freq", "value"),
)

def update_figure(n_intervals, ticker, freq):
    data, lines = find_price_peaks(ticker, freq, look_back_period = 180)
    df_2 = get_stats(ticker)
    df_3 = get_money_flow(ticker)

    fig_ = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing = 0.05,
        row_heights=[0.7, 0.15, 0.15],
        specs=[[{"secondary_y": False}],
               [{"secondary_y": False}],
                [{"secondary_y": True}]],
    )

    fig_.add_trace(
        go.Candlestick(
            x=data.index,
            open=data['open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name="Candlestick",
        ), row=1, col=1
    )

    # 添加现价注释
    ATM = data['Close'].iloc[-1]
    fig_.add_annotation(
        x=data.index[-1],
        y=data['Close'].iloc[-1],
        text=f"现价{ATM:.3f}",
        showarrow=True,
        yref='y1',
        xref='x1',
        yshift=10,
        font=dict(size=16)
    )

    # 添加资金流注释
    money_flow = df_3.iloc[-1][-2] / 1e4  # 单位转换为万
    money_flow_sign = df_3.iloc[-1][-1]  # 资金流方向（"+"或"-"）
    money_flow_color = "tomato" if money_flow_sign == "+" else "seagreen"

    fig_.add_annotation(
        x=data.index[-1],
        y=data['Close'].iloc[-1],
        text=f"资金流{money_flow:.2f}万 ({money_flow_sign})",
        showarrow=False,
        yref='y1',
        xref='x1',
        yshift=80,
        font=dict(size=16, color=money_flow_color)
    )

    fig_.add_trace(
        go.Bar(
            x=data.index,
            y=data['Volume'],
            marker=dict(
                color=data['Close'],
                line=dict(
                    width=3,
                    color="darkmagenta",
                ),
                autocolorscale=True,
            ),
            name="Volume",
        ),
        row=2,
        col=1
    )

    # 添加CCI指标曲线 (25周期)
    fig_.add_trace(
        go.Scatter(
            x=data.index,
            y=ta.cci(data['High'], data['Low'], data['Close'], length=25),
            mode='lines',
            name='CCI-25',
            line=dict(color='darkorchid', width=2),
        ),
        row=3,  # 在第3行显示
        col=1,  # 在第1列显示
        secondary_y=True  # 使用次坐标轴
    )

    # 添加CCI指标曲线 (50周期)
    fig_.add_trace(
        go.Scatter(
            x=data.index,
            y=ta.cci(data['High'], data['Low'], data['Close'], length=50),
            mode='lines',
            name='CCI-50',
            line=dict(color='darkcyan', width=2),
        ),
        row=3,  # 在第3行显示
        col=1,  # 在第1列显示
        secondary_y=True  # 使用次坐标轴
    )

    # 更新主坐标轴设置（左侧Y轴）
    fig_.update_yaxes(
        showgrid=True,  # 显示网格线
        showline=True,  # 显示轴线
        linewidth=2,  # 轴线宽度
        range=[-50, 50],  # Y轴范围设置为-50到50
        row=3,  # 应用于第3行
        col=1  # 应用于第1列
    )

    # 更新次坐标轴设置（右侧Y轴）
    fig_.update_yaxes(
        showgrid=True,  # 显示网格线
        showline=True,  # 显示轴线
        linewidth=2,  # 轴线宽度
        range=[-200, 200],  # Y轴范围设置为-200到200
        row=3,  # 应用于第3行
        col=1,  # 应用于第1列
        secondary_y=True  # 应用于次坐标轴
    )

    # 绘制水平线及对应标注
    for line_value in lines:
        # 为每个线值绘制一条横线
        fig_.add_shape(
            type='line',
            x0=data.index[0],  # 图表左侧边界
            y0=line_value,  # 线的Y轴位置
            x1=data.index[-1],  # 图表右侧边界
            y1=line_value,  # 线的Y轴位置
            line=dict(
                color='RoyalBlue',
                width=1.5,
                dash='dash'  # 可选：设置虚线样式
            ),
            xref='x',
            yref='y',
            row=1,
            col=1
        )

        # 在图表右侧添加线值标注
        fig_.add_annotation(
            x=data.index[-1],  # 最右侧位置
            y=line_value,  # 对应的Y值位置
            text=f"{line_value:.3f}",  # 显示格式化的数值
            showarrow=False,  # 不显示箭头
            font=dict(
                color='RoyalBlue',
                size=14  # 字体大小
            ),
            xanchor='left',  # 文本相对于x位置左对齐
            yanchor='middle',  # 文本相对于y位置居中
            xshift=5,  # 向右偏移5像素
            row=1,
            col=1
        )

    # 准备HTML格式的数据展示
    df_2_string = '<br>'.join(df_2.T.to_string(header=False).split('\n'))

    fig_.add_annotation(
        xref='paper',  # 使用整个图表区域作为参考
        yref='paper',  # 使用整个图表区域作为参考
        x=0.1,  # x位置从左边开始10%
        y=1,  # y位置在顶部(1表示顶部)
        text=df_2_string,  # 显示的文本内容
        showarrow=False,  # 不显示指向箭头
        align='left',  # 文本左对齐
        font=dict(size=14)  # 设置字体大小为14
    )

    fig_.update_layout(
        height=800,
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
        template="plotly_dark",
        # PRESENTATION / GGPLOT2 / SOLARIZED / PLOTLY / PLOTLY_WHITE / PLOTLY_DARK
        transition_duration=500,
    )

    return fig_

if __name__ == '__main__':
    # app.run_server(debug=True, port=8051)
    app.run(debug=True, port=os.getenv('DASH_THACKRAY'))
    # end of the script