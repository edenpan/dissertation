from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
import yfinance as yf

from ..config import AppSettings


@dataclass
class YFinanceProvider:
    settings: AppSettings

    def __post_init__(self) -> None:
        options = self.settings.provider_options
        self._auto_adjust = bool(options.get("auto_adjust", True))
        self._progress = bool(options.get("progress", False))
        self._prepost = bool(options.get("prepost", False))

    def fetch(
        self,
        symbol: str,
        start: Optional[datetime],
        end: Optional[datetime],
        interval: str,
    ) -> pd.DataFrame:
        end_dt = end or datetime.now(timezone.utc)
        start_dt = start or (end_dt - timedelta(days=365))

        if end_dt <= start_dt:
            start_dt = end_dt - timedelta(days=30)

        # yfinance restricts the window for minute-level data.
        if interval.endswith("m") and (end_dt - start_dt) > timedelta(days=7):
            start_dt = end_dt - timedelta(days=7)

        data = yf.download(
            symbol,
            start=start_dt,
            end=end_dt,
            interval=interval,
            auto_adjust=self._auto_adjust,
            progress=self._progress,
            prepost=self._prepost,
            threads=False,
        )

        if data.empty:
            return data

        frame = self._normalize_frame(data)
        return frame

    def _normalize_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        normalized = frame.copy()
        if not isinstance(normalized.index, pd.DatetimeIndex):
            normalized.index = pd.to_datetime(normalized.index)

        if normalized.index.tz is None:
            normalized.index = normalized.index.tz_localize("UTC")

        normalized = normalized.tz_convert(self.settings.timezone)
        normalized.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adjclose",
                "Volume": "volume",
            },
            inplace=True,
        )
        if "adjclose" not in normalized.columns:
            normalized["adjclose"] = normalized["close"]

        columns = [col for col in ("open", "high", "low", "close", "adjclose", "volume") if col in normalized.columns]
        return normalized[columns]
