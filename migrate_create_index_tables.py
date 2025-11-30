#!/usr/bin/env python3
"""
创建指数和指数成分股表的迁移脚本

使用方法:
    python migrate_create_index_tables.py
"""

from common.db import Base, get_engine, init_db


def main():
    """创建指数相关的表"""
    print("开始创建指数相关表...")
    
    engine = get_engine()
    
    # 只创建新的表（如果已存在则跳过）
    Base.metadata.create_all(bind=engine)
    
    print("✓ 表创建完成")
    print("\n创建的表:")
    print("  - indexes: 指数基本信息表")
    print("  - index_constituents: 指数成分股关系表")
    print("\n表结构说明:")
    print("indexes 表字段:")
    print("  - id: 主键")
    print("  - symbol: 指数代码（如 ^HSI, ^NDX）")
    print("  - name: 指数名称")
    print("  - exchange: 交易所")
    print("  - currency: 货币")
    print("  - description: 描述信息")
    print("\nindex_constituents 表字段:")
    print("  - id: 主键")
    print("  - index_id: 指数ID（外键）")
    print("  - symbol_id: 股票ID（外键）")
    print("  - symbol: 股票代码（冗余字段）")
    print("  - effective_date: 生效日期（加入指数的日期）")
    print("  - expiry_date: 失效日期（移除日期，NULL表示仍在指数中）")
    print("  - weight: 权重（可选）")
    print("  - notes: 备注")


if __name__ == "__main__":
    main()