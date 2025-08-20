# 动力波策略说明

## 重要提示

当前目录下有多个动力波策略文件，请使用正确的版本：

### ✅ 新版本（推荐使用）
- **入口文件**: `power_wave.py`
- **核心逻辑**: `power_wave_strategy.py`  
- **特点**: 
  - 使用xtdata数据源
  - 支持daemon.py管理
  - 包含MACD、布林线、百分位等多重条件判断
  - 可配置不同品种（默认沪金）

### ❌ 旧版本（不推荐）
- `pow_wave_strategy.py` - 使用vectorbt，依赖tushare
- `power_wave_xtdata.py` - 早期的xtdata版本

## 运行方式

### 方式1：直接运行（推荐）
```bash
# 从项目根目录运行
python power_wave_strategy/power_wave.py
```

### 方式2：通过daemon管理
```bash
# daemon.py已配置为启动power_wave.py
python daemon.py
```

## 策略功能

1. **开仓条件**（必须全部满足）：
   - 动力波颜色变化（红绿切换）
   - MACD金叉/死叉确认
   - 布林线中轨位置判断
   - 百分位条件（<25%做多，>75%做空）

2. **风控设置**：
   - 硬止损：666元
   - 阶梯式浮动止盈
   - 开仓保护期

3. **数据源**：
   - 使用xtdata
   - 自动获取主力合约

## 配置品种

默认使用沪金，如需更改品种，修改`power_wave.py`中的配置：

```python
# 例如改为螺纹钢
config.update_product(
    product_type='rb',
    product_name='螺纹钢',
    multiplier=10,
    exchange='SF'
)
```

## 注意事项

1. 确保已安装xtdata模块
2. 确保Redis服务正在运行
3. 如遇到导入错误，请确认运行的是`power_wave.py`而不是其他文件