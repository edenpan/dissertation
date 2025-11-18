from __future__ import annotations

import logging
from datetime import date
from typing import Dict, Iterable, List, Sequence, Tuple

import pandas as pd
from sqlalchemy import Select, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from common.db import DailyPrice, Symbol, get_engine, get_session, init_db

logger = logging.getLogger(__name__)

_symbol_cache: Dict[str, str] = {}


def getSymbolList() -> List[Tuple[str, str]]:
    """Return cached (symbol, display_name) tuples."""
    global _symbol_cache
    if not _symbol_cache:
        init_db()
        with get_session() as session:
            rows = session.execute(select(Symbol.symbol, Symbol.full_name)).all()
        _symbol_cache = {
            row.symbol: row.full_name or row.symbol  # type: ignore[attr-defined]
            for row in rows
        }
    return list(_symbol_cache.items())


def insertPd(symbol_name: str, pdRecord: pd.DataFrame | None) -> None:
    """Append or update price rows from a DataFrame."""
    if pdRecord is None or pdRecord.empty:
        return

    frame = pdRecord.copy()
    frame.columns = [col.strip().lower() for col in frame.columns]
    expected = {"datetime", "open", "high", "low", "close", "adjclose", "volume"}
    if not expected.issubset(frame.columns):
        missing = expected - set(frame.columns)
        raise ValueError(f"DataFrame is missing columns: {', '.join(sorted(missing))}")

    frame["datetime"] = pd.to_datetime(frame["datetime"]).dt.date
    frame.rename(columns={"adjclose": "adj_close"}, inplace=True)

    init_db()
    with get_session() as session:
        symbol_row = _ensure_symbol(session, symbol_name)
        payload = []
        for row in frame.itertuples(index=False):
            payload.append(
                {
                    "symbol_id": symbol_row.id,
                    "traded_at": row.datetime,
                    "open": _nan_to_none(row.open),
                    "high": _nan_to_none(row.high),
                    "low": _nan_to_none(row.low),
                    "close": _nan_to_none(row.close),
                    "adj_close": _nan_to_none(row.adj_close),
                    "volume": _nan_to_int(row.volume),
                }
            )

        if not payload:
            return

        stmt = mysql_insert(DailyPrice).values(payload)
        update_clause = {
            "open": stmt.inserted.open,
            "high": stmt.inserted.high,
            "low": stmt.inserted.low,
            "close": stmt.inserted.close,
            "adj_close": stmt.inserted.adj_close,
            "volume": stmt.inserted.volume,
        }
        session.execute(stmt.on_duplicate_key_update(update_clause))


def getDaliyData(symbol_name: str, start: date | None = None, end: date | None = None) -> pd.DataFrame:
    """Fetch historical bars for the given symbol."""
    init_db()
    engine = get_engine()
    stmt = _build_price_query(symbol_name, start, end)
    frame = pd.read_sql(stmt, engine, parse_dates=["datetime"])
    frame.rename(columns={"adj_close": "adjclose"}, inplace=True)
    return frame


def _build_price_query(symbol_name: str, start: date | None, end: date | None) -> Select:
    stmt = (
        select(
            DailyPrice.traded_at.label("datetime"),
            DailyPrice.open,
            DailyPrice.close,
            DailyPrice.high,
            DailyPrice.low,
            DailyPrice.adj_close,
            DailyPrice.volume,
        )
        .join(Symbol, DailyPrice.symbol_id == Symbol.id)
        .where(Symbol.symbol == symbol_name)
        .order_by(DailyPrice.traded_at)
    )
    if start:
        stmt = stmt.where(DailyPrice.traded_at >= start)
    if end:
        stmt = stmt.where(DailyPrice.traded_at <= end)
    return stmt


def _ensure_symbol(session, symbol_name: str) -> Symbol:
    row = session.scalar(select(Symbol).where(Symbol.symbol == symbol_name))
    if row:
        return row
    row = Symbol(symbol=symbol_name)
    session.add(row)
    session.flush()
    _symbol_cache[symbol_name] = symbol_name
    return row


def _nan_to_none(value):
    if value is None:
        return None
    if pd.isna(value):
        return None
    return float(value)


def _nan_to_int(value):
    cleaned = _nan_to_none(value)
    if cleaned is None:
        return None
    return int(cleaned)
