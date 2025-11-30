#!/usr/bin/env python3
"""
为 daily_prices 表添加时间戳字段的迁移脚本

新增字段:
- created_at: 创建时间
- updated_at: 更新时间

使用方法:
    python migrate_add_daily_prices_timestamps.py
"""

from sqlalchemy import text

from common.db import get_engine


def migrate():
    """执行迁移"""
    engine = get_engine()
    
    print("开始迁移 daily_prices 表...")
    
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
        
        # 检查字段是否已存在
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
            AND table_name = 'daily_prices'
            AND column_name IN ('created_at', 'updated_at')
        """))
        
        existing_columns = {row[0] for row in result.fetchall()}
        
        # 添加 created_at 字段
        if 'created_at' not in existing_columns:
            print("添加 created_at 字段...")
            conn.execute(text("""
                ALTER TABLE daily_prices
                ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                AFTER volume
            """))
            print("✓ created_at 字段添加成功")
        else:
            print("✓ created_at 字段已存在")
        
        # 添加 updated_at 字段
        if 'updated_at' not in existing_columns:
            print("添加 updated_at 字段...")
            conn.execute(text("""
                ALTER TABLE daily_prices
                ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP
                AFTER created_at
            """))
            print("✓ updated_at 字段添加成功")
        else:
            print("✓ updated_at 字段已存在")
        
        conn.commit()
    
    print("\n迁移完成!")
    print("\n新增字段说明:")
    print("  - created_at: 记录创建时间（首次插入数据时自动设置）")
    print("  - updated_at: 记录更新时间（每次更新数据时自动更新）")
    print("\n注意事项:")
    print("  - 已存在的记录会使用当前时间作为 created_at 和 updated_at 的初始值")
    print("  - 新插入的记录会自动设置这两个字段")
    print("  - updated_at 会在每次 UPDATE 操作时自动更新")
    
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