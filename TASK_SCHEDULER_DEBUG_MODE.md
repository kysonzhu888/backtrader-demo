# 任务调度器调试模式使用说明

## 🎯 **功能概述**

任务调度器现在支持调试模式，在调试模式下所有任务都会在3秒后执行，方便快速测试和验证任务功能。

## 🔧 **启用调试模式**

### 方法1：设置环境变量
```bash
# Windows PowerShell
$env:DEBUG_MODE='1'
python task_scheduler.py

# Windows CMD
set DEBUG_MODE=1
python task_scheduler.py

# Linux/Mac
export DEBUG_MODE=1
python task_scheduler.py
```

### 方法2：在代码中设置
```python
import os
os.environ['DEBUG_MODE'] = '1'

from task_scheduler import start_scheduler
start_scheduler()
```

## ✅ **调试模式特性**

### 1. **延迟时间统一**
- 所有任务都使用 `debug_delay` 字段的值（默认3秒）
- 忽略正常的调度时间设置
- 便于快速测试任务执行

### 2. **日志提示**
启动时会显示调试模式提示：
```
🔧 任务调度器运行在调试模式下 - 所有任务将在3秒后执行
```

### 3. **状态显示**
在调试模式下，`get_task_status()` 和 `get_task_info()` 方法会显示调试延迟时间而不是正常延迟时间。

## 🧪 **测试验证**

### 运行测试脚本
```bash
python simple_debug_test.py
```

**预期输出：**
```
=== 测试调试模式 ===
总任务数: 12

前3个任务的延迟时间:
1. features_data_preloader: 3.0秒
2. features_daily_loader: 3.0秒
3. features_daily_report: 3.0秒

✅ 调试模式工作正常
```

### 手动测试
```python
import os
from task_scheduler import get_all_task_status

# 设置调试模式
os.environ['DEBUG_MODE'] = '1'

# 获取任务状态
status_list = get_all_task_status()

# 检查延迟时间
for status in status_list[:3]:
    print(f"{status['name']}: {status['delay_seconds']:.1f}秒")
```

## 📋 **任务配置**

### TaskConfig 字段
```python
@dataclass
class TaskConfig:
    # ... 其他字段 ...
    debug_delay: int = 3  # 调试模式下的延迟秒数
```

### 自定义调试延迟
可以为不同任务设置不同的调试延迟时间：
```python
self.register_task(TaskConfig(
    name="my_task",
    function=my_function,
    hour=8, minute=30,
    description="我的任务",
    debug_delay=5  # 调试模式下5秒后执行
))
```

## 🔄 **正常模式 vs 调试模式**

### 正常模式
- 任务按照设定的时间执行
- 延迟时间根据当前时间和下次执行时间计算
- 适合生产环境

### 调试模式
- 所有任务都在3秒后执行
- 忽略正常的时间设置
- 适合开发和测试

## 🎯 **使用场景**

### 1. **开发测试**
```bash
# 快速测试新任务
$env:DEBUG_MODE='1'
python task_scheduler.py
```

### 2. **功能验证**
```python
# 验证任务是否正常工作
import os
os.environ['DEBUG_MODE'] = '1'
from task_scheduler import start_scheduler
start_scheduler()
```

### 3. **问题排查**
```python
# 排查任务执行问题
import os
os.environ['DEBUG_MODE'] = '1'
from task_scheduler import get_all_task_status

status_list = get_all_task_status()
for status in status_list:
    if status['enabled']:
        print(f"{status['name']}: {status['delay_seconds']}秒")
```

## ⚠️ **注意事项**

### 1. **环境变量**
- 调试模式通过环境变量 `DEBUG_MODE=1` 控制
- 必须在启动调度器之前设置
- 重启调度器后需要重新设置

### 2. **任务执行**
- 调试模式下任务会立即执行（3秒后）
- 不会影响任务的正常逻辑
- 只是改变了执行时间

### 3. **生产环境**
- 生产环境不要启用调试模式
- 调试模式仅用于开发和测试
- 确保生产环境的环境变量设置正确

## 🚀 **快速开始**

### 1. **启用调试模式**
```bash
$env:DEBUG_MODE='1'
```

### 2. **启动调度器**
```bash
python task_scheduler.py
```

### 3. **观察日志**
```
🔧 任务调度器运行在调试模式下 - 所有任务将在3秒后执行
任务 features_data_preloader 将在 2025-07-28 11:30:00 执行，延迟 3.00 秒
任务 features_daily_loader 将在 2025-07-28 11:30:00 执行，延迟 3.00 秒
...
```

### 4. **验证执行**
3秒后所有任务开始执行，可以观察日志确认任务是否正常工作。

## 📝 **总结**

调试模式是一个非常有用的功能，可以：
- ✅ 快速测试任务功能
- ✅ 验证任务配置是否正确
- ✅ 排查任务执行问题
- ✅ 提高开发和测试效率

通过设置 `DEBUG_MODE=1` 环境变量，您可以轻松启用调试模式，所有任务将在3秒后执行，大大提高了开发和测试的效率！ 