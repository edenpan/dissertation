#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证 adj_close 数据是否正确获取
"""

import sys
import pandas as pd
from strategies import utils

def test_adj_close_data():
    """测试 adj_close 数据获取"""
    
    # 测试股票代码
    test_symbol = '5'
    
    print(f"正在获取股票 {test_symbol} 的数据...")
    
    # 获取数据
    try:
        stock_data = utils.getStockDataWithTime(test_symbol, '2013-07-13', '2016-12-12')
        
        print(f"\n数据形状: {stock_data.shape}")
        print(f"\n列名: {stock_data.columns.tolist()}")
        
        # 检查 adjclose 列是否存在
        if 'adjclose' in stock_data.columns:
            print("\n✓ adjclose 列存在")
            
            # 检查是否有空值
            null_count = stock_data['adjclose'].isnull().sum()
            print(f"adjclose 空值数量: {null_count}")
            
            # 显示前几行数据
            print("\n前5行数据:")
            print(stock_data[['datetime', 'open', 'high', 'low', 'close', 'adjclose', 'volume']].head())
            
            # 显示统计信息
            print("\nadjclose 统计信息:")
            print(stock_data['adjclose'].describe())
            
            # 检查 adjclose 和 close 的差异
            if 'close' in stock_data.columns:
                diff = (stock_data['adjclose'] - stock_data['close']).abs()
                print(f"\nadjclose 和 close 的平均差异: {diff.mean():.4f}")
                print(f"adjclose 和 close 的最大差异: {diff.max():.4f}")
                
                # 显示有差异的行数
                diff_rows = (diff > 0.01).sum()
                print(f"差异大于0.01的行数: {diff_rows} / {len(stock_data)}")
        else:
            print("\n✗ adjclose 列不存在！")
            print(f"可用的列: {stock_data.columns.tolist()}")
            
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_adj_close_data()