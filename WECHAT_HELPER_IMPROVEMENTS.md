# WeChatHelper 错误处理改进

## 问题描述

在使用 `WeChatHelper` 发送微信消息时，经常出现以下错误：
```
(-2147467259, '未指定的错误', (None, None, None, 0, None))
```

这个错误通常是由于：
1. 微信窗口状态异常
2. COM 接口通信问题
3. 微信版本兼容性问题
4. 网络连接不稳定

## 改进内容

### 1. 增强的错误处理机制

#### 重试机制
- 消息发送失败时自动重试最多3次
- 每次重试间隔递增（1秒、2秒）
- 重试前先切换到目标聊天窗口

#### COM 错误检测
- 自动检测 COM 相关错误（包括 `-2147467259` 错误码）
- 检测到 COM 错误时自动重新初始化微信客户端
- 提供详细的错误日志记录

### 2. 新增功能

#### 健康检查
```python
# 检查微信客户端连接状态
health_status = wechat.check_wechat_health()
if not health_status:
    print("微信客户端连接异常")
```

#### 强制重新初始化
```python
# 强制重新初始化微信客户端
success = wechat.force_reinitialize()
if success:
    print("重新初始化成功")
```

#### 发送统计
```python
# 获取发送统计信息
stats = wechat.get_send_stats()
print(f"发送统计: {stats}")
```

### 3. 改进的消息发送流程

#### 消息发送流程
1. **预处理**：检查消息和接收者有效性
2. **去重检查**：避免发送重复消息
3. **间隔控制**：确保发送间隔不小于2秒
4. **窗口切换**：先切换到目标聊天窗口
5. **发送重试**：失败时最多重试3次
6. **错误恢复**：COM错误时自动重新初始化

#### 文件发送流程
1. **文件验证**：检查文件是否存在
2. **窗口切换**：切换到目标聊天窗口
3. **发送重试**：失败时最多重试3次
4. **错误恢复**：COM错误时自动重新初始化

## 使用方法

### 基本使用
```python
from utils.wechat_helper import WeChatHelper

# 创建实例
wechat = WeChatHelper()

# 发送消息
wechat.send_message("测试消息", "群聊名称")

# 发送文件
wechat.send_file("path/to/file.txt", "群聊名称")
```

### 错误处理
```python
# 检查健康状态
if not wechat.check_wechat_health():
    # 强制重新初始化
    wechat.force_reinitialize()

# 获取发送统计
stats = wechat.get_send_stats()
print(f"成功发送: {stats['success_count']}")
print(f"失败次数: {stats['error_count']}")
```

### 调试模式
```python
import os

# 设置调试模式（不实际发送消息）
os.environ['DEBUG_MODE'] = '1'
wechat = WeChatHelper()
wechat.send_message("调试消息", "测试群聊")
```

## 配置选项

### 环境变量
- `DEBUG_MODE=1`：启用调试模式，不实际发送消息

### 可调参数
- `min_interval`：最小发送间隔（默认2秒）
- `max_retries`：最大重试次数（默认3次）

## 错误代码说明

| 错误代码 | 含义 | 处理方式 |
|----------|------|----------|
| `-2147467259` | COM接口错误 | 自动重新初始化 |
| `COM` 相关错误 | COM通信问题 | 自动重新初始化 |
| 其他错误 | 一般性错误 | 记录日志，继续处理 |

## 最佳实践

### 1. 定期健康检查
```python
# 在任务执行前检查微信客户端状态
if not wechat.check_wechat_health():
    Logger.warning("微信客户端状态异常，尝试重新初始化")
    wechat.force_reinitialize()
```

### 2. 错误监控
```python
# 监控发送统计
stats = wechat.get_send_stats()
if stats['error_count'] > 10:
    Logger.error("发送错误次数过多，需要检查微信状态")
```

### 3. 优雅降级
```python
# 如果微信发送失败，可以考虑其他通知方式
try:
    wechat.send_message(message, recipient)
except Exception as e:
    Logger.error(f"微信发送失败: {e}")
    # 可以考虑邮件、短信等其他通知方式
```

## 测试

运行测试脚本验证功能：
```bash
python test_wechat_helper_fix.py
```

测试包括：
- 健康检查功能
- 消息发送功能
- 错误处理机制
- 重新初始化功能
- 调试模式

## 注意事项

1. **微信版本**：确保使用兼容的微信版本
2. **窗口状态**：确保微信窗口处于正常状态
3. **网络连接**：确保网络连接稳定
4. **权限设置**：确保程序有足够的权限访问微信

## 故障排除

### 常见问题

1. **COM错误频繁出现**
   - 检查微信版本是否最新
   - 重启微信客户端
   - 检查系统权限

2. **消息发送失败**
   - 检查群聊名称是否正确
   - 确认微信窗口处于活跃状态
   - 检查网络连接

3. **文件发送失败**
   - 检查文件路径是否正确
   - 确认文件格式支持
   - 检查文件大小限制

### 日志分析
查看日志文件中的错误信息：
- `[default_error]`：错误日志
- `[default_info]`：信息日志
- `[default_warning]`：警告日志

通过改进的错误处理机制，`WeChatHelper` 现在能够更好地处理各种异常情况，提高消息发送的成功率和稳定性。 