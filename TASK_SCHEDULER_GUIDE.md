# 任务调度器使用指南

## 概述

`TaskScheduler` 是一个统一的任务调度器，用于管理所有定时任务的启动时间。它解决了现有任务中时间管理分散、难以维护的问题。

## 主要功能

### ✅ 统一时间管理
- 所有任务的启动时间都从 `TaskScheduler` 获取
- 支持多种执行频率：每日、每周、每月、每小时、自定义间隔
- 自动计算下次执行时间

### ✅ 任务管理
- 任务的启用/禁用
- 动态添加/删除任务
- 任务状态监控

### ✅ 调试支持
- 调试模式下快速执行（3秒延迟）
- 详细的日志记录
- 任务执行状态跟踪

## 预定义任务

| 任务名称 | 描述 | 执行时间 | 频率 |
|---------|------|----------|------|
| `features_daily_report` | 期货日报 | 08:01 | 每日 |
| `news_reporter` | 早间新闻播报 | 08:05 | 每日 |
| `weather_report` | 天气播报 | 每2小时 | 自定义 |
| `features_weekly_report` | 期货周报 | 07:25 | 每周一 |
| `features_monthly_report` | 期货月报 | 07:30 | 每月1号 |
| `hk_top10_broadcaster` | 港股TOP10播报 | 09:30 | 每日 |
| `live_news` | 实时新闻 | 每小时 | 每小时 |
| `regular_cleanup_db` | 数据库清理 | 02:00 | 每日 |
| `holder_trade_strategy` | 持仓交易策略 | 14:30 | 每日 |
| `features_min_monitor` | 分钟级监控 | 每5分钟 | 自定义 |

## 使用方法

### 1. 启动所有任务

```python
from task_scheduler import start_scheduler, stop_scheduler

# 启动所有任务
start_scheduler()

# 停止所有任务
stop_scheduler()
```

### 2. 获取任务状态

```python
from task_scheduler import get_all_task_status

# 获取所有任务状态
status_list = get_all_task_status()
for status in status_list:
    print(f"任务: {status['name']}")
    print(f"  下次执行: {status['next_run']}")
    print(f"  启用状态: {status['enabled']}")
```

### 3. 管理单个任务

```python
from task_scheduler import get_task_scheduler

scheduler = get_task_scheduler()

# 获取任务信息
task_info = scheduler.get_task_info("features_daily_report")

# 启用/禁用任务
scheduler.disable_task("news_reporter")
scheduler.enable_task("news_reporter")
```

### 4. 添加新任务

```python
from task_scheduler import TaskScheduler, TaskConfig, TaskFrequency


def my_task_function():
    print("执行我的任务")


# 创建任务配置
new_task = TaskConfig(
    name="my_task",
    function=my_task_function,
    hour=15, minute=30,
    frequency=TaskFrequency.DAILY,
    description="我的新任务"
)

# 注册任务
scheduler = TaskScheduler()
scheduler.register_task(new_task)
```

## 修改现有任务

### 原始代码（需要修改）

```python
# tasks/features_daily_report.py
def schedule_task():
    # 设置下次运行时间
    now = DateUtils.now()
    next_run = now.replace(hour=8, minute=1, second=0, microsecond=0)
    if now >= next_run:
        next_run += timedelta(days=1)
    delay = (next_run - now).total_seconds()

    # 如果是 debug 模式，则立刻执行
    if os.getenv('DEBUG_MODE') == '1':
        delay = 3

    logging.info(f"日报即将在{delay}秒后执行，请等待...")
    Timer(delay, run_daily_report).start()

if __name__ == "__main__":
    schedule_task()
```

### 修改后的代码

```python
# tasks/features_daily_report.py
# 删除 schedule_task 函数

if __name__ == "__main__":
    # 方法1: 直接运行任务（用于测试）
    run_daily_report()

    # 方法2: 使用统一调度器（推荐）
    from task_scheduler import start_scheduler

    start_scheduler()
```

## 任务频率类型

### TaskFrequency.DAILY
每日执行，在指定时间执行一次。

```python
TaskConfig(
    name="daily_task",
    function=my_function,
    hour=8, minute=30,
    frequency=TaskFrequency.DAILY
)
```

### TaskFrequency.WEEKLY
每周执行，在指定星期的指定时间执行。

```python
TaskConfig(
    name="weekly_task",
    function=my_function,
    hour=7, minute=25,
    frequency=TaskFrequency.WEEKLY  # 每周一执行
)
```

### TaskFrequency.MONTHLY
每月执行，在每月1号的指定时间执行。

```python
TaskConfig(
    name="monthly_task",
    function=my_function,
    hour=7, minute=30,
    frequency=TaskFrequency.MONTHLY  # 每月1号执行
)
```

### TaskFrequency.HOURLY
每小时执行，在每小时的指定分钟执行。

```python
TaskConfig(
    name="hourly_task",
    function=my_function,
    minute=0,  # 每小时0分执行
    frequency=TaskFrequency.HOURLY
)
```

### TaskFrequency.CUSTOM
自定义间隔执行。

```python
TaskConfig(
    name="custom_task",
    function=my_function,
    frequency=TaskFrequency.CUSTOM,
    custom_interval_hours=2,      # 每2小时
    custom_interval_minutes=30    # 每30分钟
)
```

## 调试模式

设置环境变量 `DEBUG_MODE=1` 可以启用调试模式：

```bash
export DEBUG_MODE=1
python tasks/task_scheduler.py
```

在调试模式下，所有任务都会在3秒后执行，方便测试。

## API 参考

### TaskScheduler 类

#### 方法

- `register_task(task_config: TaskConfig)` - 注册任务
- `unregister_task(task_name: str)` - 注销任务
- `enable_task(task_name: str)` - 启用任务
- `disable_task(task_name: str)` - 禁用任务
- `start_all_tasks()` - 启动所有任务
- `stop_all_tasks()` - 停止所有任务
- `get_task_status()` - 获取所有任务状态
- `get_task_info(task_name: str)` - 获取特定任务信息

### TaskConfig 类

#### 属性

- `name: str` - 任务名称
- `function: Callable` - 执行函数
- `hour: int` - 执行小时 (0-23)
- `minute: int` - 执行分钟 (0-59)
- `second: int` - 执行秒数 (0-59)
- `frequency: TaskFrequency` - 执行频率
- `custom_interval_hours: int` - 自定义间隔小时数
- `custom_interval_minutes: int` - 自定义间隔分钟数
- `enabled: bool` - 是否启用
- `description: str` - 任务描述
- `debug_delay: int` - 调试模式下的延迟秒数

## 最佳实践

### 1. 任务函数设计
- 任务函数应该是独立的，不依赖外部状态
- 添加适当的错误处理和日志记录
- 避免长时间阻塞的操作

### 2. 时间配置
- 避免任务执行时间冲突
- 考虑系统负载，合理分配执行时间
- 使用有意义的描述信息

### 3. 监控和维护
- 定期检查任务执行状态
- 监控任务执行日志
- 及时处理失败的任务

## 迁移指南

### 步骤1: 备份现有代码
```bash
cp tasks/features_daily_report.py tasks/features_daily_report_backup.py
```

### 步骤2: 修改任务文件
删除 `schedule_task` 函数，保留核心执行函数。

### 步骤3: 测试修改
```bash
python test_task_scheduler.py
```

### 步骤4: 逐步迁移
建议按照以下顺序迁移：
1. 简单的每日任务
2. 复杂的定时任务
3. 自定义间隔任务

## 故障排除

### 常见问题

1. **任务不执行**
   - 检查任务是否已启用
   - 检查执行时间是否正确
   - 查看日志文件

2. **任务重复执行**
   - 检查是否有多个调度器实例
   - 确保任务函数是幂等的

3. **时间计算错误**
   - 检查系统时区设置
   - 验证 DateUtils.now() 返回的时间

### 调试技巧

1. 启用详细日志
2. 使用调试模式快速测试
3. 检查任务状态信息
4. 监控系统资源使用

## 总结

统一的任务调度器提供了以下优势：

- **集中管理**: 所有任务时间配置集中在一个地方
- **易于维护**: 修改时间配置不需要修改多个文件
- **功能丰富**: 支持多种执行频率和动态管理
- **调试友好**: 提供调试模式和详细日志
- **扩展性强**: 易于添加新任务和功能

通过使用 `TaskScheduler`，您可以更好地管理和监控所有定时任务，提高系统的可维护性和可靠性。 