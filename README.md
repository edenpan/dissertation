# dissertation

Tools for collecting US equity market data and experimenting with trading strategies.

## Quick Start

1. **Launch MySQL**
   ```bash
   docker-compose up -d mysql
   ```
   The container boots with a default database (`stockdb`) and credentials matching the values used by the Python stack (`runner` / `tester`). Override them with the `DATA_DB_*` environment variables if needed.

2. **Install dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Fetch daily bars**
   ```bash
   python manage.py fetch-data --symbols AAPL,MSFT,GOOG --start 2020-01-01 --end 2024-01-01
   ```
   You can also reuse the TradingView configuration file:
   ```bash
   python manage.py fetch-data \
     --config chartService/python/chart_service/config/default_settings.yaml
   ```

4. **Run a backtest**
   ```bash
   python manage.py backtest AAPL --start 2021-01-01 --end 2024-01-01 \
     --short-window 20 --long-window 60 --capital 15000
   ```
   Add `--fetch-missing` to pull data automatically before simulating.

## Index Workflows

Fetch every NASDAQ-100 constituent and store their daily bars:

```bash
python manage.py fetch-index nasdaq100 --start 2023-01-01 --end 2024-01-01
```

Run the SMA crossover backtest across the same basket:

```bash
python manage.py backtest-index nasdaq100 --start 2023-01-01 --end 2024-01-01 \
  --short-window 20 --long-window 60 --fetch-missing
```

The summary highlights average/best/worst performers and prints per-symbol returns.

## Configuration

The data stack reads connection details from the environment. Defaults match `docker-compose.yml`:

| Variable | Default |
|----------|---------|
| `DATA_DB_HOST` | `127.0.0.1` |
| `DATA_DB_PORT` | `3306` |
| `DATA_DB_USER` | `runner` |
| `DATA_DB_PASSWORD` | `tester` |
| `DATA_DB_NAME` | `stockdb` |
| `DATA_DB_CHARSET` | `utf8mb4` |

## chartService

The TradingView-compatible service lives in [chartService/python](chartService/python) and continues to source data from Yahoo Finance via `yfinance`. Start it with:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r chartService/python/requirements.txt
export FLASK_APP=miniapp:app
flask run
```

Provide a custom symbol list by copying `chartService/python/chart_service/config/default_settings.yaml` and pointing `CHART_SERVICE_CONFIG` at the new file.

> The legacy Django implementation in `chartService/saveload_backend` still requires additional modernization before it can run on Python 3.

## Legacy crawlers and indicators

Historical scrapers and indicator experiments remain under `crawler/` and `strategies/`. They now use the shared MySQL infrastructure exposed via `common.db` and `crawler.util.sqlUtil`. Modern workflows (data ingestion + backtesting) are driven by `manage.py`.
