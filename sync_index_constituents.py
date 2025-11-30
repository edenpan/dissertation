#!/usr/bin/env python3
"""
同步指数成分股脚本

功能：
1. 从数据源（如维基百科）获取指数的最新成分股
2. 与数据库中的现有成分股进行比对
3. 新增的股票：添加记录并设置 effective_date 为当天
4. 移除的股票：设置 expiry_date 为当天
5. 记录数据来源（source）和时间戳

使用方法:
    python sync_index_constituents.py nasdaq100
    python sync_index_constituents.py ndx
"""

import sys
from datetime import date, datetime
from typing import List, Set

from sqlalchemy import and_, or_

from common.db import Index, IndexConstituent, Symbol, get_session
from data_pipeline.constituents import load_index_constituents
from data_pipeline.ingest import SymbolConfig


# 数据源映射
SOURCE_MAP = {
    "nasdaq100": "wiki",
    "ndx": "wiki",
}


def get_or_create_index(session, index_symbol: str, index_name: str, exchange: str, currency: str) -> Index:
    """获取或创建指数"""
    index = session.query(Index).filter(Index.symbol == index_symbol).first()
    
    if index:
        print(f"✓ 指数已存在: {index_symbol} - {index.name}")
    else:
        index = Index(
            symbol=index_symbol,
            name=index_name,
            exchange=exchange,
            currency=currency,
        )
        session.add(index)
        session.flush()
        print(f"✓ 创建新指数: {index_symbol} - {index_name}")
    
    return index


def get_or_create_symbol(session, symbol_config: SymbolConfig) -> Symbol:
    """获取或创建股票"""
    symbol = session.query(Symbol).filter(Symbol.symbol == symbol_config.symbol).first()
    
    if not symbol:
        symbol = Symbol(
            symbol=symbol_config.symbol,
            full_name=symbol_config.full_name,
            exchange=symbol_config.exchange,
            currency=symbol_config.currency,
        )
        session.add(symbol)
        session.flush()
        print(f"  + 创建新股票: {symbol_config.symbol} - {symbol_config.full_name}")
    
    return symbol


def get_current_constituents_from_db(session, index_id: int, as_of_date: date) -> Set[str]:
    """从数据库获取指定日期的有效成分股代码集合"""
    constituents = (
        session.query(IndexConstituent.symbol)
        .filter(
            and_(
                IndexConstituent.index_id == index_id,
                IndexConstituent.effective_date <= as_of_date,
                or_(
                    IndexConstituent.expiry_date.is_(None),
                    IndexConstituent.expiry_date > as_of_date,
                ),
            )
        )
        .all()
    )
    return {c.symbol for c in constituents}


def sync_constituents(
    session,
    index_symbol: str,
    index_name: str,
    exchange: str,
    currency: str,
    source_key: str,
) -> dict:
    """
    同步指数成分股
    
    返回统计信息字典
    """
    print(f"\n{'='*60}")
    print(f"开始同步指数: {index_symbol} ({index_name})")
    print(f"{'='*60}\n")
    
    # 1. 获取或创建指数
    index = get_or_create_index(session, index_symbol, index_name, exchange, currency)
    
    # 2. 从数据源获取最新成分股
    print(f"\n从数据源获取成分股列表...")
    try:
        latest_constituents = load_index_constituents(source_key)
        print(f"✓ 获取到 {len(latest_constituents)} 只成分股")
    except Exception as e:
        print(f"✗ 获取成分股失败: {e}")
        return {"error": str(e)}
    
    latest_symbols = {c.symbol for c in latest_constituents}
    
    # 3. 获取数据库中的当前成分股
    today = date.today()
    db_symbols = get_current_constituents_from_db(session, index.id, today)
    print(f"✓ 数据库中当前有 {len(db_symbols)} 只成分股")
    
    # 4. 比对差异
    new_symbols = latest_symbols - db_symbols  # 新增的
    removed_symbols = db_symbols - latest_symbols  # 移除的
    unchanged_symbols = latest_symbols & db_symbols  # 未变化的
    
    print(f"\n差异分析:")
    print(f"  - 新增: {len(new_symbols)} 只")
    print(f"  - 移除: {len(removed_symbols)} 只")
    print(f"  - 未变: {len(unchanged_symbols)} 只")
    
    # 获取数据源标识
    source = SOURCE_MAP.get(source_key, "unknown")
    
    # 5. 处理新增的成分股
    added_count = 0
    if new_symbols:
        print(f"\n处理新增成分股:")
        for symbol_str in sorted(new_symbols):
            # 找到对应的 SymbolConfig
            symbol_config = next((c for c in latest_constituents if c.symbol == symbol_str), None)
            if not symbol_config:
                continue
            
            # 确保股票存在
            symbol = get_or_create_symbol(session, symbol_config)
            
            # 创建成分股记录
            constituent = IndexConstituent(
                index_id=index.id,
                symbol_id=symbol.id,
                symbol=symbol_str,
                effective_date=today,
                weight=symbol_config.weight,
                source=source,
            )
            session.add(constituent)
            added_count += 1
            weight_info = f", 权重 = {symbol_config.weight}%" if symbol_config.weight else ""
            print(f"  + {symbol_str}: 生效日期 = {today}{weight_info}")
        
        session.flush()
    
    # 6. 处理移除的成分股
    removed_count = 0
    if removed_symbols:
        print(f"\n处理移除成分股:")
        for symbol_str in sorted(removed_symbols):
            # 查找当前有效的记录
            constituent = (
                session.query(IndexConstituent)
                .filter(
                    and_(
                        IndexConstituent.index_id == index.id,
                        IndexConstituent.symbol == symbol_str,
                        IndexConstituent.effective_date <= today,
                        or_(
                            IndexConstituent.expiry_date.is_(None),
                            IndexConstituent.expiry_date > today,
                        ),
                    )
                )
                .order_by(IndexConstituent.effective_date.desc())
                .first()
            )
            
            if constituent:
                constituent.expiry_date = today
                constituent.updated_at = datetime.now()
                removed_count += 1
                weight_info = f", 权重 = {constituent.weight}%" if constituent.weight else ""
                print(f"  - {symbol_str}: 失效日期 = {today}{weight_info}")
        
        session.flush()
    
    # 7. 更新未变化成分股的权重（如果权重有变化）
    updated_weight_count = 0
    if unchanged_symbols:
        print(f"\n检查权重更新:")
        for symbol_str in unchanged_symbols:
            # 找到对应的 SymbolConfig
            symbol_config = next((c for c in latest_constituents if c.symbol == symbol_str), None)
            if not symbol_config or symbol_config.weight is None:
                continue
            
            # 查找当前有效的记录
            constituent = (
                session.query(IndexConstituent)
                .filter(
                    and_(
                        IndexConstituent.index_id == index.id,
                        IndexConstituent.symbol == symbol_str,
                        IndexConstituent.effective_date <= today,
                        or_(
                            IndexConstituent.expiry_date.is_(None),
                            IndexConstituent.expiry_date > today,
                        ),
                    )
                )
                .order_by(IndexConstituent.effective_date.desc())
                .first()
            )
            
            if constituent and constituent.weight != symbol_config.weight:
                old_weight = constituent.weight
                constituent.weight = symbol_config.weight
                constituent.updated_at = datetime.now()
                updated_weight_count += 1
                print(f"  ~ {symbol_str}: 权重 {old_weight}% -> {symbol_config.weight}%")
        
        if updated_weight_count > 0:
            session.flush()
        else:
            print(f"  无权重变化")
    
    # 8. 返回统计信息
    stats = {
        "index_symbol": index_symbol,
        "index_name": index_name,
        "total_latest": len(latest_symbols),
        "total_db": len(db_symbols),
        "added": added_count,
        "removed": removed_count,
        "unchanged": len(unchanged_symbols),
        "weight_updated": updated_weight_count,
        "sync_date": today,
        "source": source,
    }
    
    print(f"\n{'='*60}")
    print(f"同步完成!")
    print(f"{'='*60}")
    print(f"统计信息:")
    print(f"  - 最新成分股数量: {stats['total_latest']}")
    print(f"  - 数据库原有数量: {stats['total_db']}")
    print(f"  - 新增: {stats['added']}")
    print(f"  - 移除: {stats['removed']}")
    print(f"  - 未变: {stats['unchanged']}")
    print(f"  - 权重更新: {stats['weight_updated']}")
    print(f"  - 同步日期: {stats['sync_date']}")
    print(f"  - 数据来源: {stats['source']}")
    
    return stats


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python sync_index_constituents.py <index_name>")
        print("\n支持的指数:")
        print("  - nasdaq100 (或 ndx): 纳斯达克100指数")
        sys.exit(1)
    
    index_key = sys.argv[1].lower()
    
    # 指数配置
    INDEX_CONFIGS = {
        "nasdaq100": {
            "symbol": "^NDX",
            "name": "NASDAQ-100",
            "exchange": "NASDAQ",
            "currency": "USD",
        },
        "ndx": {
            "symbol": "^NDX",
            "name": "NASDAQ-100",
            "exchange": "NASDAQ",
            "currency": "USD",
        },
    }
    
    if index_key not in INDEX_CONFIGS:
        print(f"错误: 不支持的指数 '{index_key}'")
        print("\n支持的指数:")
        for key in INDEX_CONFIGS:
            config = INDEX_CONFIGS[key]
            print(f"  - {key}: {config['name']}")
        sys.exit(1)
    
    config = INDEX_CONFIGS[index_key]
    
    try:
        with get_session() as session:
            stats = sync_constituents(
                session,
                index_symbol=config["symbol"],
                index_name=config["name"],
                exchange=config["exchange"],
                currency=config["currency"],
                source_key=index_key,
            )
            
            if "error" in stats:
                print(f"\n同步失败: {stats['error']}")
                sys.exit(1)
            
            print(f"\n✓ 同步成功!")
            
    except Exception as e:
        print(f"\n✗ 同步过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()