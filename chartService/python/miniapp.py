from __future__ import annotations

import os

from flask import Flask

from chart_service import create_app

CONFIG_ENV_VAR = "CHART_SERVICE_CONFIG"


def build_app() -> Flask:
    config_path = os.environ.get(CONFIG_ENV_VAR)
    return create_app(config_path=config_path)


app = build_app()


if __name__ == "__main__":
    app.run(debug=app.config["SETTINGS"].debug)
