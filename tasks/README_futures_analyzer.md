# 股指期货净空单量分析程序

## 功能概述

本程序用于统计中金所四个股指期货（IH、IF、IM、IC）每日的净空单量变动，并生成分析报告发送到微信。

## 核心功能

1. **数据下载**: 自动从中金所官网下载四个股指期货的持仓数据
2. **数据解析**: 解析CSV文件，区分中信证券和其他券商的持仓情况
3. **统计分析**: 计算净空单量变动和总持仓情况
4. **报告生成**: 生成中文分析报告
5. **微信推送**: 自动发送报告到指定微信联系人

## 程序结构

```
tasks/
├── futures_net_short_position_analyzer.py  # 主程序
├── test_futures_analyzer.py                # 测试脚本
├── futures_data/                           # 数据存储目录
│   ├── IF_20250805.csv                     # IF期货数据
│   ├── IH_20250805.csv                     # IH期货数据
│   ├── IC_20250805.csv                     # IC期货数据
│   └── IM_20250805.csv                     # IM期货数据
└── README_futures_analyzer.md              # 说明文档
```

## 使用方法

### 1. 手动运行

```bash
# 直接运行主程序
python tasks/futures_net_short_position_analyzer.py

# 运行测试脚本
python tasks/test_futures_analyzer.py
```

### 2. 定时任务

程序已集成到任务调度器中，每天下午5点自动执行：

```python
# 在 task_scheduler.py 中已注册
TaskConfig(
    name="futures_net_short_position_analyzer",
    function=self._import_and_run_task("futures_net_short_position_analyzer", "main"),
    hour=17, minute=0,
    description="股指期货净空单量分析 - 统计中金所四个股指期货的净空单量变动",
    frequency=TaskFrequency.DAILY,
    run_in_main_thread=True
)
```

## 数据来源

- **数据地址**: http://www.cffex.com.cn/sj/ccpm/
- **数据格式**: CSV文件
- **更新频率**: 每日收盘后更新
- **数据内容**: 排名前20券商的持仓数据

## 分析逻辑

### 1. 中信证券识别
程序会自动识别以下关键词：
- 中信
- 中信期货
- 中信证券

### 2. 净空单计算
```
净空单量 = 总卖单量 - 总买单量
```

### 3. 策略建议
- 净空单量 < 6.5万：适合做多
- 净空单量 > 11万：适合做空
- 6.5万 ≤ 净空单量 ≤ 11万：建议观望

## 报告格式

生成的报告包含以下信息：
1. 中信证券在各期货上的持仓变化
2. 其他主要玩家的持仓变化
3. IH、IF和IC、IM的合计变化
4. 市场偏向判断
5. 总净空单量
6. 策略建议

### 示例报告
```
2025年08月05号，净空单数据如下：
某信，IF减空208手, IH减空132手, IC加空78手, IM加空753手；
其他主要玩家，IF加空509手, IH加空1389手, IC加空509手, IM加空509手；
合计对IH、IF加空1558手，合计对IC、IM加空1849手。
操作完成后，共持有净空单79638手。
净空单量在正常范围内，建议观望。
```

## 配置说明

### 微信接收者配置
在 `futures_net_short_position_analyzer.py` 中修改：

```python
# 发送到微信
recipients = ["文件传输助手"]  # 可以根据需要修改接收者
```

### 数据目录配置
```python
self.data_dir = "tasks/futures_data"  # 可以修改数据存储路径
```

## 依赖库

- `requests`: 用于下载CSV文件
- `pandas`: 用于解析CSV数据
- `datetime`: 用于日期处理
- `utils.logger_utils`: 日志工具
- `utils.wechat_helper`: 微信发送工具
- `utils.date_utils`: 日期工具

## 注意事项

1. **数据时效性**: 数据一般在当天收盘后才有，程序会在下午5点前使用昨天的数据，5点后使用今天的数据
2. **网络连接**: 需要稳定的网络连接来下载数据
3. **微信客户端**: 发送微信消息需要Windows系统并安装微信客户端
4. **文件编码**: CSV文件使用UTF-8编码
5. **数据准确性**: 程序会验证下载的数据完整性

## 故障排除

### 1. 数据下载失败
- 检查网络连接
- 确认中金所网站可访问
- 检查URL格式是否正确

### 2. CSV解析失败
- 检查文件编码是否为UTF-8
- 确认CSV文件格式正确
- 检查文件是否完整下载

### 3. 微信发送失败
- 确认微信客户端已登录
- 检查接收者名称是否正确
- 确认程序在主线程中运行

## 更新日志

- **v1.0**: 初始版本，支持基本的净空单量分析功能
- 支持四个股指期货（IH、IF、IM、IC）的数据分析
- 集成定时任务调度
- 支持微信消息推送 