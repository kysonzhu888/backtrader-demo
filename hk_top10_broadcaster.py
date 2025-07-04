import environment
import os
import threading
import time
import logging
from datetime import datetime, timedelta

import pandas as pd

from date_utils import DateUtils
from wechat_helper import WeChatHelper
from tushare_helper import TushareHelper
from logger_utils import Logger

# 定义目标微信群列表
target_groups = ["投资策略VIP群"]


def broadcast_hk_top10_task():
    """
    实际执行港股通十大成交股获取和播报的任务。
    """
    Logger.info("正在获取港股通十大成交股数据...", save_to_file=False)
    try:
        # 获取当前日期
        current_date = DateUtils.now().strftime('%Y%m%d')
        
        # 获取沪市港股通数据
        sh_data = TushareHelper.ggt_top10(trade_date=current_date, market_type='2')
        # 获取深市港股通数据
        sz_data = TushareHelper.ggt_top10(trade_date=current_date, market_type='4')
        
        # 检查是否获取到数据
        if sh_data is None and sz_data is None:
            Logger.warning("未获取到任何港股通数据", save_to_file=True)
            return
            
        # 处理并发送沪市数据
        if sh_data is not None and not sh_data.empty:
            try:
                sh_message = process_market_data(sh_data, "沪市")
                if sh_message:
                    wechat_helper = WeChatHelper()
                    wechat_helper.send_message(sh_message, target_groups[0])
                    time.sleep(5)  # 发送间隔
            except Exception as e:
                Logger.error(f"处理沪市数据时发生错误: {e}", save_to_file=True)
            
        # 处理并发送深市数据
        if sz_data is not None and not sz_data.empty:
            try:
                sz_message = process_market_data(sz_data, "深市")
                if sz_message:
                    wechat_helper = WeChatHelper()
                    wechat_helper.send_message(sz_message, target_groups[0])
                    time.sleep(5)  # 发送间隔
            except Exception as e:
                Logger.error(f"处理深市数据时发生错误: {e}", save_to_file=True)
            
        # 处理并发送汇总数据
        try:
            summary_message = generate_summary_message(sh_data, sz_data)
            if summary_message:
                for group in target_groups[2:]:
                    wechat_helper = WeChatHelper()
                    wechat_helper.send_message(summary_message, group)
                    time.sleep(5)  # 发送间隔
        except Exception as e:
            Logger.error(f"处理汇总数据时发生错误: {e}", save_to_file=True)
                
    except Exception as e:
        Logger.error(f"获取或播报港股通数据时发生错误: {e}", save_to_file=True)


def process_market_data(data, market_name):
    """
    处理市场数据并生成消息
    
    Args:
        data: DataFrame，包含市场数据
        market_name: str，市场名称（沪市/深市）
        
    Returns:
        str: 格式化后的消息，如果处理失败则返回 None
    """
    try:
        if data is None or data.empty:
            Logger.warning(f"{market_name}数据为空", save_to_file=True)
            return None
            
        # 根据市场类型选择对应的字段
        amount_field = 'sh_amount' if market_name == '沪市' else 'sz_amount'
        net_amount_field = 'sh_net_amount' if market_name == '沪市' else 'sz_net_amount'
            
        # 检查必要的列是否存在
        required_columns = ['trade_date', 'name', 'ts_code', amount_field, net_amount_field]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            Logger.error(f"{market_name}数据缺少必要的列: {missing_columns}", save_to_file=True)
            return None
            
        # 获取交易日期
        trade_date = data['trade_date'].iloc[0] if not data['trade_date'].empty else DateUtils.now().strftime('%Y%m%d')
        
        # 构建消息
        message = f"{market_name}港股通十大成交股 ({trade_date}):\n"
        
        # 处理每一行数据
        for i, (_, row) in enumerate(data.iterrows(), 1):
            try:
                # 检查数值是否有效
                amount = float(row[amount_field]) if pd.notna(row[amount_field]) else 0
                net_amount = float(row[net_amount_field]) if pd.notna(row[net_amount_field]) else 0
                
                # 格式化数值（改为亿元单位）
                amount_str = f"{amount/100000000:.2f}亿" if amount > 0 else "0.00亿"
                net_amount_str = f"{net_amount/100000000:.2f}亿" if net_amount != 0 else "0.00亿"
                
                # 添加行数据
                message += f"{i}. {row['name']}({row['ts_code']}) "
                message += f"成交额: {amount_str} "
                message += f"净买入: {net_amount_str}\n"
            except Exception as e:
                Logger.error(f"处理第{i}行数据时发生错误: {e}", save_to_file=True)
                continue
        
        return message
        
    except Exception as e:
        Logger.error(f"处理{market_name}数据时发生错误: {e}", save_to_file=True)
        return None


def generate_summary_message(sh_data, sz_data):
    """
    生成汇总消息
    
    Args:
        sh_data: DataFrame，沪市数据
        sz_data: DataFrame，深市数据
        
    Returns:
        str: 格式化后的汇总消息，如果处理失败则返回 None
    """
    try:
        # 检查是否有数据
        if (sh_data is None or sh_data.empty) and (sz_data is None or sz_data.empty):
            Logger.warning("没有可用的数据来生成汇总消息", save_to_file=True)
            return None
            
        # 合并数据
        dfs_to_concat = []
        if sh_data is not None and not sh_data.empty:
            # 重命名沪市数据列
            sh_data = sh_data.rename(columns={
                'sh_amount': 'total_amount',
                'sh_net_amount': 'total_net_amount'
            })
            dfs_to_concat.append(sh_data)
            
        if sz_data is not None and not sz_data.empty:
            # 重命名深市数据列
            sz_data = sz_data.rename(columns={
                'sz_amount': 'total_amount',
                'sz_net_amount': 'total_net_amount'
            })
            dfs_to_concat.append(sz_data)
            
        if not dfs_to_concat:
            Logger.warning("没有可用的数据来生成汇总消息", save_to_file=True)
            return None
            
        # 使用列表中的第一个DataFrame作为基础
        all_data = dfs_to_concat[0]
        if len(dfs_to_concat) > 1:
            all_data = pd.concat(dfs_to_concat, ignore_index=True)
                  
        if all_data is None or all_data.empty:
            Logger.warning("合并后的数据为空", save_to_file=True)
            return None
            
        # 检查必要的列
        required_columns = ['name', 'ts_code', 'total_amount', 'total_net_amount']
        missing_columns = [col for col in required_columns if col not in all_data.columns]
        if missing_columns:
            Logger.error(f"汇总数据缺少必要的列: {missing_columns}", save_to_file=True)
            return None
            
        # 按成交额排序
        all_data = all_data.sort_values('total_amount', ascending=False)
        
        # 构建消息
        message = f"港股通十大成交股汇总 ({DateUtils.now().strftime('%Y%m%d')}):\n\n"
        
        # 处理前10名数据
        for i, (_, row) in enumerate(all_data.head(10).iterrows(), 1):
            try:
                # 检查数值是否有效
                amount = float(row['total_amount']) if pd.notna(row['total_amount']) else 0
                net_amount = float(row['total_net_amount']) if pd.notna(row['total_net_amount']) else 0
                
                # 格式化数值（改为亿元单位）
                amount_str = f"{amount/100000000:.2f}亿" if amount > 0 else "0.00亿"
                net_amount_str = f"{net_amount/100000000:.2f}亿" if net_amount != 0 else "0.00亿"
                
                # 添加行数据
                message += f"{i}. {row['name']}({row['ts_code']}) "
                message += f"成交额: {amount_str} "
                message += f"净买入: {net_amount_str}\n"
            except Exception as e:
                Logger.error(f"处理汇总数据第{i}行时发生错误: {e}", save_to_file=True)
                continue
        
        return message
        
    except Exception as e:
        Logger.error(f"生成汇总消息时发生错误: {e}", save_to_file=True)
        return None


def schedule_next_broadcast():
    """
    计算下一次播报的时间并启动 Timer。
    """
    now = DateUtils.now()
    # 计算距离下一个20:15的秒数
    next_time = now.replace(hour=20, minute=15, second=0)
    if now >= next_time:
        next_time = next_time + timedelta(days=1)

    delay_seconds = (next_time - now).total_seconds()

    # 如果是 debug 模式，则立刻执行
    if os.getenv('DEBUG_MODE') == '1':
        delay_seconds = 3

    Logger.info(f"下一次港股通数据播报将在 {delay_seconds:.2f} 秒后执行 ({next_time})...", save_to_file=False)

    # 使用 Timer 调度任务
    threading.Timer(delay_seconds, broadcast_hk_top10_task).start()


# 如何使用这个脚本（示例，直接运行即可启动调度）
if __name__ == "__main__":
    Logger.info("港股通十大成交股播报调度脚本启动...", save_to_file=True)
    # 启动第一次调度
    schedule_next_broadcast()
