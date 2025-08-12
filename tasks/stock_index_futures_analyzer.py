#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股指期货净空单量分析器
统计中金所四个股指期货（IH、IF、IM、IC）每日的净空单量变动
"""

import os
import random
import sys
import csv

from time import sleep

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

from environment import group_chat_name_dlb, group_chat_name_vip

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.logger_utils import Logger
from utils.wechat import send_message, send_message_to_multiple_recipients


@dataclass
class PositionData:
    """持仓数据结构"""
    contract: str  # 合约代码
    expiry: str    # 交割月份
    rank: int      # 排名
    broker: str    # 期货公司
    buy_volume: int = 0        # 买单量
    buy_change: int = 0        # 买单变动
    sell_volume: int = 0       # 卖单量
    sell_change: int = 0       # 卖单变动


@dataclass
class ContractSummary:
    """合约汇总数据"""
    contract: str
    zx_buy_total: int = 0      # 中信买单总量
    zx_sell_total: int = 0     # 中信卖单总量
    zx_buy_change: int = 0     # 中信买单变动
    zx_sell_change: int = 0    # 中信卖单变动
    
    others_buy_total: int = 0   # 其他玩家买单总量
    others_sell_total: int = 0  # 其他玩家卖单总量
    others_buy_change: int = 0  # 其他玩家买单变动
    others_sell_change: int = 0 # 其他玩家卖单变动
    
    # 计算属性
    @property
    def zx_net_short(self) -> int:
        """中信净空单（卖单-买单）"""
        return self.zx_sell_total - self.zx_buy_total
    
    @property
    def others_net_short(self) -> int:
        """其他玩家净空单"""
        return self.others_sell_total - self.others_buy_total
    
    @property
    def total_net_short(self) -> int:
        """总净空单"""
        return self.zx_net_short + self.others_net_short
    
    @property
    def zx_net_short_change(self) -> int:
        """中信净空单变动"""
        return self.zx_sell_change - self.zx_buy_change
    
    @property
    def others_net_short_change(self) -> int:
        """其他玩家净空单变动"""
        return self.others_sell_change - self.others_buy_change


class FuturesNetShortAnalyzer:
    """股指期货净空单量分析器"""
    
    # 四个股指期货代码
    CONTRACTS = ['IF', 'IH', 'IC', 'IM']
    
    # 中金所数据URL模板
    URL_TEMPLATE = "http://www.cffex.com.cn/sj/ccpm/{date}/{contract}_1.csv"
    
    # 中信证券的可能名称
    ZX_NAMES = ['中信期货(代客)', '中信证券', '中信期货']
    
    def __init__(self):
        """初始化"""
        self.data_dir = os.path.join(os.path.dirname(__file__), 'futures_data')
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        Logger.info("股指期货净空单量分析器初始化完成")
    
    def generate_urls(self, date: datetime) -> Dict[str, str]:
        """
        生成四个股指期货的下载URL
        
        Args:
            date: 目标日期
            
        Returns:
            Dict[str, str]: 合约代码 -> URL的映射
        """
        date_str = date.strftime("%Y%m%d")
        date_path = date.strftime("%Y%m/%d")
        
        urls = {}
        for contract in self.CONTRACTS:
            urls[contract] = self.URL_TEMPLATE.format(
                date=date_path, 
                contract=contract
            )
        
        Logger.info(f"生成 {date_str} 的URL: {len(urls)} 个合约")
        return urls
    
    def get_target_date(self) -> datetime:
        """
        获取目标日期
        下午5点前使用昨天的数据，5点后使用今天的数据
        周末和节假日需要特殊处理
        """
        now = datetime.now()
        
        if now.hour < 17:  # 下午5点前
            target_date = now - timedelta(days=1)
            Logger.info(f"当前时间{now.strftime('%H:%M')}，使用昨天的数据: {target_date.strftime('%Y-%m-%d')}")
        else:
            target_date = now
            Logger.info(f"当前时间{now.strftime('%H:%M')}，使用今天的数据: {target_date.strftime('%Y-%m-%d')}")
        
        # 检查是否为周末，如果是周末则使用周五的数据
        weekday = target_date.weekday()
        if weekday == 5:  # 周六
            target_date = target_date - timedelta(days=1)
            Logger.info(f"今天是周六，调整为使用周五的数据: {target_date.strftime('%Y-%m-%d')}")
        elif weekday == 6:  # 周日
            target_date = target_date - timedelta(days=2)
            Logger.info(f"今天是周日，调整为使用周五的数据: {target_date.strftime('%Y-%m-%d')}")
        
        return target_date
    
    def download_csv(self, contract: str, url: str, date: datetime) -> Optional[str]:
        """
        下载CSV数据并保存到本地
        
        Args:
            contract: 合约代码
            url: 下载URL
            date: 日期
            
        Returns:
            Optional[str]: 本地文件路径，失败返回None
        """
        date_str = date.strftime("%Y%m%d")
        file_path = os.path.join(self.data_dir, f"{contract}_{date_str}.csv")
        
        try:
            Logger.info(f"开始下载 {contract} 数据: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 保存文件
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            Logger.info(f"{contract} 数据下载成功: {file_path}")
            return file_path
            
        except Exception as e:
            Logger.error(f"下载 {contract} 数据失败: {e}")
            return None
    
    def parse_csv(self, file_path: str) -> List[PositionData]:
        """
        解析CSV文件，提取持仓数据
        
        Args:
            file_path: CSV文件路径
            
        Returns:
            List[PositionData]: 持仓数据列表
        """
        positions = []
        
        try:
            # 尝试多种编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
            file_content = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        file_content = f.readlines()
                    Logger.info(f"成功使用 {encoding} 编码读取文件: {file_path}")
                    break
                except UnicodeDecodeError:
                    continue
            
            if file_content is None:
                Logger.error(f"无法以任何编码读取文件: {file_path}")
                return []
            
            # 跳过前两行表头，处理剩余数据
            if len(file_content) > 2:
                data_lines = file_content[2:]
            else:
                Logger.error(f"文件内容不足: {file_path}")
                return []
            
            # 解析每一行数据
            for line in data_lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 解析CSV行
                row = [col.strip() for col in line.split(',')]
                
                if len(row) < 11:
                    continue
                
                # 解析数据
                try:
                    date = row[0].strip()
                    contract_expiry = row[1].strip()
                    rank = int(row[2].strip()) if row[2].strip() else 0
                    
                    # 提取合约代码和交割月份
                    contract = contract_expiry[:2]
                    expiry = contract_expiry[2:] if len(contract_expiry) > 2 else ""
                    
                    # 买单数据
                    buy_broker = row[6].strip() if len(row) > 6 else ""
                    buy_volume = int(row[7].strip()) if len(row) > 7 and row[7].strip() else 0
                    buy_change = int(row[8].strip()) if len(row) > 8 and row[8].strip() else 0
                    
                    # 卖单数据  
                    sell_broker = row[9].strip() if len(row) > 9 else ""
                    sell_volume = int(row[10].strip()) if len(row) > 10 and row[10].strip() else 0
                    sell_change = int(row[11].strip()) if len(row) > 11 and row[11].strip() else 0
                    
                    # 创建买单持仓数据
                    if buy_broker:
                        positions.append(PositionData(
                            contract=contract,
                            expiry=expiry,
                            rank=rank,
                            broker=buy_broker,
                            buy_volume=buy_volume,
                            buy_change=buy_change
                        ))
                    
                    # 创建卖单持仓数据
                    if sell_broker:
                        positions.append(PositionData(
                            contract=contract,
                            expiry=expiry,
                            rank=rank,
                            broker=sell_broker,
                            sell_volume=sell_volume,
                            sell_change=sell_change
                        ))
                        
                except (ValueError, IndexError) as e:
                    Logger.warning(f"解析行数据失败: {row}, 错误: {e}")
                    continue
            
            Logger.info(f"解析完成: {file_path}, 共 {len(positions)} 条记录")
            return positions
            
        except Exception as e:
            Logger.error(f"解析CSV文件失败: {file_path}, 错误: {e}")
            return []
    
    def analyze_positions(self, all_positions: List[PositionData]) -> Dict[str, ContractSummary]:
        """
        分析持仓数据，按合约汇总
        
        Args:
            all_positions: 所有持仓数据
            
        Returns:
            Dict[str, ContractSummary]: 合约代码 -> 汇总数据的映射
        """
        summaries = {}
        
        for position in all_positions:
            contract = position.contract
            if contract not in summaries:
                summaries[contract] = ContractSummary(contract=contract)
            
            summary = summaries[contract]
            
            # 判断是否为中信
            is_zx = any(zx_name in position.broker for zx_name in self.ZX_NAMES)
            
            if position.buy_volume > 0:  # 买单数据
                if is_zx:
                    summary.zx_buy_total += position.buy_volume
                    summary.zx_buy_change += position.buy_change
                else:
                    summary.others_buy_total += position.buy_volume
                    summary.others_buy_change += position.buy_change
            
            if position.sell_volume > 0:  # 卖单数据
                if is_zx:
                    summary.zx_sell_total += position.sell_volume
                    summary.zx_sell_change += position.sell_change
                else:
                    summary.others_sell_total += position.sell_volume
                    summary.others_sell_change += position.sell_change
        
        Logger.info(f"分析完成: {len(summaries)} 个合约")
        return summaries
    
    def generate_report(self, summaries: Dict[str, ContractSummary], date: datetime) -> str:
        """
        生成分析报告
        
        Args:
            summaries: 合约汇总数据
            date: 分析日期
            
        Returns:
            str: 报告内容
        """
        report_lines = []
        report_lines.append(f"📊 股指期货净空单分析报告")
        report_lines.append(f"📅 日期: {date.strftime('%Y年%m月%d日')}")
        report_lines.append("")
        
        # 中信数据汇总
        zx_total_net_short = 0
        zx_total_change = 0
        zx_details = []
        
        # 其他玩家数据汇总
        others_total_net_short = 0
        others_total_change = 0
        others_details = []
        
        for contract in self.CONTRACTS:
            if contract in summaries:
                summary = summaries[contract]
                
                # 中信数据
                zx_total_net_short += summary.zx_net_short
                zx_total_change += summary.zx_net_short_change
                
                if summary.zx_net_short_change != 0:
                    change_desc = "加空" if summary.zx_net_short_change > 0 else "减空"
                    zx_details.append(f"{contract}{change_desc}{abs(summary.zx_net_short_change)}手")
                
                # 其他玩家数据
                others_total_net_short += summary.others_net_short
                others_total_change += summary.others_net_short_change
                
                if summary.others_net_short_change != 0:
                    change_desc = "加空" if summary.others_net_short_change > 0 else "减空"
                    others_details.append(f"{contract}{change_desc}{abs(summary.others_net_short_change)}手")
        
        # 中信部分
        if zx_total_change != 0:
            zx_change_desc = "加空" if zx_total_change > 0 else "减空"
            report_lines.append(f"🏢 某信，{zx_change_desc}{abs(zx_total_change)}手；")
            if zx_details:
                detail_str = "，".join(zx_details)
                if detail_str:
                    report_lines.append(f"   分别{detail_str}；")
        else:
            report_lines.append(f"🏢 某信，今日持仓无变化；")
        
        # 其他玩家部分
        if others_total_change != 0:
            others_change_desc = "加空" if others_total_change > 0 else "减空"
            report_lines.append(f"👥 其他主要玩家，{others_change_desc}{abs(others_total_change)}手；")
            if others_details:
                detail_str = "，".join(others_details)
                if detail_str:
                    report_lines.append(f"   分别{detail_str}；")
        else:
            report_lines.append(f"👥 其他主要玩家，今日持仓无变化；")
        
        # 总计
        total_net_short = zx_total_net_short + others_total_net_short
        total_change = zx_total_change + others_total_change
        
        report_lines.append("")
        change_desc = "加空" if total_change > 0 else "减空"
        report_lines.append(f"📈 合计{change_desc}{abs(total_change)}手")
        report_lines.append(f"📊 操作完成后，共持有净空单{total_net_short}手")
        
        # 交易建议
        report_lines.append("")
        if total_net_short < 65000:
            report_lines.append("💡 净空单量位于6.5万以下，适合做多")
        elif total_net_short > 110000:
            report_lines.append("💡 净空单量超过11万，适合做空")
        else:
            report_lines.append("💡 净空单量处于中性区间，观望为主")
        
        return "\n".join(report_lines)
    
    def run_analysis(self, retry_count=0, max_retries=3) -> bool:
        """
        运行完整的分析流程，支持重试
        
        Args:
            retry_count: 当前重试次数
            max_retries: 最大重试次数
            
        Returns:
            bool: 是否成功
        """
        try:
            retry_msg = f"重试第{retry_count}次" if retry_count > 0 else ""
            Logger.info(f"开始股指期货净空单量分析...{retry_msg}")
            
            # 1. 确定目标日期
            target_date = self.get_target_date()
            
            # 2. 生成下载URL
            urls = self.generate_urls(target_date)
            
            # 3. 下载CSV数据
            downloaded_files = []
            for contract, url in urls.items():
                file_path = self.download_csv(contract, url, target_date)
                if file_path:
                    downloaded_files.append((contract, file_path))
            
            if not downloaded_files:
                Logger.error("没有成功下载任何数据文件")
                # 尝试重试
                if retry_count < max_retries:
                    Logger.info(f"等待30秒后重试...")
                    import time
                    time.sleep(30)
                    return self.run_analysis(retry_count + 1, max_retries)
                return False
            
            # 4. 解析CSV数据
            all_positions = []
            for contract, file_path in downloaded_files:
                positions = self.parse_csv(file_path)
                all_positions.extend(positions)
            
            if not all_positions:
                Logger.error("没有解析到任何持仓数据")
                return False
            
            # 5. 分析数据
            summaries = self.analyze_positions(all_positions)
            
            # 6. 生成报告
            report = self.generate_report(summaries, target_date)
            
            # 7. 发送微信消息
            success = send_message_to_multiple_recipients(report, [group_chat_name_dlb, group_chat_name_vip])
            if success:
                Logger.info("股指期货净空单分析报告已发送")
            else:
                Logger.warning("发送微信消息失败，但分析完成")
                Logger.info("分析报告内容:")
                Logger.info(report)
            
            # 保存报告到文件
            report_file = os.path.join(self.data_dir, f"report_{target_date.strftime('%Y%m%d')}.txt")
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            Logger.info(f"报告已保存到: {report_file}")
            
            return True
            
        except Exception as e:
            Logger.error(f"分析过程出错: {e}")
            # 尝试重试
            if retry_count < max_retries:
                Logger.info(f"等待30秒后重试...")
                import time
                time.sleep(30)
                return self.run_analysis(retry_count + 1, max_retries)
            return False


def run_stock_index_futures_analysis(first_run=False):
    """
    定时执行股指期货净空单分析
    每天17:00执行
    """
    from threading import Timer
    from datetime import datetime

    # 获取当前时间
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    
    # 首次启动时发送通知
    if first_run:
        startup_msg = f"🚀 股指期货分析器已启动\n⏰ 将在每天17:00自动执行分析\n📍 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
        try:
            send_message(group_chat_name_dlb, startup_msg)
            Logger.info("启动通知已发送到老公老婆群")
        except Exception as e:
            Logger.warning(f"发送启动通知失败: {e}")
    
    if current_hour == 17:  # 每天17:00执行
        Logger.info("股指期货净空单分析任务开始执行...", save_to_file=True)
        
        analyzer = FuturesNetShortAnalyzer()
        success = analyzer.run_analysis()
        
        if success:
            Logger.info("股指期货净空单量分析完成", save_to_file=True)
        else:
            Logger.error("股指期货净空单量分析失败", save_to_file=True)
    else:
        # 计算距离下次执行的时间
        if current_hour < 17:
            hours_to_wait = 17 - current_hour
            minutes_to_wait = -current_minute
        else:
            hours_to_wait = 24 - current_hour + 17
            minutes_to_wait = -current_minute
        
        total_minutes = hours_to_wait * 60 + minutes_to_wait
        Logger.info(f"当前时间 {now.strftime('%H:%M')}，股指期货分析任务将在约{total_minutes}分钟后（17:00）执行")
    
    # 每小时检查一次
    Timer(60 * 60, lambda: run_stock_index_futures_analysis(False)).start()


def main():
    """主函数 - 用于直接测试"""
    sleep(random.randint(1,10))

    analyzer = FuturesNetShortAnalyzer()
    success = analyzer.run_analysis()
    if success:
        Logger.info("股指期货净空单量分析完成")
    else:
        Logger.error("股指期货净空单量分析失败")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        # 守护进程模式
        Logger.info("股指期货净空单分析器启动 - 守护进程模式")
        run_stock_index_futures_analysis(first_run=True)
    else:
        # 直接运行模式（用于测试）
        main()