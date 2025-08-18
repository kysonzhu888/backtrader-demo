# 动力波策略（基于xtdata）

## 概述

动力波策略是一个基于动力波指标的量化交易策略，已从tushare数据源迁移到xtdata数据源。策略支持多品种交易，默认使用沪金（AU）。

## 主要特性

### 策略逻辑
- 使用动力波指标判断市场趋势
- 绿变红开多，红变绿开空
- 颜色保持时持仓，颜色反转时平仓

### 风险管理
- **硬止损**：666元（可配置）
- **阶梯式止盈**：
  - 浮盈≥3000元：保留1800元利润
  - 浮盈≥2000元：保留1000元利润
  - 浮盈≥1200元：保留500元利润
  - 浮盈≥666元：推保本（+0.25点）

### 交易保护
- 开盘后15分钟不开仓
- 收盘前15分钟不开仓
- 止损后30分钟不开仓
- 14:58和22:58强制平仓

## 文件说明

```
power_wave_strategy/
├── power_wave_xtdata.py    # 策略主文件（新）
├── run_power_wave.py        # 启动脚本
├── power_wave.py            # 动力波指标计算（原有）
└── README_XTDATA.md         # 本文档
```

## 使用方法

### 1. 基本用法

```bash
# 使用默认配置（沪金）
python run_power_wave.py

# 指定品种
python run_power_wave.py --product AG  # 沪银
python run_power_wave.py --product OI  # 菜籽油

# 自定义止损
python run_power_wave.py --product AU --stop-loss 1000
```

### 2. 支持的品种

| 代码 | 品种 | 合约乘数 | 交易所 |
|------|------|---------|--------|
| AU | 沪金 | 1000 | 上期所 |
| AG | 沪银 | 15 | 上期所 |
| CU | 沪铜 | 5 | 上期所 |
| OI | 菜籽油 | 10 | 郑商所 |
| RB | 螺纹钢 | 10 | 上期所 |
| IF | 沪深300 | 300 | 中金所 |

### 3. 配置修改

在 `power_wave_xtdata.py` 中的 `PowerWaveConfig` 类可以修改以下参数：

```python
# 动力波参数
POWER_WAVE_HL_PERIOD = 34    # 高低点周期
POWER_WAVE_EMA1_PERIOD = 13  # 第一个EMA周期
POWER_WAVE_EMA2_PERIOD = 2   # 第二个EMA周期

# 风控参数
HARD_STOP_LOSS = 666         # 硬止损金额

# 阶梯止盈
BREAKEVEN_THRESHOLDS = [3000, 2000, 1200, 666]
BREAKEVEN_PROFITS = [1800, 1000, 500, 0]
```

## 播报格式

### 开仓播报
```
【动力波信号播报】
品种：AU  周期：1min  时间：2025-01-01 09:30:00
上一根颜色：绿，当前颜色：红
满足开仓条件，开仓方向：多
开仓价格：580.50
```

### 平仓播报
```
【动力波信号播报】
品种：AU  周期：1min  时间：2025-01-01 10:15:00
开仓价格：580.50，当前价格：582.30
颜色变绿平多，本单盈利1800元
```

### 止损播报
```
【动力波信号播报】
品种：AU  周期：1min  时间：2025-01-01 09:45:00
开仓价格：580.50，当前价格：579.84
硬止损，本单亏损-666元
```

## 架构说明

### 主要组件

1. **PowerWaveConfig**：策略配置类
   - 品种配置
   - 风控参数
   - 交易保护时间

2. **PowerWaveIndicator**：动力波指标计算
   - VARD/VARE计算
   - 颜色判断
   - 信号生成

3. **PowerWaveStrategy**：策略主类
   - 数据获取（xtdata）
   - 信号处理
   - 仓位管理
   - 风控执行

### 数据流程

```
xtdata获取实时数据
    ↓
动力波指标计算
    ↓
生成交易信号
    ↓
风控检查
    ↓
执行交易
    ↓
微信播报
```

## 与原版本的主要区别

1. **数据源**：从tushare改为xtdata
2. **架构**：参考boll_strategy的架构，更清晰
3. **去除依赖**：不再使用vectorbt
4. **配置化**：支持多品种，参数可配置
5. **代码结构**：模块化设计，便于维护

## 注意事项

1. 需要先配置好xtdata的登录信息
2. 确保Redis服务正常运行
3. 配置好微信推送功能
4. 建议先在模拟环境测试

## 运行要求

- Python 3.7+
- xtquant（迅投QMT Python API）
- Redis
- 相关Python包：pandas, numpy, redis等

## 常见问题

### Q: 如何切换品种？
A: 使用命令行参数 `--product` 指定，如 `python run_power_wave.py --product AG`

### Q: 如何调整止损？
A: 使用命令行参数 `--stop-loss` 指定，如 `python run_power_wave.py --stop-loss 1000`

### Q: 如何查看日志？
A: 日志会输出到控制台和日志文件，查看 `logs/` 目录

### Q: 如何添加新品种？
A: 在 `run_power_wave.py` 的 `PRODUCT_CONFIGS` 字典中添加品种配置

## 更新记录

### v2.0 (2025-01)
- 数据源从tushare迁移到xtdata
- 重构代码架构，参考boll_strategy
- 支持多品种配置
- 移除vectorbt依赖