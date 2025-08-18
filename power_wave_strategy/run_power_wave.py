#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
动力波策略启动脚本
可以通过命令行参数指定品种
"""

import sys
import argparse
from power_wave_xtdata import PowerWaveStrategy, PowerWaveConfig


# 品种配置字典
# 注意：xtdata中期货代码都是小写
PRODUCT_CONFIGS = {
    'au': {
        'name': '沪金',
        'multiplier': 1000,
        'exchange': 'SF'  # 上期所
    },
    'ag': {
        'name': '沪银',
        'multiplier': 15,
        'exchange': 'SF'  # 上期所
    },
    'cu': {
        'name': '沪铜',
        'multiplier': 5,
        'exchange': 'SF'  # 上期所
    },
    'OI': {
        'name': '菜籽油',
        'multiplier': 10,
        'exchange': 'ZF'  # 郑商所
    },
    'rb': {
        'name': '螺纹钢',
        'multiplier': 10,
        'exchange': 'SF'  # 上期所
    },
    'IF': {
        'name': '沪深300股指',
        'multiplier': 300,
        'exchange': 'IF'  # 中金所
    }
}


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='动力波策略启动脚本')
    parser.add_argument(
        '--product',
        type=str,
        default='au',
        choices=list(PRODUCT_CONFIGS.keys()),
        help='交易品种代码（默认：au沪金）'
    )
    parser.add_argument(
        '--stop-loss',
        type=int,
        default=666,
        help='硬止损金额（默认：666元）'
    )
    
    args = parser.parse_args()
    
    # 获取品种配置
    product_code = args.product.lower()  # xtdata使用小写
    if product_code not in PRODUCT_CONFIGS:
        print(f"错误：不支持的品种 {product_code}")
        print(f"支持的品种：{', '.join(PRODUCT_CONFIGS.keys())}")
        sys.exit(1)
    
    product_config = PRODUCT_CONFIGS[product_code]
    
    # 更新配置
    PowerWaveConfig.update_product(
        product_type=product_code,
        product_name=product_config['name'],
        multiplier=product_config['multiplier'],
        exchange=product_config['exchange']
    )
    
    # 更新止损金额
    if args.stop_loss > 0:
        PowerWaveConfig.HARD_STOP_LOSS = args.stop_loss
        PowerWaveConfig.HARD_STOP_LOSS_POINTS = args.stop_loss / product_config['multiplier']
    
    # 打印配置信息
    print("=" * 60)
    print("动力波策略配置")
    print("=" * 60)
    print(f"交易品种：{product_config['name']}({product_code})")
    print(f"合约乘数：{product_config['multiplier']}")
    print(f"交易所：{product_config['exchange']}")
    print(f"硬止损：{PowerWaveConfig.HARD_STOP_LOSS}元")
    print(f"止损点数：{PowerWaveConfig.HARD_STOP_LOSS_POINTS:.2f}")
    print("=" * 60)
    
    # 创建并启动策略
    try:
        strategy = PowerWaveStrategy()
        strategy.start()
        
        print("\n策略已启动，按 Ctrl+C 停止...")
        
        # 保持程序运行
        import time
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n正在停止策略...")
        strategy.stop()
        print("策略已停止")
    except Exception as e:
        print(f"策略运行错误：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()