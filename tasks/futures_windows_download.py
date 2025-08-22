#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
使用Windows系统工具下载中金所数据
通过PowerShell或curl命令绕过Python网络限制
"""

import os
import subprocess
import platform
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def download_with_powershell(url: str, output_file: str) -> bool:
    """
    使用PowerShell下载文件（Windows）
    """
    if platform.system() != 'Windows':
        logger.error("PowerShell仅在Windows系统可用")
        return False
    
    try:
        # PowerShell命令
        ps_command = f'''
        $headers = @{{
            "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            "Accept" = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            "Accept-Language" = "zh-CN,zh;q=0.9"
            "Referer" = "http://www.cffex.com.cn/"
        }}
        
        try {{
            Invoke-WebRequest -Uri "{url}" -OutFile "{output_file}" -Headers $headers -TimeoutSec 30
            Write-Host "Success"
        }} catch {{
            Write-Host "Failed: $_"
            exit 1
        }}
        '''
        
        logger.info(f"使用PowerShell下载: {url}")
        result = subprocess.run(
            ['powershell', '-Command', ps_command],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0 and os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            if file_size > 100:
                logger.info(f"✅ PowerShell下载成功: {output_file} ({file_size} bytes)")
                return True
        
        logger.error(f"PowerShell下载失败: {result.stderr}")
        return False
        
    except Exception as e:
        logger.error(f"PowerShell执行错误: {e}")
        return False


def download_with_curl(url: str, output_file: str) -> bool:
    """
    使用curl命令下载文件（跨平台）
    """
    try:
        curl_command = [
            'curl',
            '-L',  # 跟随重定向
            '-o', output_file,
            '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            '-H', 'Accept-Language: zh-CN,zh;q=0.9',
            '-H', 'Referer: http://www.cffex.com.cn/',
            '--connect-timeout', '30',
            '--max-time', '60',
            url
        ]
        
        logger.info(f"使用curl下载: {url}")
        result = subprocess.run(curl_command, capture_output=True, text=True, timeout=90)
        
        if result.returncode == 0 and os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            if file_size > 100:
                logger.info(f"✅ curl下载成功: {output_file} ({file_size} bytes)")
                return True
        
        logger.error(f"curl下载失败: {result.stderr}")
        return False
        
    except FileNotFoundError:
        logger.error("curl命令未找到，请安装curl")
        return False
    except Exception as e:
        logger.error(f"curl执行错误: {e}")
        return False


def download_with_wget(url: str, output_file: str) -> bool:
    """
    使用wget命令下载文件
    """
    try:
        wget_command = [
            'wget',
            '-O', output_file,
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            '--header=Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            '--header=Accept-Language: zh-CN,zh;q=0.9',
            '--header=Referer: http://www.cffex.com.cn/',
            '--timeout=30',
            '--tries=3',
            url
        ]
        
        logger.info(f"使用wget下载: {url}")
        result = subprocess.run(wget_command, capture_output=True, text=True, timeout=90)
        
        if result.returncode == 0 and os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            if file_size > 100:
                logger.info(f"✅ wget下载成功: {output_file} ({file_size} bytes)")
                return True
        
        logger.error(f"wget下载失败: {result.stderr}")
        return False
        
    except FileNotFoundError:
        logger.error("wget命令未找到")
        return False
    except Exception as e:
        logger.error(f"wget执行错误: {e}")
        return False


def download_all_contracts():
    """
    下载所有合约数据
    """
    now = datetime.now()
    date_path = now.strftime("%Y%m/%d")
    date_str = now.strftime("%Y%m%d")
    
    # 创建下载目录
    download_dir = os.path.join(os.path.dirname(__file__), 'futures_data')
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    
    contracts = ['IF', 'IH', 'IC', 'IM']
    success_count = 0
    
    # 根据系统选择下载方法
    system = platform.system()
    logger.info(f"当前系统: {system}")
    
    for contract in contracts:
        url = f"http://www.cffex.com.cn/sj/ccpm/{date_path}/{contract}_1.csv"
        output_file = os.path.join(download_dir, f"{contract}_{date_str}.csv")
        
        # 如果文件已存在且大小合理，跳过
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            if file_size > 1000:
                logger.info(f"文件已存在: {output_file} ({file_size} bytes)")
                success_count += 1
                continue
        
        # 尝试不同的下载方法
        success = False
        
        # Windows优先使用PowerShell
        if system == 'Windows':
            success = download_with_powershell(url, output_file)
        
        # 尝试curl（跨平台）
        if not success:
            success = download_with_curl(url, output_file)
        
        # 尝试wget
        if not success:
            success = download_with_wget(url, output_file)
        
        if success:
            success_count += 1
        else:
            logger.error(f"所有方法都无法下载 {contract}")
    
    logger.info(f"\n下载完成: {success_count}/{len(contracts)} 个文件")
    
    if success_count == len(contracts):
        logger.info("✅ 所有文件下载成功！")
        # 运行分析
        from stock_index_futures_analyzer import FuturesAnalyzerConfig, FuturesNetShortAnalyzer
        config = FuturesAnalyzerConfig()
        analyzer = FuturesNetShortAnalyzer(config)
        analyzer.run_analysis()
        return True
    elif success_count > 0:
        logger.warning(f"部分文件下载成功 ({success_count}/{len(contracts)})")
        return False
    else:
        logger.error("所有文件下载失败")
        show_manual_solution()
        return False


def show_manual_solution():
    """
    显示手动解决方案
    """
    print("\n" + "="*70)
    print("手动解决方案")
    print("="*70)
    print("\n由于网络限制，建议您：")
    print("\n1. 直接在浏览器中下载文件")
    print("2. 使用代理软件（如Clash、V2Ray等）")
    print("3. 使用VPN连接")
    print("\n或者尝试以下命令（在命令行中执行）：")
    
    now = datetime.now()
    date_path = now.strftime("%Y%m/%d")
    date_str = now.strftime("%Y%m%d")
    
    print("\nWindows PowerShell命令：")
    for contract in ['IF', 'IH', 'IC', 'IM']:
        url = f"http://www.cffex.com.cn/sj/ccpm/{date_path}/{contract}_1.csv"
        print(f'Invoke-WebRequest -Uri "{url}" -OutFile "{contract}_{date_str}.csv"')
    
    print("\nLinux/Mac curl命令：")
    for contract in ['IF', 'IH', 'IC', 'IM']:
        url = f"http://www.cffex.com.cn/sj/ccpm/{date_path}/{contract}_1.csv"
        print(f'curl -L -o {contract}_{date_str}.csv "{url}"')
    
    print("="*70)


if __name__ == "__main__":
    download_all_contracts()