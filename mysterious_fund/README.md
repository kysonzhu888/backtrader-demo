# 神秘资金监控模块

## 概述

神秘资金监控模块专门用于监控ETF基金（如沪深300ETF 510300.SH）的异常成交量情况。当一分钟成交量超过设定阈值时，系统会发出告警，帮助识别可能的大资金流入或流出。

## 功能特性

- **实时监控**: 持续监控ETF基金的成交量数据
- **异常检测**: 当成交量超过阈值时自动发出告警
- **RESTful API**: 提供完整的API接口供前端调用
- **数据统计**: 提供告警统计和历史数据查询
- **可配置阈值**: 支持自定义成交量阈值设置

## 模块结构

```
mysterious_fund/
├── __init__.py                    # 模块初始化文件
├── mysterious_fund_alert_detector.py    # 异常检测器
├── mysterious_fund_market_service.py    # 市场数据服务
├── mysterious_fund_blueprint.py         # Flask蓝图和API
├── test_mysterious_fund.py              # 测试脚本
├── start_mysterious_fund_demo.py        # 启动脚本
└── README.md                            # 说明文档
```

## 主要组件

### 1. MysteriousFundAlertDetector
异常检测器，负责：
- 监控成交量数据
- 判断是否超过阈值
- 生成告警信息

### 2. MysteriousFundMarketService  
市场数据服务，负责：
- 获取实时市场数据
- 更新基金信息
- 触发异常检测

### 3. MysteriousFundBlueprint
Flask蓝图，提供以下API接口：
- `GET /mysterious_fund/market_data` - 获取市场数据
- `GET /mysterious_fund/alerts/recent` - 获取最近告警
- `GET /mysterious_fund/alerts/stats` - 获取告警统计
- `POST /mysterious_fund/config/threshold` - 设置阈值

## 使用方法

### 1. 启动服务
```bash
python mysterious_fund/start_mysterious_fund_demo.py
```

### 2. 测试API
```bash
python mysterious_fund/test_mysterious_fund.py
```

### 3. 在Flask应用中注册
```python
from mysterious_fund import mysterious_fund_bp

app.register_blueprint(mysterious_fund_bp, url_prefix='/mysterious_fund')
```

## 配置参数

- `VOLUME_THRESHOLD`: 成交量阈值（默认1亿元）
- `MONITOR_CODES`: 监控的基金代码列表
- `ALERT_INTERVAL`: 告警间隔时间（秒）

## 告警级别

- **低**: 成交量超过阈值的1-2倍
- **中**: 成交量超过阈值的2-5倍  
- **高**: 成交量超过阈值的5-10倍
- **紧急**: 成交量超过阈值的10倍以上

## 注意事项

1. 确保市场数据服务正常运行
2. 监控时间仅限交易时段（9:30-11:30, 13:00-15:00）
3. 告警数据会保存到数据库中
4. 建议定期清理历史告警数据 