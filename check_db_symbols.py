#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查数据库中的股票代码
"""

from common.db import Symbol, DailyPrice, get_session, init_db
from sqlalchemy import select, func

def check_symbols():
    """检查数据库中的股票代码"""
    init_db()
    
    with get_session() as session:
        # 查询所有股票
        symbols = session.execute(select(Symbol)).scalars().all()
        
        print(f"数据库中共有 {len(symbols)} 个股票:")
        print("=" * 80)
        
        for sym in symbols:
            # 统计每个股票的数据行数
            count = session.scalar(
                select(func.count(DailyPrice.id))
                .where(DailyPrice.symbol_id == sym.id)
            )
            
            print(f"ID: {sym.id:3d} | 代码: {sym.symbol:15s} | 名称: {sym.full_name or 'N/A':30s} | 数据行数: {count:5d}")
        
        print("=" * 80)
        
        # 查询股票5的数据
        print("\n尝试查询股票代码 '5':")
        sym5 = session.scalar(select(Symbol).where(Symbol.symbol == '5'))
        if sym5:
            print(f"找到股票: {sym5.symbol} - {sym5.full_name}")
            count = session.scalar(
                select(func.count(DailyPrice.id))
                .where(DailyPrice.symbol_id == sym5.id)
            )
            print(f"数据行数: {count}")
        else:
            print("未找到股票代码 '5'")
        
        # 查询股票0005.HK的数据
        print("\n尝试查询股票代码 '0005.HK':")
        sym_hk = session.scalar(select(Symbol).where(Symbol.symbol == '0005.HK'))
        if sym_hk:
            print(f"找到股票: {sym_hk.symbol} - {sym_hk.full_name}")
            count = session.scalar(
                select(func.count(DailyPrice.id))
                .where(DailyPrice.symbol_id == sym_hk.id)
            )
            print(f"数据行数: {count}")
            
            # 显示前5行数据
            prices = session.execute(
                select(DailyPrice)
                .where(DailyPrice.symbol_id == sym_hk.id)
                .order_by(DailyPrice.traded_at)
                .limit(5)
            ).scalars().all()
            
            print("\n前5行数据:")
            for price in prices:
                print(f"  日期: {price.traded_at} | "
                      f"开盘: {price.open:7.2f} | "
                      f"最高: {price.high:7.2f} | "
                      f"最低: {price.low:7.2f} | "
                      f"收盘: {price.close:7.2f} | "
                      f"调整收盘: {price.adj_close:7.2f} | "
                      f"成交量: {price.volume}")
        else:
            print("未找到股票代码 '0005.HK'")

if __name__ == "__main__":
    check_symbols()