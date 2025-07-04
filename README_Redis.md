# Redis缓存功能使用说明

## 概述

本项目集成了Redis缓存功能，用于缓存股票实时数据，提高数据访问效率并减少对数据源的频繁请求。

## 功能特性

### 1. 实时数据缓存
- 自动缓存股票实时行情数据
- 支持单只股票和批量股票数据缓存
- 数据按日期自动分类存储

### 2. 数据查询接口
- 获取某只股票当天的所有历史数据
- 获取股票最新实时数据
- 批量获取多只股票的最新数据

### 3. 自动清理机制
- 每天凌晨自动清空前一天的缓存数据
- 防止数据量过大影响系统性能
- 支持手动清理缓存

### 4. 筛选结果缓存
- 缓存股票筛选结果，提高筛选效率
- 支持条件哈希，避免重复计算

## 安装和配置

### 1. 安装Redis
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Windows
# 下载Redis for Windows并安装
```

### 2. 启动Redis服务
```bash
# Linux/macOS
redis-server

# Windows
redis-server.exe
```

### 3. 安装Python依赖
```bash
pip install -r requirements.txt
```

### 4. 配置环境变量
在 `environment.py` 中添加Redis配置：
```python
# Redis配置
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = None  # 如果有密码，请设置
```

## API接口

### 1. 获取股票当天数据
```
GET /stock_data_today/<stock_code>?limit=100
```
- `stock_code`: 股票代码（如：000001.SZ）
- `limit`: 可选，限制返回的数据条数

**响应示例：**
```json
[
  {
    "code": "000001.SZ",
    "price": 12.34,
    "volume": 1000000,
    "timestamp": "2025-01-20T14:30:00",
    "change": 0.56,
    "change_pct": 4.76
  }
]
```

### 2. 获取缓存统计信息
```
GET /cache_stats
```

**响应示例：**
```json
{
  "today_stocks": 150,
  "latest_stocks": 150,
  "filter_caches": 5,
  "total_records": 45000,
  "date": "20250120"
}
```

### 3. 清空缓存
```
POST /clear_cache
```

**响应示例：**
```json
{
  "message": "缓存清空成功"
}
```

## 使用示例

### 1. 启动市场数据服务
```python
from mini_stock.market_data_service import start_service
from datetime import datetime

# 启动服务，自动初始化Redis缓存
start_service(
    host='0.0.0.0',
    port=5000,
    report_date=datetime(2025, 1, 20)
)
```

### 2. 直接使用缓存管理器
```python
from mini_stock.redis_cache_manager import RedisCacheManager

# 初始化缓存管理器
cache_manager = RedisCacheManager(
    host='localhost',
    port=6379,
    db=0
)

# 缓存股票数据
stock_data = {
    "code": "000001.SZ",
    "price": 12.34,
    "volume": 1000000
}
cache_manager.cache_stock_data("000001.SZ", stock_data)

# 获取当天数据
today_data = cache_manager.get_stock_data_today("000001.SZ", limit=100)

# 获取最新数据
latest_data = cache_manager.get_latest_stock_data("000001.SZ")
```

### 3. 测试Redis功能
```bash
python test_redis_cache.py
```

## 数据存储结构

### Redis Key命名规则
- 当天数据：`stock_data:{股票代码}:{日期}` (List类型)
- 最新数据：`stock_latest:{股票代码}` (String类型，5分钟过期)
- 筛选缓存：`filter_cache:{条件哈希}` (String类型，5分钟过期)

### 数据格式
```json
{
  "code": "000001.SZ",
  "price": 12.34,
  "volume": 1000000,
  "change": 0.56,
  "change_pct": 4.76,
  "open": 11.80,
  "high": 12.50,
  "low": 11.75,
  "close": 12.34,
  "timestamp": "2025-01-20T14:30:00.123456"
}
```

## 性能优化

### 1. 批量操作
- 使用Redis Pipeline进行批量读写操作
- 减少网络往返次数，提高性能

### 2. 过期策略
- 当天数据：第二天凌晨自动过期
- 最新数据：5分钟过期
- 筛选结果：5分钟过期

### 3. 内存管理
- 定期清理过期数据
- 限制单只股票的历史数据量
- 监控Redis内存使用情况

## 监控和维护

### 1. 查看缓存统计
```bash
curl http://localhost:5000/cache_stats
```

### 2. 手动清理缓存
```bash
curl -X POST http://localhost:5000/clear_cache
```

### 3. Redis监控命令
```bash
# 连接Redis
redis-cli

# 查看所有key
keys *

# 查看内存使用
info memory

# 查看连接数
info clients
```

## 故障排除

### 1. Redis连接失败
- 检查Redis服务是否启动
- 确认主机地址和端口配置
- 检查防火墙设置

### 2. 数据缓存失败
- 检查Redis内存是否充足
- 确认数据格式是否正确
- 查看日志文件

### 3. 数据查询失败
- 确认股票代码格式正确
- 检查Redis连接状态
- 验证数据是否存在

## 注意事项

1. **数据量控制**：单只股票每天可能产生数千条记录，注意监控Redis内存使用
2. **网络延迟**：Redis连接延迟会影响数据缓存性能
3. **数据一致性**：缓存数据可能与实时数据存在短暂延迟
4. **备份策略**：重要数据建议定期备份Redis数据
5. **监控告警**：建议设置Redis内存使用率告警

## 扩展功能

### 1. 数据压缩
可以考虑对历史数据进行压缩存储，减少内存占用

### 2. 分布式缓存
对于大规模应用，可以考虑使用Redis Cluster

### 3. 数据持久化
配置Redis RDB或AOF持久化，防止数据丢失

### 4. 缓存预热
在服务启动时预加载常用股票数据 