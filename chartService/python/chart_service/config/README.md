# Configuration

- `default_settings.yaml` ships with a small list of US equities (AAPL, MSFT, GOOG, AMZN, TSLA) and sensible defaults for the TradingView adapter.
- Copy this file to another location, customise the `symbols` block, and point the web service to it by setting the `CHART_SERVICE_CONFIG` environment variable before starting Flask.
- Provider options are passed directly to the `yfinance.download` call. Toggle `auto_adjust`, `progress`, or `prepost` if you need different behaviour.

Example snippet for two tickers:

```yaml
symbols:
  - symbol: NVDA
    full_name: NVIDIA Corporation
    description: NVIDIA Corporation
    exchange: NASDAQ
    currency: USD
  - symbol: META
    full_name: Meta Platforms, Inc.
    description: Meta Platforms, Inc.
    exchange: NASDAQ
    currency: USD
```
