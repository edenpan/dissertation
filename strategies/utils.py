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
    normalized_symbol = _normalize_symbol(symbol)
    return sqlUtil.getDaliyData(normalized_symbol)


def getStockDataWithTime(symbol: str, startTime: str | date, endTime: str | date) -> pd.DataFrame:
    """Fetch price history between two dates (inclusive)."""
    normalized_symbol = _normalize_symbol(symbol)
    start = _normalize_date(startTime)
    end = _normalize_date(endTime)
    return sqlUtil.getDaliyData(normalized_symbol, start=start, end=end)


def transferDate(strDate: str) -> int:
    """Legacy helper retained for backwards compatibility."""
    return int(pd.Timestamp(strDate).timestamp())


def _normalize_symbol(symbol: str) -> str:
    """Normalize stock symbol to match database format.
    
    Converts Hong Kong stock codes like '5', '0005', '5.HK' to '0005.HK' format.
    Leaves other symbols unchanged.
    """
    symbol = symbol.strip()
    
    # If already in correct format (e.g., '0005.HK'), return as is
    if symbol.endswith('.HK'):
        return symbol
    
    # Check if it's a numeric Hong Kong stock code
    try:
        # Remove any leading zeros and convert to int to validate
        code_num = int(symbol)
        # Format as 4-digit code with .HK suffix
        return f"{code_num:04d}.HK"
    except ValueError:
        # Not a numeric code, return as is (e.g., 'AAPL', 'MSFT')
        return symbol


def _normalize_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()
