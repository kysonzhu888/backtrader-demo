# coding:utf-8

import datetime
import pandas as pd
import numpy as np
from xtquant import xtdata
import os
import json

def after_init():
    # 获取当前日期
    now_date = datetime.datetime.now().strftime("%Y%m%d")

    # 获取所有A股列表
    ls = xtdata.get_stock_list_in_sector("沪深A股")

    # 获取行情数据
    ticks = xtdata.get_full_tick(ls)

    # 计算市值
    mv_dict = {}
    for i in ticks:
        # 获取总股本
        info = xtdata.get_instrument_detail(i)
        TotalVolume = info["TotalVolume"]
        # 计算当前市值
        mv = TotalVolume * ticks[i]["lastPrice"]
        # 排除停牌
        if ticks[i]["openInt"] == 1:
            continue
        # 排除ST
        if "ST" in info["InstrumentName"]:
            continue
        # 排除未上市
        if str(info["OpenDate"]) <= "19700101":
            continue
        # 记录
        mv_dict[i] = TotalVolume * ticks[i]["lastPrice"]

    # 排序
    sorted_dict = dict(sorted(mv_dict.items(), key=lambda item: item[1]))
    sorted_ls = [i[0] for i in sorted(mv_dict.items(), key=lambda item: item[1])]

    # 取市值最小的50只
    final_ls = sorted_ls[:50]

    # 创建保存目录
    save_dir = "stock_lists"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # 保存股票列表到文件
    save_file = os.path.join(save_dir, f"{now_date}_small_cap_50.json")
    with open(save_file, 'w', encoding='utf-8') as f:
        json.dump({
            'date': now_date,
            'stocks': final_ls,
            'market_values': {stock: mv_dict[stock] for stock in final_ls}
        }, f, ensure_ascii=False, indent=2)

    print(f"小市值50只股票列表已保存到: {save_file}")
    print("股票列表:")
    for i, stock in enumerate(final_ls, 1):
        print(f"{i}. {stock} - 市值: {mv_dict[stock]/100000000:.2f}亿")

    return final_ls

if __name__ == "__main__":
    after_init()
