from __future__ import annotations

from datetime import date
from typing import Dict, Iterable

import pandas as pd

from crawler.util import sqlUtil

_symbol_cache: Dict[str, str] | None = None


def getSymbolList() -> Dict[str, str]:
    """Return a cached mapping of ticker -> display name."""
    global _symbol_cache
    if _symbol_cache is None:
        pairs = sqlUtil.getSymbolList()
        _symbol_cache = {symbol: display for symbol, display in pairs}
    return _symbol_cache


def getStockData(symbol: str) -> pd.DataFrame:
    """Fetch the full price history for a ticker."""
    return sqlUtil.getDaliyData(symbol)


def getStockDataWithTime(symbol: str, startTime: str | date, endTime: str | date) -> pd.DataFrame:
    """Fetch price history between two dates (inclusive)."""
    start = _normalize_date(startTime)
    end = _normalize_date(endTime)
    return sqlUtil.getDaliyData(symbol, start=start, end=end)


def transferDate(strDate: str) -> int:
    """Legacy helper retained for backwards compatibility."""
    return int(pd.Timestamp(strDate).timestamp())


def _normalize_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()
