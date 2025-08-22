#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股指期货分析器网络问题解决方案
提供多种网络配置方案解决连接问题
"""

from stock_index_futures_analyzer import FuturesAnalyzerConfig, FuturesNetShortAnalyzer

def solution_1_use_https():
    """方案1：使用HTTPS协议"""
    print("=== 方案1：尝试使用HTTPS ===")
    
    config = FuturesAnalyzerConfig()
    config.use_https = True  # 启用HTTPS
    
    analyzer = FuturesNetShortAnalyzer(config)
    return analyzer.run_analysis()

def solution_2_use_proxy():
    """方案2：使用代理服务器"""
    print("=== 方案2：使用代理服务器 ===")
    
    config = FuturesAnalyzerConfig()
    config.use_proxy = True
    
    # 请根据您的实际代理设置修改
    config.http_proxy = "http://127.0.0.1:7890"  # 例如：Clash代理
    config.https_proxy = "http://127.0.0.1:7890"
    
    analyzer = FuturesNetShortAnalyzer(config)
    return analyzer.run_analysis()

def solution_3_increase_timeout():
    """方案3：增加超时时间"""
    print("=== 方案3：增加超时时间 ===")
    
    config = FuturesAnalyzerConfig()
    config.connection_timeout = 30  # 连接超时30秒
    config.read_timeout = 60       # 读取超时60秒
    
    analyzer = FuturesNetShortAnalyzer(config)
    return analyzer.run_analysis()

def solution_4_mixed():
    """方案4：混合方案（HTTPS + 长超时）"""
    print("=== 方案4：混合方案 ===")
    
    config = FuturesAnalyzerConfig()
    config.use_https = True
    config.connection_timeout = 20
    config.read_timeout = 40
    config.max_download_retries = 5  # 增加重试次数
    
    analyzer = FuturesNetShortAnalyzer(config)
    return analyzer.run_analysis()

def solution_5_vpn_proxy():
    """方案5：使用VPN代理（如果您有VPN）"""
    print("=== 方案5：VPN代理方案 ===")
    print("请确保您的VPN已连接")
    
    config = FuturesAnalyzerConfig()
    config.use_proxy = True
    
    # 常见VPN软件的代理端口
    # Clash: 7890
    # V2Ray: 1080 或 10808
    # Shadowsocks: 1080
    config.http_proxy = "http://127.0.0.1:1080"  # 根据实际修改
    config.https_proxy = "http://127.0.0.1:1080"
    
    analyzer = FuturesNetShortAnalyzer(config)
    return analyzer.run_analysis()

def test_all_solutions():
    """测试所有解决方案"""
    solutions = [
        ("HTTPS协议", solution_1_use_https),
        ("代理服务器", solution_2_use_proxy),
        ("增加超时", solution_3_increase_timeout),
        ("混合方案", solution_4_mixed),
    ]
    
    for name, solution_func in solutions:
        print(f"\n{'='*50}")
        print(f"测试方案：{name}")
        print('='*50)
        
        try:
            success = solution_func()
            if success:
                print(f"✅ {name} 成功！")
                return True
            else:
                print(f"❌ {name} 失败")
        except Exception as e:
            print(f"❌ {name} 出错: {e}")
    
    print("\n所有方案都失败了，可能需要：")
    print("1. 检查网络连接")
    print("2. 检查防火墙设置")
    print("3. 使用VPN或代理软件")
    print("4. 联系网络管理员")
    
    return False

def manual_test():
    """手动测试网络连接"""
    import urllib.request
    
    print("=== 手动测试网络连接 ===")
    
    urls_to_test = [
        "http://www.cffex.com.cn",
        "https://www.cffex.com.cn",
        "http://www.baidu.com",  # 测试基本网络
        "https://www.baidu.com",
    ]
    
    for url in urls_to_test:
        print(f"\n测试 {url}...")
        try:
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                status = response.getcode()
                print(f"✅ {url} - 状态码: {status}")
        except Exception as e:
            print(f"❌ {url} - 错误: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            # 测试网络连接
            manual_test()
        elif sys.argv[1] == "--auto":
            # 自动尝试所有方案
            test_all_solutions()
        elif sys.argv[1] == "--https":
            solution_1_use_https()
        elif sys.argv[1] == "--proxy":
            solution_2_use_proxy()
        elif sys.argv[1] == "--timeout":
            solution_3_increase_timeout()
        else:
            print("用法:")
            print("  python futures_network_fix.py --test     # 测试网络连接")
            print("  python futures_network_fix.py --auto     # 自动尝试所有方案")
            print("  python futures_network_fix.py --https    # 使用HTTPS")
            print("  python futures_network_fix.py --proxy    # 使用代理")
            print("  python futures_network_fix.py --timeout  # 增加超时")
    else:
        print("网络问题解决方案：")
        print("1. 运行 --test 测试网络连接")
        print("2. 运行 --auto 自动尝试所有方案")
        print("\n如果仍有问题，请编辑本文件中的代理设置")