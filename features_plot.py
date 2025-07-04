import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager

# 1. 设置字体路径（确保路径真实存在）
font_path = "/System/Library/Fonts/STHeiti Medium.ttc"  # macOS 自带中文字体
# 或者使用其他已安装的字体（如 PingFang）
# font_path = "/System/Library/Fonts/PingFang.ttc"

# 2. 添加字体到 Matplotlib 字体管理器
font_prop = font_manager.FontProperties(fname=font_path)
font_manager.fontManager.addfont(font_path)

# 3. 设置全局字体（需用字体的内部名称，而非文件名）
plt.rcParams['font.family'] = font_prop.get_name()
# 解决负号显示问题
plt.rcParams['axes.unicode_minus'] = False

# ----------------------------
# 1. 准备数据（替换为您的实际数据）
# ----------------------------
data = {
    "品种名称": [
        "氧化铝", "沪铝", "烧碱", "国际铜", "LPG", "沪铜", "豆一",
        "PTA", "塑料", "螺纹钢", "热卷", "甲醇", "合成橡胶", "豆二",
        "棉花", "豆粕", "焦炭", "白糖", "菜油", "菜粕", "PVC", "沥青",
        "棕榈油", "低硫燃油", "燃油", "焦煤", "原油", "纯碱", "玻璃", "纸浆"
    ],
    "涨跌幅": [
        3.74, 0.60, 0.58, 0.25, 0.23, 0.19, 0.17,
        -0.40, -0.41, -0.42, -0.44, -0.52, -0.53, -0.61,
        -0.62, -0.67, -0.68, -0.69, -0.70, -0.81, -0.83,
        -0.84, -0.96, -1.20, -1.41, -1.71, -2.07, -2.26, -2.60, -3.05
    ]
}

df = pd.DataFrame(data)
df = df.sort_values(by="涨跌幅", ascending=False)  # 按涨跌幅从高到低排序

# ----------------------------
# 2. 绘制柱状图
# ----------------------------
plt.figure(figsize=(10, 12))  # 设置画布大小（宽度，高度）

# 定义颜色（涨红跌绿）
colors = ['#ff4444' if x >= 0 else '#33aa33' for x in df['涨跌幅']]

# 绘制横向柱状图
bars = plt.barh(
    y=df['品种名称'],
    width=df['涨跌幅'],
    color=colors,
    height=0.6  # 控制柱子粗细
)

# 添加数据标签
for bar in bars:
    width = bar.get_width()
    label_x = width if width > 0 else width - 0.5  # 调整标签位置
    plt.text(
        label_x,
        bar.get_y() + bar.get_height()/2,
        f'{width:.2f}%',
        va='center',
        ha='left' if width < 0 else 'right',
        fontsize=10
    )

# ----------------------------
# 3. 美化图表
# ----------------------------
plt.title("国内期市夜盘涨跌幅", fontsize=14, pad=20)
plt.xlabel("涨跌幅 (%)", fontsize=12)
plt.grid(axis='x', linestyle='--', alpha=0.6)  # 添加横向网格线

# 调整坐标轴
plt.axvline(0, color='gray', linewidth=0.8)  # 零线
plt.xlim(-4, 4)  # 控制横轴范围（根据数据最大值调整）
plt.xticks(fontsize=10)
plt.yticks(fontsize=10, rotation=0)  # 品种名称不旋转

# 隐藏边框
for spine in ['top', 'right', 'bottom']:
    plt.gca().spines[spine].set_visible(False)

plt.tight_layout()  # 自动调整间距
plt.savefig('output.png')
# plt.show()