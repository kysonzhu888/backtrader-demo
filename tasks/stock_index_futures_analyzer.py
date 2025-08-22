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
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

from environment import group_chat_name_dlb, group_chat_name_vip

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.logger_utils import Logger
from utils.wechat import send_message, send_message_to_multiple_recipients


@dataclass
class FuturesAnalyzerConfig:
    """股指期货分析器配置"""
    
    # 运行时间配置
    scheduled_hour: int = 16  # 每天运行的小时（24小时制）
    scheduled_minute: int = 0  # 每天运行的分钟
    check_interval_minutes: int = 60  # 检查间隔（分钟）
    
    # 数据切换时间配置
    data_switch_hour: int = 16  # 下午几点后使用今天的数据（否则用昨天的）
    
    # 网络配置
    connection_timeout: int = 10  # 连接超时（秒）
    read_timeout: int = 20  # 读取超时（秒）
    max_download_retries: int = 3  # 单个文件最大重试次数
    max_analysis_retries: int = 3  # 整体分析最大重试次数
    retry_wait_seconds: int = 60  # 重试等待时间（秒）
    
    # 文件配置
    min_file_size_bytes: int = 1000  # 有效文件最小大小（字节）
    data_dir_name: str = 'futures_data'  # 数据目录名
    
    # 分析配置
    low_threshold: int = 65000   # 净空单量低阈值（适合做多）
    high_threshold: int = 110000  # 净空单量高阈值（适合做空）
    
    # 微信通知配置
    enable_startup_notification: bool = True  # 是否发送启动通知
    enable_error_notification: bool = True   # 是否发送错误通知
    
    # 合约配置
    contracts: list = field(default_factory=lambda: ['IF', 'IH', 'IC', 'IM'])
    
    # URL配置
    base_url: str = "http://www.cffex.com.cn"
    url_template: str = "http://www.cffex.com.cn/sj/ccpm/{date}/{contract}_1.csv"
    
    # 中信证券名称匹配
    zx_names: list = field(default_factory=lambda: ['中信期货(代客)', '中信证券', '中信期货'])
    
    def get_scheduled_time_str(self) -> str:
        """获取计划执行时间的字符串表示"""
        return f"{self.scheduled_hour:02d}:{self.scheduled_minute:02d}"
    
    def is_scheduled_time(self, hour: int, minute: int = None) -> bool:
        """检查是否为计划执行时间"""
        if minute is None:
            return hour == self.scheduled_hour
        return hour == self.scheduled_hour and minute == self.scheduled_minute


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
    
    def __init__(self, config: FuturesAnalyzerConfig = None):
        """初始化"""
        self.config = config or FuturesAnalyzerConfig()
        self.data_dir = os.path.join(os.path.dirname(__file__), self.config.data_dir_name)
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        # 创建带有重试策略的requests session
        self.session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        # 配置HTTP适配器
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        Logger.info("股指期货净空单量分析器初始化完成")
    
    def test_connection(self) -> bool:
        """
        测试网络连接到中金所官网
        
        Returns:
            bool: 连接是否成功
        """
        try:
            Logger.info("测试网络连接到中金所官网...")
            response = self.session.get(
                self.config.base_url, 
                timeout=(5, 10),
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            if response.status_code == 200:
                Logger.info("网络连接正常")
                return True
            else:
                Logger.warning(f"网络连接异常，状态码: {response.status_code}")
                return False
        except Exception as e:
            Logger.warning(f"网络连接测试失败: {e}")
            return False
    
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
        for contract in self.config.contracts:
            urls[contract] = self.config.url_template.format(
                date=date_path, 
                contract=contract
            )
        
        Logger.info(f"生成 {date_str} 的URL: {len(urls)} 个合约")
        return urls
    
    def get_target_date(self) -> datetime:
        """
        获取目标日期
        下午4点前使用昨天的数据，4点后使用今天的数据
        周末和节假日需要特殊处理
        """
        now = datetime.now()
        
        if now.hour < self.config.data_switch_hour:  # 配置的时间点前
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
    
    def download_csv(self, contract: str, url: str, date: datetime, retry_count: int = 0) -> Optional[str]:
        """
        下载CSV数据并保存到本地，支持重试
        
        Args:
            contract: 合约代码
            url: 下载URL
            date: 日期
            retry_count: 当前重试次数
            
        Returns:
            Optional[str]: 本地文件路径，失败返回None
        """
        date_str = date.strftime("%Y%m%d")
        file_path = os.path.join(self.data_dir, f"{contract}_{date_str}.csv")
        max_retries = self.config.max_download_retries
        
        # 如果文件已存在且不是今天的文件，直接使用
        if os.path.exists(file_path) and date.date() != datetime.now().date():
            Logger.info(f"{contract} 使用已存在的历史数据: {file_path}")
            return file_path
        
        # 如果是今天的文件且已存在且大小合理，也可以使用（避免重复下载）
        if os.path.exists(file_path) and date.date() == datetime.now().date():
            file_size = os.path.getsize(file_path)
            if file_size > self.config.min_file_size_bytes:  # 文件大小超过配置值认为是有效的
                Logger.info(f"{contract} 使用已存在的今日数据: {file_path} ({file_size}字节)")
                return file_path
        
        try:
            retry_msg = f"(重试第{retry_count}次)" if retry_count > 0 else ""
            Logger.info(f"开始下载 {contract} 数据{retry_msg}: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            # 使用配置的超时时间
            response = self.session.get(
                url, 
                headers=headers, 
                timeout=(self.config.connection_timeout, self.config.read_timeout),
                allow_redirects=True
            )
            response.raise_for_status()
            
            # 检查响应内容
            if len(response.content) < 100:
                raise Exception(f"响应内容太短({len(response.content)}字节)，可能是错误页面")
            
            # 保存文件
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            Logger.info(f"{contract} 数据下载成功: {file_path} ({len(response.content)}字节)")
            return file_path
            
        except requests.exceptions.Timeout as e:
            Logger.warning(f"下载 {contract} 数据超时: {e}")
            # 超时重试
            if retry_count < max_retries:
                sleep_time = min(10 + retry_count * 5, 30)  # 递增等待时间
                Logger.info(f"等待{sleep_time}秒后重试...")
                sleep(sleep_time)
                return self.download_csv(contract, url, date, retry_count + 1)
            
        except requests.exceptions.ConnectionError as e:
            Logger.warning(f"下载 {contract} 数据连接错误: {e}")
            # 连接错误重试
            if retry_count < max_retries:
                sleep_time = min(15 + retry_count * 10, 60)  # 更长的等待时间
                Logger.info(f"网络连接问题，等待{sleep_time}秒后重试...")
                sleep(sleep_time)
                return self.download_csv(contract, url, date, retry_count + 1)
                
        except Exception as e:
            Logger.error(f"下载 {contract} 数据失败: {e}")
            # 其他错误重试
            if retry_count < max_retries:
                sleep_time = min(5 + retry_count * 5, 20)
                Logger.info(f"等待{sleep_time}秒后重试...")
                sleep(sleep_time)
                return self.download_csv(contract, url, date, retry_count + 1)
            
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
            is_zx = any(zx_name in position.broker for zx_name in self.config.zx_names)
            
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
        
        for contract in self.config.contracts:
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
        if total_net_short < self.config.low_threshold:
            report_lines.append(f"💡 净空单量位于{self.config.low_threshold/10000:.1f}万以下，适合做多")
        elif total_net_short > self.config.high_threshold:
            report_lines.append(f"💡 净空单量超过{self.config.high_threshold/10000:.1f}万，适合做空")
        else:
            report_lines.append("💡 净空单量处于中性区间，观望为主")
        
        return "\n".join(report_lines)
    
    def _send_error_notification(self, error_message: str):
        """
        发送错误通知到微信
        
        Args:
            error_message: 错误消息
        """
        if not self.config.enable_error_notification:
            return
            
        try:
            success = send_message_to_multiple_recipients(error_message, [group_chat_name_dlb, group_chat_name_vip])
            if success:
                Logger.info("错误通知已发送到微信")
            else:
                Logger.warning("发送错误通知到微信失败")
        except Exception as e:
            Logger.error(f"发送错误通知异常: {e}")
    
    def run_analysis(self, retry_count=0, max_retries=None) -> bool:
        """
        运行完整的分析流程，支持重试
        
        Args:
            retry_count: 当前重试次数
            max_retries: 最大重试次数（None时使用配置值）
            
        Returns:
            bool: 是否成功
        """
        if max_retries is None:
            max_retries = self.config.max_analysis_retries
            
        try:
            retry_msg = f"重试第{retry_count}次" if retry_count > 0 else ""
            Logger.info(f"开始股指期货净空单量分析...{retry_msg}")
            
            # 0. 测试网络连接（仅首次尝试时测试）
            if retry_count == 0:
                if not self.test_connection():
                    Logger.warning("网络连接测试失败，但仍尝试继续执行...")
            
            # 1. 确定目标日期
            target_date = self.get_target_date()
            
            # 2. 生成下载URL
            urls = self.generate_urls(target_date)
            
            # 3. 下载CSV数据
            downloaded_files = []
            failed_contracts = []
            
            for contract, url in urls.items():
                file_path = self.download_csv(contract, url, target_date)
                if file_path:
                    downloaded_files.append((contract, file_path))
                else:
                    failed_contracts.append(contract)
            
            # 检查下载结果
            if not downloaded_files:
                error_msg = "所有合约数据下载失败"
                Logger.error(error_msg)
                # 发送失败通知
                self._send_error_notification(f"❌ 股指期货分析失败\n{error_msg}\n日期: {target_date.strftime('%Y-%m-%d')}")
                # 尝试重试
                if retry_count < max_retries:
                    Logger.info(f"等待{self.config.retry_wait_seconds}秒后重试...")
                    import time
                    time.sleep(self.config.retry_wait_seconds)
                    return self.run_analysis(retry_count + 1, max_retries)
                return False
            elif failed_contracts:
                error_msg = f"部分合约下载失败: {failed_contracts}"
                Logger.error(error_msg)
                # 发送失败通知
                self._send_error_notification(f"⚠️ 股指期货分析部分失败\n{error_msg}\n成功下载: {[c for c, _ in downloaded_files]}\n日期: {target_date.strftime('%Y-%m-%d')}")
                return False
            else:
                Logger.info(f"所有合约数据下载成功: {[c for c, _ in downloaded_files]}")
            
            # 4. 解析CSV数据
            all_positions = []
            for contract, file_path in downloaded_files:
                positions = self.parse_csv(file_path)
                all_positions.extend(positions)
            
            if not all_positions:
                error_msg = "没有解析到任何持仓数据"
                Logger.error(error_msg)
                # 发送失败通知
                self._send_error_notification(f"❌ 股指期货分析失败\n{error_msg}\n日期: {target_date.strftime('%Y-%m-%d')}")
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
            error_msg = f"分析过程出错: {e}"
            Logger.error(error_msg)
            # 发送失败通知
            try:
                self._send_error_notification(f"❌ 股指期货分析异常\n{error_msg}\n重试次数: {retry_count}/{max_retries}")
            except:
                pass  # 避免通知发送失败影响重试逻辑
            # 尝试重试
            if retry_count < max_retries:
                Logger.info(f"等待{self.config.retry_wait_seconds}秒后重试...")
                import time
                time.sleep(self.config.retry_wait_seconds)
                return self.run_analysis(retry_count + 1, max_retries)
            return False


def run_stock_index_futures_analysis(config: FuturesAnalyzerConfig = None, first_run=False):
    """
    定时执行股指期货净空单分析
    
    Args:
        config: 分析器配置，None时使用默认配置
        first_run: 是否为首次运行
    """
    from threading import Timer
    from datetime import datetime

    if config is None:
        config = FuturesAnalyzerConfig()

    # 获取当前时间
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    
    # 首次启动时发送通知
    if first_run and config.enable_startup_notification:
        startup_msg = f"🚀 股指期货分析器已启动\n⏰ 将在每天{config.get_scheduled_time_str()}自动执行分析\n📍 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
        try:
            send_message(group_chat_name_dlb, startup_msg)
            Logger.info("启动通知已发送到老公老婆群")
        except Exception as e:
            Logger.warning(f"发送启动通知失败: {e}")
    
    if config.is_scheduled_time(current_hour):  # 配置的时间执行
        Logger.info("股指期货净空单分析任务开始执行...", save_to_file=True)
        
        analyzer = FuturesNetShortAnalyzer(config)
        success = analyzer.run_analysis()
        
        if success:
            Logger.info("股指期货净空单量分析完成", save_to_file=True)
        else:
            Logger.error("股指期货净空单量分析失败", save_to_file=True)
    else:
        # 计算距离下次执行的时间
        scheduled_hour = config.scheduled_hour
        if current_hour < scheduled_hour:
            hours_to_wait = scheduled_hour - current_hour
            minutes_to_wait = -current_minute
        else:
            hours_to_wait = 24 - current_hour + scheduled_hour
            minutes_to_wait = -current_minute
        
        total_minutes = hours_to_wait * 60 + minutes_to_wait
        Logger.info(f"当前时间 {now.strftime('%H:%M')}，股指期货分析任务将在约{total_minutes}分钟后（{config.get_scheduled_time_str()}）执行")
    
    # 使用配置的检查间隔
    check_interval = config.check_interval_minutes * 60
    Timer(check_interval, lambda: run_stock_index_futures_analysis(config, False)).start()


def main():
    """主函数 - 用于直接测试"""
    sleep(random.randint(1,20))

    # 可以在这里自定义配置，例如：
    # config = FuturesAnalyzerConfig()
    # config.scheduled_hour = 15  # 改为15点执行
    # config.low_threshold = 70000  # 调整阈值
    
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