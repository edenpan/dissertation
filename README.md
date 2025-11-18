# dissertation

## chartService
The backend of the chart view service now targets **Python 3.10+** and retrieves **US equity data through Yahoo Finance** via `yfinance`.

APIs that are required by TradingView remain documented in [chartService/ChartServices.md](chartService/ChartServices.md).

The runnable Flask backend lives in [chartService/python](chartService/python). To start it locally:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r chartService/python/requirements.txt
export FLASK_APP=miniapp:app
# Optional: override the default config
# export CHART_SERVICE_CONFIG=/path/to/settings.yaml
flask run
```

Configuration is fully data-driven. Copy `chartService/python/chart_service/config/default_settings.yaml`, adjust the symbol list or provider settings, and point `CHART_SERVICE_CONFIG` at the new file.

> The historical Django-based `chartService/saveload_backend` remains a legacy component and will need additional work before it can run on Python 3.

## crawler
The data crawler part.  
Basically to analysis the website and crawl the financial data.  
The Stock/history/yqd.py is used to get the daily stock data from yahoo and store the data into local postgresql database.  

## strategies
In this directory, there are a backtest framework and a pso parameter optimaziation and several implemented indicators.  




    
