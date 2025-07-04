# 实时监控系统使用说明

## 功能概述

本系统包含以下核心功能：
1. **Redis缓存**: 股票实时数据缓存和历史数据查询
2. **实时监控**: 开板检测、涨停跌停、异常放量等异常情况监控
3. **统一仪表板**: 在原有仪表板中集成实时提示功能，左侧显示股票数据，右侧显示异常提示

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动Redis服务
```bash
# 确保Redis服务正在运行
redis-server
```

### 3. 启动完整监控系统
```bash
python start_monitor_system.py
```

### 4. 访问监控页面
打开浏览器访问：http://localhost:8051

## 单独启动各组件

### 启动市场数据服务（带Redis缓存）
```bash
python start_with_redis.py
```

### 启动监控仪表板
```bash
python mini_stock/ministock_dash_board.py
```

### 测试Redis功能
```bash
python test_redis_cache.py
```

### 测试监控规则
```bash
python test_monitor_rules.py
```

## 监控功能说明

### 异常检测类型
1. **开板**: 涨停后价格回落
2. **涨停**: 涨幅达到9.9%以上
3. **跌停**: 跌幅达到-9.9%以下
4. **异常放量**: 成交量放大3倍以上
5. **价格异动**: 价格变化超过5%
6. **突破**: 突破当日新高

### 提示级别
- **低**: 一般信息
- **中**: 需要注意
- **高**: 重要提醒
- **紧急**: 开板等关键事件

## 页面布局

### 统一仪表板 (http://localhost:8051)
```
┌─────────────────────────────────────────────────────────┐
│                    小市值成分股实时监控                  │
├─────────────────────────────────────────────────────────┤
│ 最后更新: 2025-01-20 14:30:00                           │
├─────────────────────────────────────────────────────────┤
│ 股票数据 (65%) │ 异常统计 (35%)                          │
│ ┌─────────────────────────┐ │ ┌─────────────────────┐   │
│ │ 序号 │ 股票名 │ 最新价 │ │ │ 今日异常: 15         │   │
│ │ 1    │ 000001│ 12.34  │ │ │ 开板: 3              │   │
│ │ 2    │ 000002│ 15.67  │ │ │ 涨停: 5              │   │
│ │ ...  │ ...   │ ...    │ │ │ 跌停: 2              │   │
│ └─────────────────────────┘ │ └─────────────────────┘   │
│                             │ ┌─────────────────────┐   │
│                             │ │ 实时提示             │   │
│                             │ │ 🔴 000001.SZ 开板！ │   │
│                             │ │ 🟡 000002.SZ 异常放量│   │
│                             │ │ ...                  │   │
│                             │ └─────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 页面功能
- **左侧**: 小市值成分股实时监控表格
- **右侧**: 异常统计和实时提示
- **自动更新**: 每3秒自动刷新数据
- **导航栏**: 支持切换到股票筛选页面

## API接口

### 市场数据接口
```bash
# 获取市场数据
curl "http://localhost:5000/market_data"

# 获取股票列表
curl "http://localhost:5000/stock_list"

# 获取某只股票当天数据
curl "http://localhost:5000/stock_data_today/000001.SZ?limit=100"
```

### 异常提示接口
```bash
# 获取最近异常提示
curl "http://localhost:5000/alerts/recent?minutes=30"

# 获取指定类型异常
curl "http://localhost:5000/alerts/type/开板"

# 获取异常统计
curl "http://localhost:5000/alerts/stats"
```

### 缓存管理接口
```bash
# 获取缓存统计
curl "http://localhost:5000/cache_stats"

# 清空缓存
curl -X POST "http://localhost:5000/clear_cache"
```

## 文件说明

### 核心文件
- `mini_stock/monitor_rules.py`: 监控规则管理器
- `mini_stock/market_data_service.py`: 集成了监控功能的市场数据服务
- `mini_stock/ministock_dash_board.py`: 统一监控仪表板（已集成实时提示）
- `mini_stock/layouts.py`: 页面布局定义
- `start_monitor_system.py`: 系统启动器

### 测试文件
- `test_monitor_rules.py`: 监控规则测试
- `test_redis_cache.py`: Redis功能测试
- `redis_client_example.py`: API使用示例

### 文档文件
- `README_Redis.md`: Redis详细文档
- `USAGE.md`: 本使用说明

## 配置说明

### Redis配置 (environment.py)
```python
REDIS_HOST = '192.168.50.52'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = None
```

### 监控参数 (monitor_rules.py)
```python
limit_up_threshold = 0.099      # 涨停阈值
limit_down_threshold = -0.099   # 跌停阈值
volume_surge_threshold = 3.0    # 异常放量阈值
price_surge_threshold = 0.05    # 价格异动阈值
breakout_threshold = 0.02       # 突破阈值
```

## 注意事项

1. **Redis连接**: 确保Redis服务正在运行且可连接
2. **数据延迟**: 异常检测基于实时数据，可能存在1-3秒延迟
3. **内存使用**: 监控历史记录默认保存1000条，注意内存使用
4. **网络稳定**: 确保网络连接稳定，避免数据丢失
5. **日志监控**: 关注日志输出，及时发现异常情况
6. **统一入口**: 所有监控功能已集成到原有仪表板，无需多个页面

## 故障排除

### Redis连接失败
- 检查Redis服务是否启动
- 确认IP地址和端口配置
- 检查防火墙设置

### 监控页面无法访问
- 确认市场数据服务正在运行
- 检查端口8051是否被占用
- 查看服务日志

### 异常检测不准确
- 检查前收盘价数据是否正确
- 确认监控参数设置合理
- 查看数据源是否正常

## 扩展功能

### 添加新的监控规则
在 `monitor_rules.py` 中的 `MonitorRules.update_stock_data()` 方法中添加新的检测逻辑。

### 自定义提示级别
修改 `AlertLevel` 枚举和相应的颜色配置。

### 增加数据源
在 `market_data_service.py` 中集成新的数据源。

### 优化性能
- 调整更新频率
- 优化Redis缓存策略
- 增加数据压缩 