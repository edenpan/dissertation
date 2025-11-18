from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, Optional

from ..config import AppSettings, SymbolSettings


class SymbolService:
    """Provide symbol metadata and search functionality."""

    def __init__(self, settings: AppSettings):
        self._settings = settings

    def list_symbols(self) -> List[Dict[str, str]]:
        return [self._to_listing(symbol) for symbol in self._settings.symbols]

    def search(self, query: Optional[str] = None) -> List[Dict[str, str]]:
        if not query:
            return self.list_symbols()

        normalized = query.lower()
        results = []
        for symbol in self._settings.symbols:
            if normalized in symbol.symbol.lower() or normalized in symbol.full_name.lower():
                results.append(self._to_listing(symbol))
        return results

    def get_symbol(self, symbol: str) -> Optional[Dict[str, str]]:
        match = self._settings.find_symbol(symbol)
        if not match:
            return None
        return self._to_symbol(match)

    def _to_listing(self, settings: SymbolSettings) -> Dict[str, str]:
        return {
            "symbol": settings.symbol,
            "full_name": settings.full_name,
            "description": settings.description,
            "exchange": settings.exchange,
            "ticker": settings.symbol,
            "type": "stock",
        }

    def _to_symbol(self, settings: SymbolSettings) -> Dict[str, str]:
        payload = asdict(settings)
        payload.update(
            {
                "name": settings.symbol,
                "ticker": settings.symbol,
                "session": settings.session,
                "exchange": settings.exchange,
                "listed_exchange": settings.listed_exchange,
                "timezone": settings.timezone,
                "pricescale": settings.price_scale,
                "minmov": settings.minmov,
                "has_intraday": True,
                "supported_resolutions": self._settings.supported_resolutions,
                "has_daily": True,
                "has_weekly_and_monthly": True,
                "has_no_volume": False,
                "type": "stock",
                "currency_code": settings.currency,
            }
        )
        return payload
