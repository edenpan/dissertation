#!/usr/bin/env python3
"""
指数成分股管理示例脚本

演示如何:
1. 添加指数
2. 添加成分股
3. 更新成分股（移除/替换）
4. 查询当前成分股
5. 查询历史成分股
"""

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from common.db import Index, IndexConstituent, Symbol, get_session


def add_index(
    session: Session,
    symbol: str,
    name: str,
    exchange: Optional[str] = None,
    currency: Optional[str] = None,
    description: Optional[str] = None,
) -> Index:
    """添加或更新指数信息"""
    index = session.query(Index).filter(Index.symbol == symbol).first()
    
    if index:
        # 更新现有指数
        index.name = name
        index.exchange = exchange
        index.currency = currency
        index.description = description
        print(f"更新指数: {symbol} - {name}")
    else:
        # 创建新指数
        index = Index(
            symbol=symbol,
            name=name,
            exchange=exchange,
            currency=currency,
            description=description,
        )
        session.add(index)
        print(f"添加指数: {symbol} - {name}")
    
    session.flush()
    return index


def add_constituent(
    session: Session,
    index_symbol: str,
    stock_symbol: str,
    effective_date: date,
    weight: Optional[float] = None,
    notes: Optional[str] = None,
) -> IndexConstituent:
    """添加成分股到指数"""
    # 获取指数
    index = session.query(Index).filter(Index.symbol == index_symbol).first()
    if not index:
        raise ValueError(f"指数不存在: {index_symbol}")
    
    # 获取股票
    symbol = session.query(Symbol).filter(Symbol.symbol == stock_symbol).first()
    if not symbol:
        raise ValueError(f"股票不存在: {stock_symbol}")
    
    # 检查是否已存在相同的记录
    existing = (
        session.query(IndexConstituent)
        .filter(
            and_(
                IndexConstituent.index_id == index.id,
                IndexConstituent.symbol_id == symbol.id,
                IndexConstituent.effective_date == effective_date,
            )
        )
        .first()
    )
    
    if existing:
        print(f"成分股已存在: {stock_symbol} 在 {index_symbol} (生效日期: {effective_date})")
        return existing
    
    # 创建新的成分股记录
    constituent = IndexConstituent(
        index_id=index.id,
        symbol_id=symbol.id,
        symbol=stock_symbol,
        effective_date=effective_date,
        weight=weight,
        notes=notes,
    )
    session.add(constituent)
    print(f"添加成分股: {stock_symbol} 到 {index_symbol} (生效日期: {effective_date})")
    
    session.flush()
    return constituent


def remove_constituent(
    session: Session,
    index_symbol: str,
    stock_symbol: str,
    expiry_date: date,
    notes: Optional[str] = None,
) -> None:
    """从指数中移除成分股（设置失效日期）"""
    # 获取指数
    index = session.query(Index).filter(Index.symbol == index_symbol).first()
    if not index:
        raise ValueError(f"指数不存在: {index_symbol}")
    
    # 获取股票
    symbol = session.query(Symbol).filter(Symbol.symbol == stock_symbol).first()
    if not symbol:
        raise ValueError(f"股票不存在: {stock_symbol}")
    
    # 查找当前有效的成分股记录（expiry_date 为 NULL 或大于指定日期）
    constituent = (
        session.query(IndexConstituent)
        .filter(
            and_(
                IndexConstituent.index_id == index.id,
                IndexConstituent.symbol_id == symbol.id,
                or_(
                    IndexConstituent.expiry_date.is_(None),
                    IndexConstituent.expiry_date > expiry_date,
                ),
            )
        )
        .order_by(IndexConstituent.effective_date.desc())
        .first()
    )
    
    if not constituent:
        print(f"未找到有效的成分股记录: {stock_symbol} 在 {index_symbol}")
        return
    
    # 设置失效日期
    constituent.expiry_date = expiry_date
    if notes:
        constituent.notes = notes if not constituent.notes else f"{constituent.notes}; {notes}"
    
    print(f"移除成分股: {stock_symbol} 从 {index_symbol} (失效日期: {expiry_date})")


def get_current_constituents(
    session: Session,
    index_symbol: str,
    as_of_date: Optional[date] = None,
) -> List[IndexConstituent]:
    """获取指定日期的指数成分股（默认为当前日期）"""
    if as_of_date is None:
        as_of_date = date.today()
    
    # 获取指数
    index = session.query(Index).filter(Index.symbol == index_symbol).first()
    if not index:
        raise ValueError(f"指数不存在: {index_symbol}")
    
    # 查询在指定日期有效的成分股
    constituents = (
        session.query(IndexConstituent)
        .filter(
            and_(
                IndexConstituent.index_id == index.id,
                IndexConstituent.effective_date <= as_of_date,
                or_(
                    IndexConstituent.expiry_date.is_(None),
                    IndexConstituent.expiry_date > as_of_date,
                ),
            )
        )
        .order_by(IndexConstituent.symbol)
        .all()
    )
    
    return constituents


def get_constituent_history(
    session: Session,
    index_symbol: str,
    stock_symbol: Optional[str] = None,
) -> List[IndexConstituent]:
    """获取指数成分股的历史记录"""
    # 获取指数
    index = session.query(Index).filter(Index.symbol == index_symbol).first()
    if not index:
        raise ValueError(f"指数不存在: {index_symbol}")
    
    query = session.query(IndexConstituent).filter(IndexConstituent.index_id == index.id)
    
    if stock_symbol:
        query = query.filter(IndexConstituent.symbol == stock_symbol)
    
    history = query.order_by(
        IndexConstituent.symbol,
        IndexConstituent.effective_date.desc(),
    ).all()
    
    return history


def example_usage():
    """示例用法"""
    with get_session() as session:
        # 1. 添加指数
        print("\n=== 添加指数 ===")
        hsi = add_index(
            session,
            symbol="^HSI",
            name="恒生指数",
            exchange="HKEX",
            currency="HKD",
            description="香港恒生指数",
        )
        
        ndx = add_index(
            session,
            symbol="^NDX",
            name="纳斯达克100指数",
            exchange="NASDAQ",
            currency="USD",
            description="纳斯达克100指数",
        )
        
        # 2. 添加成分股（假设这些股票已经在 symbols 表中）
        print("\n=== 添加成分股 ===")
        try:
            # 添加恒生指数成分股
            add_constituent(
                session,
                index_symbol="^HSI",
                stock_symbol="0700.HK",  # 腾讯
                effective_date=date(2020, 1, 1),
                weight=10.5,
                notes="初始成分股",
            )
            
            add_constituent(
                session,
                index_symbol="^HSI",
                stock_symbol="0005.HK",  # 汇丰
                effective_date=date(2020, 1, 1),
                weight=8.3,
                notes="初始成分股",
            )
            
            # 添加纳斯达克100成分股
            add_constituent(
                session,
                index_symbol="^NDX",
                stock_symbol="AAPL",
                effective_date=date(2020, 1, 1),
                weight=12.0,
                notes="初始成分股",
            )
            
        except ValueError as e:
            print(f"警告: {e}")
            print("请先确保相关股票已添加到 symbols 表中")
        
        # 3. 移除成分股
        print("\n=== 移除成分股 ===")
        try:
            remove_constituent(
                session,
                index_symbol="^HSI",
                stock_symbol="0005.HK",
                expiry_date=date(2023, 6, 30),
                notes="调整指数成分",
            )
        except ValueError as e:
            print(f"警告: {e}")
        
        # 4. 查询当前成分股
        print("\n=== 查询当前成分股 ===")
        try:
            current = get_current_constituents(session, "^HSI")
            print(f"恒生指数当前成分股数量: {len(current)}")
            for c in current:
                print(f"  - {c.symbol}: 生效日期={c.effective_date}, 权重={c.weight}")
        except ValueError as e:
            print(f"警告: {e}")
        
        # 5. 查询历史成分股
        print("\n=== 查询历史成分股 ===")
        try:
            history = get_constituent_history(session, "^HSI")
            print(f"恒生指数历史记录数量: {len(history)}")
            for h in history:
                expiry = h.expiry_date if h.expiry_date else "至今"
                print(f"  - {h.symbol}: {h.effective_date} ~ {expiry}")
        except ValueError as e:
            print(f"警告: {e}")


if __name__ == "__main__":
    print("指数成分股管理示例")
    print("=" * 50)
    example_usage()
    print("\n完成!")