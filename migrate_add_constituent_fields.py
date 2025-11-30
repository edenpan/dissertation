#!/usr/bin/env python3
"""
为 index_constituents 表添加新字段的迁移脚本

新增字段:
- source: 数据来源（如 wiki, bloomberg, manual）
- created_at: 创建时间
- updated_at: 更新时间

使用方法:
    python migrate_add_constituent_fields.py
"""

from sqlalchemy import text

from common.db import get_engine


def migrate():
    """执行迁移"""
    engine = get_engine()
    
    print("开始迁移 index_constituents 表...")
    
    with engine.connect() as conn:
        # 检查表是否存在
        result = conn.execute(text("""
            SELECT COUNT(*) as cnt
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            AND table_name = 'index_constituents'
        """))
        
        if result.fetchone()[0] == 0:
            print("✗ index_constituents 表不存在，请先运行 migrate_create_index_tables.py")
            return False
        
        # 检查字段是否已存在
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
            AND table_name = 'index_constituents'
            AND column_name IN ('source', 'created_at', 'updated_at')
        """))
        
        existing_columns = {row[0] for row in result.fetchall()}
        
        # 添加 source 字段
        if 'source' not in existing_columns:
            print("添加 source 字段...")
            conn.execute(text("""
                ALTER TABLE index_constituents
                ADD COLUMN source VARCHAR(32) NOT NULL DEFAULT 'manual'
                AFTER notes
            """))
            print("✓ source 字段添加成功")
        else:
            print("✓ source 字段已存在")
        
        # 添加 created_at 字段
        if 'created_at' not in existing_columns:
            print("添加 created_at 字段...")
            conn.execute(text("""
                ALTER TABLE index_constituents
                ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                AFTER source
            """))
            print("✓ created_at 字段添加成功")
        else:
            print("✓ created_at 字段已存在")
        
        # 添加 updated_at 字段
        if 'updated_at' not in existing_columns:
            print("添加 updated_at 字段...")
            conn.execute(text("""
                ALTER TABLE index_constituents
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
    print("  - source: 数据来源（wiki=维基百科, bloomberg=彭博, manual=手动）")
    print("  - created_at: 记录创建时间")
    print("  - updated_at: 记录更新时间（自动更新）")
    
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