# Dashboard 交易监控仪表板

这是交易监控系统的仪表板模块，包含股票、期货和未来加密货币的监控功能。

## 目录结构

```
dashboard/
├── __init__.py                 # 包初始化文件
├── layouts.py                  # 页面布局定义
├── stock_filter_page.py        # 股票筛选页面
├── market_data_client.py       # 市场数据客户端
├── futures_data_processor.py   # 期货数据处理
├── static/                     # 静态资源
│   └── styles.css             # CSS样式文件
└── templates/                  # HTML模板
    ├── base.html              # 基础模板
    └── stock_filter.html      # 股票筛选模板
```

## 主要功能

1. **实时监控**: 显示股票和期货的实时价格、涨跌幅等信息
2. **异常检测**: 实时监控异常情况并提供告警
3. **股票筛选**: 提供多种筛选条件来筛选股票
4. **数据导出**: 支持将筛选结果导出为多种格式

## 使用方法

在项目根目录运行：

```bash
python trading_dashboard.py
```

## 依赖

- dash >= 2.10.0
- pandas >= 1.5.0
- requests >= 2.28.0
- 其他依赖见项目根目录的 requirements.txt 