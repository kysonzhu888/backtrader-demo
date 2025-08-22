#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
使用Selenium模拟浏览器下载中金所数据
解决反爬虫问题
"""

import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_with_selenium(date: datetime = None):
    """
    使用Selenium模拟浏览器下载数据
    
    Args:
        date: 日期，默认为今天
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        logger.error("请先安装selenium: pip install selenium")
        return False
    
    if date is None:
        date = datetime.now()
    
    # 配置Chrome选项
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # 无头模式（不显示浏览器）
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # 设置下载目录
    download_dir = os.path.join(os.path.dirname(__file__), 'futures_data')
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    contracts = ['IF', 'IH', 'IC', 'IM']
    date_path = date.strftime("%Y%m/%d")
    
    try:
        # 创建浏览器实例
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        success_count = 0
        for contract in contracts:
            url = f"http://www.cffex.com.cn/sj/ccpm/{date_path}/{contract}_1.csv"
            logger.info(f"使用Selenium下载: {url}")
            
            try:
                driver.get(url)
                time.sleep(2)  # 等待下载完成
                
                # 检查是否下载成功
                file_name = f"{contract}_{date.strftime('%Y%m%d')}.csv"
                file_path = os.path.join(download_dir, file_name)
                
                # 等待文件出现
                for _ in range(10):
                    if os.path.exists(file_path):
                        logger.info(f"✅ {contract} 下载成功: {file_path}")
                        success_count += 1
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"下载 {contract} 失败: {e}")
        
        driver.quit()
        
        if success_count == len(contracts):
            logger.info("所有文件下载成功！")
            return True
        else:
            logger.warning(f"只下载了 {success_count}/{len(contracts)} 个文件")
            return False
            
    except Exception as e:
        logger.error(f"Selenium下载失败: {e}")
        return False


def download_manual_guide():
    """
    手动下载指南
    """
    now = datetime.now()
    date_path = now.strftime("%Y%m/%d")
    date_str = now.strftime("%Y%m%d")
    
    print("\n" + "="*60)
    print("手动下载指南")
    print("="*60)
    print("\n由于网络限制，您可以手动下载数据文件：\n")
    
    contracts = ['IF', 'IH', 'IC', 'IM']
    print("请在浏览器中访问以下链接并保存文件：\n")
    
    for contract in contracts:
        url = f"http://www.cffex.com.cn/sj/ccpm/{date_path}/{contract}_1.csv"
        file_name = f"{contract}_{date_str}.csv"
        print(f"{contract}合约:")
        print(f"  URL: {url}")
        print(f"  保存为: {file_name}")
        print()
    
    save_path = os.path.join(os.path.dirname(__file__), 'futures_data')
    print(f"请将下载的文件保存到: {save_path}")
    print("\n下载完成后，程序将自动使用这些文件进行分析。")
    print("="*60)


def use_cached_data():
    """
    使用缓存数据进行分析
    """
    from stock_index_futures_analyzer import FuturesAnalyzerConfig, FuturesNetShortAnalyzer
    
    logger.info("尝试使用本地缓存数据...")
    
    config = FuturesAnalyzerConfig()
    # 增加超时和重试，但主要依赖缓存
    config.connection_timeout = 1  # 快速失败
    config.read_timeout = 1
    config.max_download_retries = 0  # 不重试
    
    analyzer = FuturesNetShortAnalyzer(config)
    
    # 检查是否有缓存文件
    data_dir = os.path.join(os.path.dirname(__file__), 'futures_data')
    if os.path.exists(data_dir):
        files = os.listdir(data_dir)
        csv_files = [f for f in files if f.endswith('.csv')]
        if csv_files:
            logger.info(f"找到 {len(csv_files)} 个缓存文件")
            # 直接运行分析（会使用缓存）
            return analyzer.run_analysis()
    
    logger.warning("没有找到缓存文件")
    return False


def smart_download():
    """
    智能下载：先尝试直接下载，失败则提供手动方案
    """
    import requests
    from datetime import datetime
    
    # 使用requests Session模拟浏览器
    session = requests.Session()
    
    # 完整的浏览器请求头
    headers = {
        'Host': 'www.cffex.com.cn',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'Referer': 'http://www.cffex.com.cn/',
    }
    
    # 先访问主页获取cookie
    try:
        logger.info("访问中金所主页获取cookie...")
        resp = session.get('http://www.cffex.com.cn/', headers=headers, timeout=10)
        logger.info(f"主页响应: {resp.status_code}")
        
        # 添加延迟，模拟人类行为
        time.sleep(2)
        
    except Exception as e:
        logger.error(f"访问主页失败: {e}")
    
    # 尝试下载数据
    now = datetime.now()
    date_path = now.strftime("%Y%m/%d")
    date_str = now.strftime("%Y%m%d")
    
    download_dir = os.path.join(os.path.dirname(__file__), 'futures_data')
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    
    contracts = ['IF', 'IH', 'IC', 'IM']
    success_count = 0
    
    for contract in contracts:
        url = f"http://www.cffex.com.cn/sj/ccpm/{date_path}/{contract}_1.csv"
        file_path = os.path.join(download_dir, f"{contract}_{date_str}.csv")
        
        try:
            logger.info(f"下载 {contract}: {url}")
            
            # 使用stream下载大文件
            resp = session.get(url, headers=headers, timeout=30, stream=True)
            resp.raise_for_status()
            
            # 保存文件
            with open(file_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(file_path)
            logger.info(f"✅ {contract} 下载成功: {file_path} ({file_size} bytes)")
            success_count += 1
            
            # 模拟人类延迟
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"❌ {contract} 下载失败: {e}")
    
    if success_count > 0:
        logger.info(f"成功下载 {success_count}/{len(contracts)} 个文件")
        return True
    else:
        logger.error("所有文件下载失败")
        download_manual_guide()
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--selenium":
            # 使用Selenium
            download_with_selenium()
        elif sys.argv[1] == "--manual":
            # 显示手动下载指南
            download_manual_guide()
        elif sys.argv[1] == "--cached":
            # 使用缓存
            use_cached_data()
        elif sys.argv[1] == "--smart":
            # 智能下载
            smart_download()
    else:
        print("股指期货数据下载工具")
        print("\n选项：")
        print("  --smart    : 智能下载（推荐）")
        print("  --selenium : 使用Selenium浏览器下载")
        print("  --manual   : 显示手动下载指南")
        print("  --cached   : 使用缓存数据")
        print("\n建议先尝试 --smart")