from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import pandas as pd

from ..config import AppSettings


ResolutionMap = {
    "1": "1m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "60": "60m",
    "1D": "1d",
    "D": "1d",
}


@dataclass
class HistoryService:
    settings: AppSettings
    provider: "HistoryProvider"

    def fetch(
        self,
        symbol: str,
        start: Optional[str],
        end: Optional[str],
        resolution: str,
    ) -> Dict[str, object]:
        base_symbol, indicator = self._parse_symbol(symbol)
        interval = ResolutionMap.get(resolution, "1d")
        start_dt = _to_datetime(start)
        end_dt = _to_datetime(end)

        frame = self.provider.fetch(base_symbol, start_dt, end_dt, interval)
        if frame is None or frame.empty:
            return {"s": "no_data"}

        if indicator:
            return self._build_indicator_payload(indicator, frame)

        return self._build_price_payload(frame)

    def _build_price_payload(self, frame: pd.DataFrame) -> Dict[str, object]:
        frame = frame.sort_index()
        timestamps = [int(ts.timestamp()) for ts in frame.index]
        return {
            "s": "ok",
            "type": "FullTick",
            "t": timestamps,
            "o": frame["open"].fillna(method="ffill").tolist(),
            "h": frame["high"].fillna(method="ffill").tolist(),
            "l": frame["low"].fillna(method="ffill").tolist(),
            "c": frame["close"].fillna(method="ffill").tolist(),
            "v": frame["volume"].fillna(0).tolist(),
        }

    def _build_indicator_payload(
        self,
        indicator: str,
        frame: pd.DataFrame,
    ) -> Dict[str, object]:
        indicator = indicator.lower()
        if indicator == "mac5":
            return self._moving_average(frame, window=5)
        if indicator == "bollingerbands":
            return self._bollinger_bands(frame, window=20, num_std=2)
        raise ValueError(f"Unsupported indicator: {indicator}")

    def _moving_average(self, frame: pd.DataFrame, window: int) -> Dict[str, object]:
        frame = frame.sort_index()
        series = frame["close"].rolling(window).mean().dropna()
        if series.empty:
            return {"s": "no_data"}
        timestamps = [int(ts.timestamp()) for ts in series.index]
        return {
            "s": "ok",
            "type": "IndicatorTick",
            "i1": series.tolist(),
            "t": timestamps,
        }

    def _bollinger_bands(
        self,
        frame: pd.DataFrame,
        window: int,
        num_std: int,
    ) -> Dict[str, object]:
        frame = frame.sort_index()
        rolling_mean = frame["close"].rolling(window).mean()
        rolling_std = frame["close"].rolling(window).std()
        boll_high = rolling_mean + (rolling_std * num_std)
        boll_low = rolling_mean - (rolling_std * num_std)

        valid = rolling_mean.dropna()
        if valid.empty:
            return {"s": "no_data"}

        aligned_index = valid.index
        timestamps = [int(ts.timestamp()) for ts in aligned_index]
        return {
            "s": "ok",
            "type": "IndicatorTick",
            "i2": rolling_mean.loc[aligned_index].tolist(),
            "i1": boll_low.loc[aligned_index].tolist(),
            "i3": boll_high.loc[aligned_index].tolist(),
            "t": timestamps,
        }

    @staticmethod
    def _parse_symbol(symbol: str) -> Tuple[str, Optional[str]]:
        if symbol.startswith("Indic#"):
            parts = symbol.split("#", 2)
            if len(parts) == 3:
                return parts[1], parts[2]
        return symbol, None


def _to_datetime(value: Optional[str]) -> Optional[datetime]:
    if value in (None, "", "null"):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError):
        return None
