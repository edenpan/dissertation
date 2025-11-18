from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import List

import numpy as np
import pandas as pd
from sqlalchemy import select

from common.db import DailyPrice, Symbol, get_engine, init_db

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Trade:
    traded_at: date
    action: str
    price: float
    shares: float
    cash_after: float


@dataclass
class BacktestResult:
    symbol: str
    start: date
    end: date
    initial_capital: float
    final_value: float
    total_return: float
    trades: List[Trade]
    equity_curve: pd.DataFrame
    short_window: int
    long_window: int

    @property
    def total_trades(self) -> int:
        return len(self.trades)


def run_sma_backtest(
    symbol: str,
    start: date,
    end: date,
    *,
    short_window: int = 20,
    long_window: int = 50,
    initial_capital: float = 10_000.0,
) -> BacktestResult:
    if short_window <= 0 or long_window <= 0:
        raise ValueError("Moving-average windows must be positive integers.")
    if short_window >= long_window:
        raise ValueError("`short_window` must be smaller than `long_window` for SMA crossover.")

    data = _load_price_history(symbol, start, end)
    if data.empty:
        raise ValueError(f"No price history found for {symbol} between {start} and {end}.")

    price = data["adj_close"].fillna(data["close"])
    short_ma = price.rolling(window=short_window).mean()
    long_ma = price.rolling(window=long_window).mean()

    signals = pd.Series(0, index=price.index)
    signals.iloc[long_window - 1 :] = np.where(
        short_ma.iloc[long_window - 1 :] > long_ma.iloc[long_window - 1 :], 1, 0
    )
    position_changes = signals.diff().fillna(0)

    cash = initial_capital
    shares = 0.0
    trades: list[Trade] = []
    equity_records: list[tuple[date, float]] = []

    for idx, row in price.items():
        change = position_changes.loc[idx]
        if change > 0 and shares == 0:
            shares = cash / row if row else 0
            cash = 0.0
            trades.append(Trade(idx.date(), "BUY", float(row), float(shares), float(cash)))
        elif change < 0 and shares > 0:
            cash += shares * row
            trades.append(Trade(idx.date(), "SELL", float(row), float(shares), float(cash)))
            shares = 0.0

        portfolio_value = cash + shares * row
        equity_records.append((idx.date(), float(portfolio_value)))

    if shares > 0:
        last_price = price.iloc[-1]
        cash += shares * last_price
        trades.append(Trade(price.index[-1].date(), "SELL", float(last_price), float(shares), float(cash)))
        shares = 0.0
        equity_records[-1] = (price.index[-1].date(), float(cash))

    final_value = cash
    total_return = (final_value - initial_capital) / initial_capital

    equity_curve = pd.DataFrame(equity_records, columns=["traded_at", "equity"])
    equity_curve.set_index("traded_at", inplace=True)

    return BacktestResult(
        symbol=symbol,
        start=start,
        end=end,
        initial_capital=initial_capital,
        final_value=final_value,
        total_return=total_return,
        trades=trades,
        equity_curve=equity_curve,
        short_window=short_window,
        long_window=long_window,
    )


def _load_price_history(symbol: str, start: date, end: date) -> pd.DataFrame:
    init_db()
    engine = get_engine()
    stmt = (
        select(
            DailyPrice.traded_at,
            DailyPrice.open,
            DailyPrice.high,
            DailyPrice.low,
            DailyPrice.close,
            DailyPrice.adj_close,
            DailyPrice.volume,
        )
        .join(Symbol, DailyPrice.symbol_id == Symbol.id)
        .where(Symbol.symbol == symbol)
        .where(DailyPrice.traded_at >= start)
        .where(DailyPrice.traded_at <= end)
        .order_by(DailyPrice.traded_at)
    )
    frame = pd.read_sql(stmt, engine, parse_dates=["traded_at"])
    if frame.empty:
        return frame
    frame.set_index("traded_at", inplace=True)
    frame.sort_index(inplace=True)
    return frame
