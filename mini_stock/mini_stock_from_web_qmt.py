# coding:utf-8

import datetime
import pandas as pd
import numpy as np


def after_init(C):
    # 取当天日期
    now_date = datetime.datetime.now().strftime("%Y%m%d")
    # 获取沪深A股列表
    ls = get_stock_list_in_sector(
        "沪深A股")  # 文档地址https://dict.thinktrader.net/innerApi/data_function.html?id=7zqjlm#contextinfo-get-stock-list-in-sector-%E8%8E%B7%E5%8F%96%E6%9D%BF%E5%9D%97%E6%88%90%E4%BB%BD%E8%82%A1

    # print(ls)
    ticks = C.get_full_tick(
        ls)  # 文档地址https://dict.thinktrader.net/innerApi/data_function.html?id=7zqjlm#contextinfo-get-full-tick-%E8%8E%B7%E5%8F%96%E5%85%A8%E6%8E%A8%E6%95%B0%E6%8D%AE

    # 计算市值
    mv_dict = {}
    for i in ticks:
        # 取流通股本
        info = C.get_instrument_detail(
            i)  # 文档地址https://dict.thinktrader.net/innerApi/data_function.html?id=7zqjlm#contextinfo-get-instrumentdetail-%E6%A0%B9%E6%8D%AE%E4%BB%A3%E7%A0%81%E8%8E%B7%E5%8F%96%E5%90%88%E7%BA%A6%E8%AF%A6%E7%BB%86%E4%BF%A1%E6%81%AF
        TotalVolumn = info["TotalVolumn"]
        # 计算当日市值
        mv = TotalVolumn * ticks[i]["lastPrice"]
        # 过滤停牌
        if ticks[i]["openInt"] == 1:
            continue
        # 过滤ST
        if "ST" in info["InstrumentName"]:
            continue
        # 过滤退市
        if "退市" in info["InstrumentName"]:
            continue
            if "退" in info["InstrumentName"]:
        continue
    # 过滤未上市
    if str(info["OpenDate"]) <= "19700101":
        continue
    # 记录
    mv_dict[i] = TotalVolumn * ticks[i]["lastPrice"]


# 排序
sorted_dict = dict(sorted(mv_dict.items(), key=lambda item: item[1]))
sorted_ls = [i[0] for i in sorted(mv_dict.items(), key=lambda item: item[1])]

print(sorted_ls)
# 取出市值最小的50只
final_ls = sorted_ls[:50]

# sector=create_sector('我的','新建板块',False)
sector = create_sector('我的', f'{now_date}小市值50只',
                       False)  # 文档地址https://dict.thinktrader.net/innerApi/system_function.html?id=7zqjlm#create-sector-%E5%88%9B%E5%BB%BA%E6%9D%BF%E5%9D%97
reset_sector_stock_list(f'{now_date}小市值50只',
                        final_ls)  # 文档地址https://dict.thinktrader.net/innerApi/system_function.html?id=7zqjlm#reset-sector-stock-list-%E8%AE%BE%E7%BD%AE%E6%9D%BF%E5%9D%97%E6%88%90%E5%88%86%E8%82%A1

return