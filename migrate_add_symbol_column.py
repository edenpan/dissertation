#!/usr/bin/env python3
"""
为 daily_prices 表添加 symbol 列的迁移脚本

如果 daily_prices 表缺少 symbol 列，此脚本会添加它并从 symbols 表填充数据

使用方法:
    python migrate_add_symbol_column.py
"""

from sqlalchemy import text

from common.db import get_engine


def migrate():
    """执行迁移"""
    engine = get_engine()
    
    print("开始检查 daily_prices 表结构...")
    
    with engine.connect() as conn:
        # 检查表是否存在
        result = conn.execute(text("""
            SELECT COUNT(*) as cnt
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            AND table_name = 'daily_prices'
        """))
        
        if result.fetchone()[0] == 0:
            print("✗ daily_prices 表不存在")
            return False
        
        # 检查 symbol 列是否存在
        result = conn.execute(text("""
            SELECT COUNT(*) as cnt
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
            AND table_name = 'daily_prices'
            AND column_name = 'symbol'
        """))
        
        if result.fetchone()[0] > 0:
            print("✓ symbol 列已存在，无需迁移")
            return True
        
        print("symbol 列不存在，开始添加...")
        
        # 添加 symbol 列
        print("步骤 1: 添加 symbol 列...")
        conn.execute(text("""
            ALTER TABLE daily_prices
            ADD COLUMN symbol VARCHAR(32) AFTER id
        """))
        print("✓ symbol 列添加成功")
        
        # 从 symbols 表填充 symbol 数据
        print("步骤 2: 从 symbols 表填充 symbol 数据...")
        result = conn.execute(text("""
            UPDATE daily_prices dp
            JOIN symbols s ON dp.symbol_id = s.id
            SET dp.symbol = s.symbol
        """))
        print(f"✓ 更新了 {result.rowcount} 行数据")
        
        # 设置 symbol 列为 NOT NULL
        print("步骤 3: 设置 symbol 列为 NOT NULL...")
        conn.execute(text("""
            ALTER TABLE daily_prices
            MODIFY COLUMN symbol VARCHAR(32) NOT NULL
        """))
        print("✓ symbol 列设置为 NOT NULL")
        
        # 添加索引
        print("步骤 4: 添加索引...")
        conn.execute(text("""
            ALTER TABLE daily_prices
            ADD INDEX idx_symbol (symbol)
        """))
        print("✓ 索引添加成功")
        
        conn.commit()
    
    print("\n迁移完成!")
    print("\n说明:")
    print("  - symbol 列已添加到 daily_prices 表")
    print("  - 已从 symbols 表填充所有现有记录的 symbol 值")
    print("  - symbol 列已设置为 NOT NULL")
    print("  - 已为 symbol 列添加索引")
    
    return True


def main():
    """主函数"""
    try:
        success = migrate()
        if not success:
            exit(1)
    except Exception as e:
        print(f"\n✗ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()