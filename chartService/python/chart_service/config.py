from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml


@dataclass(frozen=True)
class SymbolSettings:
    symbol: str
    full_name: str
    description: str
    exchange: str
    listed_exchange: str
    timezone: str
    session: str
    currency: str
    price_scale: int
    minmov: int


@dataclass(frozen=True)
class AppSettings:
    config_path: Path
    debug: bool = False
    timezone: str = "America/New_York"
    session: str = "0930-1600"
    supported_resolutions: List[str] = field(
        default_factory=lambda: ["1", "5", "15", "30", "60", "1D"]
    )
    provider: str = "yfinance"
    provider_options: Dict[str, Any] = field(default_factory=dict)
    symbols: List[SymbolSettings] = field(default_factory=list)

    def find_symbol(self, symbol: str) -> Optional[SymbolSettings]:
        for item in self.symbols:
            if item.symbol == symbol:
                return item
        return None


def load_settings(config_path: Optional[str] = None) -> AppSettings:
    """Load application settings from YAML, supporting environment overrides."""
    resolved_path = _resolve_path(config_path)
    raw = _read_yaml(resolved_path)
    return _build_settings(resolved_path, raw)


def _resolve_path(config_path: Optional[str]) -> Path:
    candidates: Iterable[Optional[str]] = (
        config_path,
        os.environ.get("CHART_SERVICE_CONFIG"),
    )

    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser().resolve()
        if path.is_file():
            return path

    default_path = (
        Path(__file__).resolve().parent / "config" / "default_settings.yaml"
    )
    return default_path


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Invalid configuration content: expected mapping, got {type(data)!r}")

    return data


def _build_settings(config_path: Path, raw: Dict[str, Any]) -> AppSettings:
    symbol_defaults = {
        "exchange": raw.get("exchange", "NASDAQ"),
        "listed_exchange": raw.get("listed_exchange", raw.get("exchange", "NASDAQ")),
        "timezone": raw.get("timezone", "America/New_York"),
        "session": raw.get("session", "0930-1600"),
        "currency": raw.get("currency", "USD"),
        "price_scale": raw.get("price_scale", 100),
        "minmov": raw.get("minmov", 1),
    }

    symbols = [
        _build_symbol(symbol_defaults, entry) for entry in raw.get("symbols", [])
    ]

    return AppSettings(
        config_path=config_path,
        debug=bool(raw.get("debug", False)),
        timezone=str(raw.get("timezone", "America/New_York")),
        session=str(raw.get("session", "0930-1600")),
        supported_resolutions=list(
            raw.get("supported_resolutions", ["1", "5", "15", "30", "60", "1D"])
        ),
        provider=str(raw.get("provider", "yfinance")),
        provider_options=dict(raw.get("provider_options", {})),
        symbols=symbols,
    )


def _build_symbol(defaults: Dict[str, Any], entry: Dict[str, Any]) -> SymbolSettings:
    try:
        data = {**defaults, **entry}
        return SymbolSettings(
            symbol=str(data["symbol"]),
            full_name=str(data["full_name"]),
            description=str(data["description"]),
            exchange=str(data["exchange"]),
            listed_exchange=str(data["listed_exchange"]),
            timezone=str(data["timezone"]),
            session=str(data["session"]),
            currency=str(data["currency"]),
            price_scale=int(data["price_scale"]),
            minmov=int(data["minmov"]),
        )
    except KeyError as exc:
        raise ValueError(f"Missing required symbol configuration key: {exc}") from exc
