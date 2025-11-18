from __future__ import annotations

from flask import Flask

from .config import AppSettings, load_settings
from .providers.yfinance_provider import YFinanceProvider
from .routes import bp as api_blueprint
from .services.history import HistoryService
from .services.symbols import SymbolService


def create_app(config_path: str | None = None, *, settings: AppSettings | None = None) -> Flask:
    app_settings = settings or load_settings(config_path)

    app = Flask(__name__)
    app.config["SETTINGS"] = app_settings

    provider = YFinanceProvider(app_settings)
    symbol_service = SymbolService(app_settings)
    history_service = HistoryService(app_settings, provider)

    app.config["SYMBOL_SERVICE"] = symbol_service
    app.config["HISTORY_SERVICE"] = history_service

    app.register_blueprint(api_blueprint)

    app.logger.debug("Chart service initialised with config %s", app_settings.config_path)
    return app
