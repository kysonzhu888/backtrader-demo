
# 🚀 量化交易策略集成平台

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-success.svg)]()

> 佛祖保佑，永无 bug 🙏

## 📖 项目简介

这是一个综合性量化交易策略平台，集成了多种交易策略、数据分析工具和自动化任务系统。项目采用模块化设计，每个策略都是独立的子模块，支持实时监控、自动报告生成和微信群消息推送。

### 🎯 核心特性

- **多策略集成**：Pinbar、动力波、跟着国家队、微盘股等多种策略
- **实时监控**：支持期货、股票实时数据监控和信号提醒  
- **自动报告**：每日/周/月自动生成期货分析报告
- **微信推送**：重要信号和报告自动推送到微信群
- **守护进程**：daemon.py确保所有任务稳定运行
- **数据可视化**：支持图表生成和Dashboard展示

---

## 📁 项目结构

```
backtrader-demo/
├── 📂 tasks/                    # 定时任务模块
│   ├── stock_index_futures_analyzer.py  # 股指期货净空单分析
│   ├── news_reporter.py         # 早间新闻播报
│   ├── features_daily_report.py # 期货日报
│   ├── weather_report.py        # 天气播报
│   └── futures_data/            # 期货数据存储
├── 📂 power_wave_strategy/      # 动力波策略
├── 📂 pinbar_strategy/          # Pinbar策略  
├── 📂 mini_stock/               # 微盘股策略
├── 📂 monitor/                  # 实时监控模块
├── 📂 dashboard/                # Web Dashboard
├── 📂 utils/                    # 工具函数
├── daemon.py                    # 守护进程管理器
├── task_scheduler.py            # 任务调度器(简化中)
└── environment.example.py       # 环境配置模板
```

---

## 🔧 快速开始

### 1️⃣ 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd backtrader-demo

# 安装Python依赖
pip install -r requirements.txt

# macOS额外依赖（用于声音提醒）
brew install mpg321

# Windows用户需要安装微信自动化依赖
pip install wxauto>=3.9.11.17.5
```

### 2️⃣ 配置设置

```bash
# 复制配置模板
cp environment.example.py environment.py

# 编辑配置文件，填入真实的API密钥和群名称
vim environment.py
```

配置示例：
```python
# Tushare API Token（必需）
tushare_token = 'YOUR_TUSHARE_API_TOKEN_HERE'

# 微信群名称配置
group_chat_name_vip = "投资策略VIP群"
group_chat_name_dlb = "动力波策略群"
```

### 3️⃣ 启动系统

```bash
# 方式1：启动完整的守护进程系统（推荐）
python daemon.py

# 方式2：单独运行某个策略（用于测试）
python tasks/stock_index_futures_analyzer.py
python power_wave_strategy/pow_wave_strategy.py
```

---

## 📊 策略模块详解

### 🎯 1. Pinbar反转策略
> **实时监控商品期货关键反转信号**

**策略原理**：
- 识别长影线（占2/3以上）+ 小实体（不超过1/3）的K线模式
- 结合支撑/阻力位确认反转信号
- 盈亏比常达2:1以上，止损明确

**核心优势**：
- ✅ 简单直观，无需复杂指标
- ✅ 高效精准，结合关键位反转信号强
- ✅ 灵活普适，适用于多个市场
- ✅ 实时监控，关键时点自动提醒

**使用方式**：
```bash
# 启动Pinbar实时监控
python pinbar_strategy/pinbar_strategy.py

# 加载历史数据
python pinbar_strategy/features_min_loader.py

# 或直接启动守护进程（推荐）
python daemon.py
```

**重要提醒**：单根 Pinbar 不足以构成交易信号，建议结合多重确认，成功率更高。


### ⚡ 2. 动力波策略
> **基于波段趋势的智能交易系统**

**策略公式**（通达信语言）：
```
VARA:=(2*CLOSE+HIGH+LOW)/4;
VARB:=LLV(LOW,34);
VARC:=HHV(HIGH,34);
VARD:=EMA((VARA-VARB)/(VARC-VARB)*100,13);
VARE:=EMA(0.667*REF(VARD,1)+0.333*VARD,2);
STICKLINE(VARD-VARE > 0,VARD,VARE,8,0),COLORRED;
STICKLINE(VARD-VARE < 0,VARD,VARE,8,0),COLOR00FF0F;
生命:EMA(VARE,10), COLORGRAY;
强弱分界线:50;
顶:80;
底:20;
```

**核心功能**：
- 📈 **波段趋势判断**：生命线（灰色）代表波段方向
- 💪 **市场强弱分析**：以50为分界线，分为强(50~80)、超强(>80)、弱(20~50)、超弱(<20)
- 🔄 **持仓信号**：红柱持股阶段，绿柱持币阶段
- 🎯 **转折点捕捉**：
  - 买入信号：生命线20下方转平向上 + 红柱站上生命线
  - 卖出信号：生命线80下方转平向下 + 绿柱跌破生命线

**使用方式**：
```bash
# 启动动力波策略
python power_wave_strategy/pow_wave_strategy.py

# 或使用守护进程（推荐）
python daemon.py
```

### 🏛️ 3. 跟着国家队策略
> **跟踪机构资金流向的聪明钱策略**

**策略原理**：通过监控大资金（国家队、机构）的持仓变化，跟随聪明钱的投资方向。

**技术要求**：
- 安装迅投交易软件
- 配置实时数据源

**使用方式**：
```bash
# 启动国家队资金监控
python if_amount_realtime.py
```

### 💎 4. 微盘股策略
> **持有市值最小300只股票的轮动策略**

**策略逻辑**：
- 🎯 **选股标准**：市值最小的300只股票（剔除ST、退市股、涨停股）
- 🔄 **调仓周期**：30天调仓一次
- 💡 **盈利原理**：
  1. A股小市值股容易被炒作，经常出现连续涨停
  2. 高抛低吸逻辑：涨上去超过300名卖出，跌下来进入前300买入

**风险提示**：追高必死，低位买入守株待兔式操作长期大概率盈利。

**使用方式**：
```bash
# 初始化股票列表
python mini_stock/ministock_strategy.py

# 查看每日收益
python mini_stock/ministock_performance_reporter.py

# 每日调仓更新
python mini_stock/MiniStockUpdateReporter.py
```

---

## 🤖 自动化任务调度

| 任务名称 | 执行时间 | 频率 | 功能说明 |
|---------|---------|------|----------|
| 📰 早间新闻播报 | 08:05 | 每日 | 推送当日重要财经新闻 |
| 📊 期货日报 | 08:38 | 每日 | 期货市场日度分析报告 |
| 📈 期货周报 | 周一 07:25 | 每周 | 期货市场周度趋势分析 |
| 📋 期货月报 | 1号 07:30 | 每月 | 期货市场月度总结报告 |
| 🧹 数据库清理 | 02:00 | 每日 | 清理过期数据和日志文件 |
| ⚡ 股指期货分析 | 17:00 | 每日 | 分析股指期货净空单变化 |
| 📱 分钟级监控 | - | 每5分钟 | 实时监控期货价格异动 |

---

## 📬 微信集成

项目支持自动化微信群消息推送功能：

- **📱 wxauto库**：Windows平台微信自动化
- **🔔 实时提醒**：重要信号和报告自动推送
- **👥 多群支持**：支持不同策略推送到不同群组
- **📊 富文本**：支持图表、表格等多媒体消息

配置示例：
```python
group_chat_name_vip = "投资策略VIP群"      # VIP群
group_chat_name_dlb = "动力波策略群"       # 动力波群
group_chat_name_monitor = "老公老婆"       # 监控群
```

---

## 🌐 Web Dashboard

项目包含Web仪表板界面，提供：
- 📊 **实时监控**：策略运行状态和信号展示
- 📈 **图表分析**：K线图、指标图表可视化
- ⚙️ **参数配置**：在线调整策略参数
- 📱 **移动适配**：支持手机端访问

访问地址：`http://localhost:5000/dashboard`

---

## 🛠️ 环境配置设置

### 首次部署配置

1. **复制环境配置模板**：
   ```bash
   cp environment.example.py environment.py
   ```

2. **编辑环境配置**：
   打开 `environment.py` 文件，填入实际的API密钥和配置：
   ```python
   # 替换为你的实际API密钥
   tushare_token = 'YOUR_ACTUAL_TUSHARE_TOKEN'
   
   # 根据实际情况修改微信群名称
   group_chat_name_vip = "你的投资群名称"
   group_chat_name_dlb = "你的策略群名称"
   ```

3. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

### ⚠️ 重要提醒

- `environment.py` 包含敏感信息（API密钥等），已被 `.gitignore` 排除，不会提交到git
- 数据文件目录（如 `tasks/futures_data/`、`reports/` 等）已被忽略，不会提交到git
- 测试文件和调试文件（`test_*.py`、`debug_*.py`）已被忽略

---

## 🐛 故障排除

### 常见问题

**1. 微信自动化失败**
```bash
# Windows用户安装wxauto
pip install wxauto>=3.9.11.17.5

# 确保微信客户端已登录
# 检查群名称是否正确配置
```

**2. Tushare API调用失败**
```python
# 检查API token是否有效
# 确认API调用频率限制
# 验证网络连接
```

**3. 守护进程异常退出**
```bash
# 查看日志文件
tail -f daemon.log

# 重启守护进程
python daemon.py
```

**4. 数据库连接问题**
```bash
# 检查SQLite数据库权限
# 清理损坏的数据库文件
rm -f *.db && python init_db.py
```

---

## ⚠️ 风险提醒

> **免责声明**：本项目仅供学习和研究使用，不构成任何投资建议。

- 📊 **历史业绩不代表未来表现**
- 💰 **投资有风险，入市需谨慎**
- 🔄 **建议充分回测后再实盘使用**
- ⚖️ **请遵守相关法律法规**
- 🛡️ **注意保护个人隐私和资金安全**

---

## 📜 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🤝 贡献指南

欢迎提交问题和改进建议！

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

---

## 📞 联系我们

如有问题或建议，请通过以下方式联系：

- 📧 **邮箱**：联系项目维护者
- 💬 **微信群**：加入项目交流群
- 🐛 **Issues**：[GitHub Issues](https://github.com/your-repo/issues)

---

<div align="center">
  <p>💝 如果这个项目对你有帮助，请给个 Star ⭐</p>
  <p>🙏 感谢所有贡献者和支持者</p>
  <p>📈 祝投资顺利，财源广进！</p>
</div>
