import streamlit as st
import pandas as pd
import requests
import json

# 检查openpyxl模块
try:
    import openpyxl
except ImportError:
    st.error("缺少openpyxl模块，无法导出Excel文件。请运行: pip install openpyxl")

st.set_page_config(page_title="股票筛选器", layout="centered")
st.title("股票筛选器")

# 配置市场数据服务地址
STOCK_MARKET_SERVICE_URL = "http://localhost:5000"

@st.cache_data(ttl=300)  # 缓存5分钟
def get_stocks_from_service(min_listed_days=90, exclude_st=True, exclude_delisted=True, 
                          exclude_limit_up=True, exclude_suspended=True):
    """从市场数据服务获取股票列表"""
    try:
        params = {
            'min_listed_days': min_listed_days,
            'exclude_st': str(exclude_st).lower(),
            'exclude_delisted': str(exclude_delisted).lower(),
            'exclude_limit_up': str(exclude_limit_up).lower(),
            'exclude_suspended': str(exclude_suspended).lower()
        }
        response = requests.get(f"{STOCK_MARKET_SERVICE_URL}/filtered_stocks", params=params)
        if response.status_code == 200:
            data = response.json()
            # 调试信息
            if data:
                st.write("API返回的数据列名:", list(data[0].keys()))
                st.write("第一条数据:", data[0])
            else:
                st.write("API返回空数据")
            return pd.DataFrame(data)
        else:
            st.error(f"获取股票数据失败: {response.text}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"连接市场数据服务失败: {str(e)}")
        return pd.DataFrame()

# 筛选条件
count = st.number_input("筛选个数", min_value=1, max_value=300, value=20)

conditions = st.multiselect(
    "筛选条件",
    ["按市值升序", "按市值降序", "排除ST", "排除退市", "上交所", "深交所", "创业板", "科创板"],
    default=["按市值降序", "排除ST", "排除退市"]
)

# 从服务获取股票数据
exclude_st = "排除ST" in conditions
exclude_delisted = "排除退市" in conditions

ALL_STOCKS = get_stocks_from_service(
    exclude_st=exclude_st,
    exclude_delisted=exclude_delisted
)

# 筛选逻辑
if ALL_STOCKS.empty:
    st.warning("没有获取到股票数据，请检查市场数据服务是否正在运行")
else:
    filtered = ALL_STOCKS.copy()
    
    # 按交易所筛选
    if "上交所" in conditions:
        filtered = filtered[filtered["市场"] == "SH"]
    if "深交所" in conditions:
        filtered = filtered[filtered["市场"] == "SZ"]
    if "创业板" in conditions:
        filtered = filtered[filtered["股票代码"].str.startswith("300")]
    if "科创板" in conditions:
        filtered = filtered[filtered["股票代码"].str.startswith("688")]
    
    # 按市值排序
    if "市值(亿)" in filtered.columns:
        if "按市值升序" in conditions:
            filtered = filtered.sort_values("市值(亿)", ascending=True)
        elif "按市值降序" in conditions:
            filtered = filtered.sort_values("市值(亿)", ascending=False)
    else:
        st.warning("数据中没有市值信息，无法按市值排序")
    
    # 限制数量
    filtered = filtered.head(count)
    
    # 显示结果
    if not filtered.empty:
        st.dataframe(filtered, use_container_width=True)
        
        # 导出按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("导出为CSV"):
                filtered.to_csv("./output/filtered_stocks.csv", index=False)
                st.success("已导出为 ./output/filtered_stocks.csv")
        with col2:
            if st.button("导出为Excel"):
                try:
                    filtered.to_excel("./output/filtered_stocks.xlsx", index=False)
                    st.success("已导出为 ./output/filtered_stocks.xlsx")
                except ImportError:
                    st.error("缺少openpyxl模块，无法导出Excel文件。请运行: pip install openpyxl")
                except Exception as e:
                    st.error(f"导出Excel文件失败: {str(e)}")
    else:
        st.warning("没有找到符合条件的股票") 