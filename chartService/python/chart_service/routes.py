from __future__ import annotations

import time
from http import HTTPStatus
from typing import Any, Dict

from flask import Blueprint, Response, current_app, jsonify, request

bp = Blueprint("chart_service", __name__)


@bp.route("/")
def healthcheck() -> str:
    return "chart service online"


@bp.route("/time")
def get_time() -> str:
    return str(int(time.time() * 1000))


@bp.route("/config")
def get_config() -> Response:
    settings = current_app.config["SETTINGS"]
    payload = {
        "supports_search": True,
        "supports_group_request": False,
        "supported_resolutions": settings.supported_resolutions,
        "supports_marks": False,
        "supports_time": True,
    }
    return _json(payload)


@bp.route("/search")
def search() -> Response:
    query = request.args.get("query") or request.args.get("q")
    symbol_service = current_app.config["SYMBOL_SERVICE"]
    results = symbol_service.search(query)
    return _json(results)


@bp.route("/symbols")
def symbols() -> Response:
    symbol = request.args.get("symbol")
    symbol_service = current_app.config["SYMBOL_SERVICE"]
    data = symbol_service.get_symbol(symbol) if symbol else None
    if not data:
        return _json(None, status=HTTPStatus.NOT_FOUND)
    return _json(data)


@bp.route("/history")
def history() -> Response:
    symbol = request.args.get("symbol")
    if not symbol:
        return _json({"s": "error", "message": "symbol is required"}, status=HTTPStatus.BAD_REQUEST)

    start = request.args.get("from")
    end = request.args.get("to")
    resolution = request.args.get("resolution", "1D")
    history_service = current_app.config["HISTORY_SERVICE"]
    result = history_service.fetch(symbol, start, end, resolution)
    status = HTTPStatus.OK if result.get("s") != "error" else HTTPStatus.BAD_REQUEST
    return _json(result, status=status)


def _json(payload: Any, status: HTTPStatus = HTTPStatus.OK) -> Response:
    resp = jsonify(payload)
    resp.status_code = int(status)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp
