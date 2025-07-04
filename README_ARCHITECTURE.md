# 市场数据服务架构说明

## 概述

本项目采用共享Flask实例的架构，将股票服务和期货服务分离为独立的蓝图，通过统一的Flask应用提供服务。

## 架构设计

### 1. 共享Flask基础服务 (`app.py`)
- 提供统一的Flask应用实例
- 管理共享配置（如上传文件夹、允许的文件类型等）
- 提供蓝图注册和启动功能

### 2. 股票服务蓝图 (`mini_stock/stock_blueprint.py`)
- 提供股票相关的API接口
- 管理`MarketDataService`实例
- 路由前缀：`/stock`

### 3. 股指期货服务蓝图 (`features/index_futures_market_service.py`)
- 提供期货相关的API接口
- 管理`IndexFuturesMarketService`实例
- 路由前缀：`/futures`

### 4. 核心服务类
- `MarketDataService`：股票市场数据服务（已从Flask中分离）
- `IndexFuturesMarketService`：股指期货市场数据服务

## API接口

### 股票服务接口 (`/stock`)
- `GET /stock/market_data` - 获取股票市场数据
- `GET /stock/preclose` - 获取前收盘价
- `GET /stock/stock_list` - 获取股票列表
- `POST /stock/set_stock_list` - 设置股票列表（文件上传）
- `GET /stock/filtered_stocks` - 获取筛选后的股票列表
- `GET /stock/stock_data_today/<stock_code>` - 获取某只股票当天数据
- `GET /stock/cache_stats` - 获取缓存统计信息
- `POST /stock/clear_cache` - 清空缓存
- `GET /stock/alerts/recent` - 获取最近的异常提示
- `GET /stock/alerts/type/<alert_type>` - 获取指定类型的异常提示
- `GET /stock/alerts/stats` - 获取异常提示统计信息

### 期货服务接口 (`/futures`)
- `GET /futures/market_data` - 获取期货市场数据
- `GET /futures/futures_list` - 获取期货列表
- `POST /futures/set_futures_list` - 设置期货列表（文件上传）
- `GET /futures/futures_info/<futures_code>` - 获取期货详细信息
- `GET /futures/health` - 期货服务健康检查

### 通用接口
- `GET /` - 服务健康检查和API概览

## 启动方式

### 使用主启动文件
```bash
python main.py
```

### 手动启动
```python
from app import get_app, register_blueprint, run_app
from mini_stock.stock_blueprint import stock_blueprint, init_market_service
from features.index_futures_market_service import futures_blueprint, init_index_futures_service

# 获取Flask应用
app = get_app()

# 初始化服务
init_market_service()
init_index_futures_service()

# 注册蓝图
register_blueprint(stock_blueprint)
register_blueprint(futures_blueprint)

# 启动服务
run_app(host='0.0.0.0', port=5000)
```

## 配置

通过`environment.py`文件配置服务参数：
- `MARKET_DATA_SERVICE_HOST` - 服务主机地址
- `MARKET_DATA_SERVICE_PORT` - 服务端口
- `DEBUG` - 调试模式
- `REDIS_HOST` - Redis主机地址
- `REDIS_PORT` - Redis端口
- `REDIS_DB` - Redis数据库
- `REDIS_PASSWORD` - Redis密码

## 优势

1. **模块化设计**：股票和期货服务完全分离，便于维护和扩展
2. **共享资源**：统一的Flask实例，减少资源消耗
3. **统一配置**：共享的配置管理，避免重复代码
4. **灵活扩展**：可以轻松添加新的服务蓝图
5. **清晰的路由**：通过URL前缀区分不同服务

## 扩展新服务

要添加新的服务，只需：
1. 创建新的蓝图文件
2. 实现服务类
3. 在`main.py`中注册蓝图

例如：
```python
# 创建新服务蓝图
new_service_blueprint = Blueprint('new_service', __name__, url_prefix='/new_service')

# 在main.py中注册
register_blueprint(new_service_blueprint)
``` 