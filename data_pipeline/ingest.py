from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Sequence

import pandas as pd
import yaml
import yfinance as yf
from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from common.db import DailyPrice, Symbol, get_session, init_db

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SymbolConfig:
    """Metadata describing a ticker to ingest."""

    symbol: str
    full_name: str | None = None
    exchange: str | None = None
    currency: str | None = None
    weight: float | None = None  # 权重（用于指数成分股）

    @classmethod
    def from_dict(cls, payload: dict) -> "SymbolConfig":
        if "symbol" not in payload:
            raise ValueError("Symbol configuration dictionaries require a `symbol` key.")
        return cls(
            symbol=str(payload["symbol"]).strip(),
            full_name=payload.get("full_name"),
            exchange=payload.get("exchange"),
            currency=payload.get("currency"),
            weight=payload.get("weight"),
        )


@dataclass
class SymbolIngestionSummary:
    symbol: str
    rows_written: int
    start: date | None
    end: date | None


@dataclass
class IngestionReport:
    symbols: List[SymbolIngestionSummary]

    @property
    def total_symbols(self) -> int:
        return len(self.symbols)

    @property
    def total_rows(self) -> int:
        return sum(item.rows_written for item in self.symbols)


def load_symbols_from_config(config_path: str | Path) -> list[SymbolConfig]:
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    with config_file.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    symbols_section = payload.get("symbols")
    if not symbols_section:
        raise ValueError(
            f"The configuration file {config_file} does not contain a `symbols` section."
        )

    configs: list[SymbolConfig] = []
    for item in symbols_section:
        configs.append(SymbolConfig.from_dict(item))
    return configs


def fetch_and_store(
    symbols: Sequence[SymbolConfig],
    start: date | None = None,
    end: date | None = None,
    *,
    force: bool = False,
) -> IngestionReport:
    """Fetch daily data for each symbol and persist it into MySQL."""
    if not symbols:
        raise ValueError("At least one symbol must be provided for ingestion.")

    init_db()
    summaries: list[SymbolIngestionSummary] = []

    normalized_start, normalized_end = _normalize_date_window(start, end)

    with get_session() as session:
        for cfg in symbols:
            logger.info("Fetching data for %s", cfg.symbol)
            symbol_row = _ensure_symbol_exists(session, cfg)
            frame = _download_history(cfg.symbol, normalized_start, normalized_end)
            if frame.empty:
                logger.warning("No data returned for %s in the requested window.", cfg.symbol)
                summaries.append(
                    SymbolIngestionSummary(
                        symbol=cfg.symbol,
                        rows_written=0,
                        start=None,
                        end=None,
                    )
                )
                continue

            min_date = frame["traded_at"].min()
            max_date = frame["traded_at"].max()

            if force:
                _delete_existing_range(session, symbol_row.id, min_date, max_date)

            rows = _upsert_prices(session, symbol_row.id, frame, cfg.symbol)
            summaries.append(
                SymbolIngestionSummary(
                    symbol=cfg.symbol,
                    rows_written=rows,
                    start=min_date,
                    end=max_date,
                )
            )

    return IngestionReport(symbols=summaries)


def _normalize_date_window(
    start: date | None,
    end: date | None,
) -> tuple[date, date]:
    today = datetime.utcnow().date()
    normalized_end = end or today
    normalized_start = start or (normalized_end - timedelta(days=365 * 5))

    if normalized_start > normalized_end:
        raise ValueError("The start date must be earlier than the end date.")

    return normalized_start, normalized_end


def _ensure_symbol_exists(session, cfg: SymbolConfig) -> Symbol:
    stmt = select(Symbol).where(Symbol.symbol == cfg.symbol)
    symbol_row = session.scalar(stmt)
    if symbol_row:
        updated = False
        for attribute in ("full_name", "exchange", "currency"):
            new_value = getattr(cfg, attribute)
            if new_value and getattr(symbol_row, attribute) != new_value:
                setattr(symbol_row, attribute, new_value)
                updated = True
        if updated:
            session.flush()
        return symbol_row

    symbol_row = Symbol(
        symbol=cfg.symbol,
        full_name=cfg.full_name or cfg.symbol,
        exchange=cfg.exchange,
        currency=cfg.currency,
    )
    session.add(symbol_row)
    session.flush()
    return symbol_row


def _download_history(symbol: str, start: date, end: date) -> pd.DataFrame:
    end_exclusive = end + timedelta(days=1)
    data = yf.download(
        symbol,
        start=start,
        end=end_exclusive,
        interval="1d",
        auto_adjust=False,
        progress=False,
        prepost=False,
        threads=False,
    )
    if data.empty:
        return pd.DataFrame(columns=["traded_at", "open", "high", "low", "close", "adj_close", "volume"])

    if isinstance(data.columns, pd.MultiIndex):
        try:
            data = data.xs(symbol, axis=1, level=-1)
        except KeyError:
            data = data.droplevel(-1, axis=1)

    frame = data.reset_index()
    if "Date" in frame.columns:
        frame.rename(columns={"Date": "traded_at"}, inplace=True)
    elif "Datetime" in frame.columns:
        frame.rename(columns={"Datetime": "traded_at"}, inplace=True)
    else:
        frame.rename(columns={"index": "traded_at"}, inplace=True)

    frame.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        },
        inplace=True,
    )

    frame["traded_at"] = pd.to_datetime(frame["traded_at"]).dt.date
    frame.sort_values("traded_at", inplace=True)
    frame.drop_duplicates(subset=["traded_at"], keep="last", inplace=True)
    return frame


def _delete_existing_range(session, symbol_id: int, start: date, end: date) -> None:
    stmt = (
        delete(DailyPrice)
        .where(DailyPrice.symbol_id == symbol_id)
        .where(DailyPrice.traded_at >= start)
        .where(DailyPrice.traded_at <= end)
    )
    session.execute(stmt)


def _upsert_prices(session, symbol_id: int, frame: pd.DataFrame, symbol: str = None) -> int:
    if frame.empty:
        return 0

    # Get symbol from symbol_id if not provided
    if symbol is None:
        from sqlalchemy import select
        from common.db import Symbol
        symbol_row = session.scalar(select(Symbol).where(Symbol.id == symbol_id))
        symbol = symbol_row.symbol if symbol_row else ""

    payload = []
    for row in frame.itertuples(index=False):
        payload.append(
            {
                "symbol": symbol,
                "symbol_id": symbol_id,
                "traded_at": row.traded_at,
                "open": _nan_to_none(row.open),
                "high": _nan_to_none(row.high),
                "low": _nan_to_none(row.low),
                "close": _nan_to_none(row.close),
                "adj_close": _nan_to_none(getattr(row, "adj_close", None)),
                "volume": _nan_to_int(row.volume),
            }
        )

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
    return len(payload)


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
