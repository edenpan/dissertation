from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, List

import pandas as pd
import requests
from requests import Response

from .ingest import SymbolConfig

logger = logging.getLogger(__name__)


class ConstituentsError(RuntimeError):
    """Raised when index constituents cannot be fetched."""


def load_index_constituents(name: str) -> List[SymbolConfig]:
    loader = _INDEX_LOADERS.get(name.lower())
    if loader is None:
        supported = ", ".join(sorted(_INDEX_LOADERS))
        raise ValueError(f"Unsupported index `{name}`. Supported indexes: {supported}")
    return loader()


def _load_nasdaq100() -> List[SymbolConfig]:
    url = "https://en.wikipedia.org/wiki/NASDAQ-100"
    try:
        response = _http_get(url)
    except Exception as exc:  # pragma: no cover - network dependent
        raise ConstituentsError(f"Failed to download NASDAQ-100 constituents: {exc}") from exc

    from io import StringIO

    tables = pd.read_html(StringIO(response.text), match="Ticker")
    if not tables:
        raise ConstituentsError("NASDAQ-100 constituents table not found in the fetched document.")

    table = tables[0]
    required_columns = {"Ticker", "Company"}
    if not required_columns.issubset(table.columns):
        raise ConstituentsError(
            "Unexpected NASDAQ-100 table structure: missing required columns."
        )

    configs: list[SymbolConfig] = []
    for _, row in table.iterrows():
        ticker = _normalize_ticker(row["Ticker"])
        if not ticker:
            continue
        company = str(row["Company"]).strip()
        
        # 尝试获取权重信息（如果表格中有）
        weight = None
        if "Weight" in table.columns or "Weighting" in table.columns:
            weight_col = "Weight" if "Weight" in table.columns else "Weighting"
            try:
                weight_val = row[weight_col]
                if pd.notna(weight_val):
                    # 处理百分比格式（如 "10.5%" 或 "10.5"）
                    weight_str = str(weight_val).strip().replace("%", "")
                    weight = float(weight_str)
            except (ValueError, TypeError):
                logger.warning(f"Could not parse weight for {ticker}: {row.get(weight_col)}")
        
        configs.append(
            SymbolConfig(
                symbol=ticker,
                full_name=company or ticker,
                exchange="NASDAQ",
                currency="USD",
                weight=weight,
            )
        )
    if not configs:
        raise ConstituentsError("Parsed NASDAQ-100 table but did not resolve any tickers.")
    return configs


def _normalize_ticker(value) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""

    # Remove footnote markers (e.g. "ABCD[1]" or "XYZ*")
    for sep in ("[", "\u2020", "\u00A0"):
        if sep in text:
            text = text.split(sep)[0]

    text = text.replace(".", "-")  # yfinance uses '-' instead of '.' for US tickers.
    text = text.replace(" ", "")
    return text


def _http_get(url: str) -> Response:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response


_INDEX_LOADERS: Dict[str, Callable[[], List[SymbolConfig]]] = {
    "nasdaq100": _load_nasdaq100,
    "ndx": _load_nasdaq100,
}
