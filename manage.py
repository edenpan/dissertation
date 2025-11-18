from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from typing import Iterable, List

from data_pipeline import IngestionReport, SymbolConfig, fetch_and_store, load_symbols_from_config
from strategies.backtester import BacktestResult, run_sma_backtest


def main(argv: Iterable[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "fetch-data":
        try:
            configs = _resolve_symbol_configs(args)
        except ValueError as exc:
            parser.error(str(exc))
        report = fetch_and_store(
            configs,
            start=args.start,
            end=args.end,
            force=args.force,
        )
        _print_ingestion_report(report)
        return 0

    if args.command == "backtest":
        start = args.start or (date.today() - timedelta(days=365 * 2))
        if start > args.end:
            parser.error("`--start` must be earlier than `--end`.")

        if args.fetch_missing:
            fetch_and_store(
                [SymbolConfig(symbol=args.symbol)],
                start=start,
                end=args.end,
            )

        try:
            result = run_sma_backtest(
                symbol=args.symbol,
                start=start,
                end=args.end,
                short_window=args.short_window,
                long_window=args.long_window,
                initial_capital=args.capital,
            )
        except ValueError as exc:
            parser.error(str(exc))
        _print_backtest_result(result)
        return 0

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dissertation data tools.")
    subparsers = parser.add_subparsers(dest="command")

    fetch_parser = subparsers.add_parser("fetch-data", help="Download daily bars into the MySQL database.")
    fetch_parser.add_argument(
        "--symbols",
        type=str,
        help="Comma separated list of ticker symbols (e.g. AAPL,MSFT,GOOG).",
    )
    fetch_parser.add_argument(
        "--config",
        type=str,
        help="Path to a YAML configuration file with a `symbols` section.",
    )
    fetch_parser.add_argument(
        "--start",
        type=_parse_date,
        help="Inclusive start date (YYYY-MM-DD). Defaults to five years ago.",
        default=None,
    )
    fetch_parser.add_argument(
        "--end",
        type=_parse_date,
        help="Inclusive end date (YYYY-MM-DD). Defaults to today.",
        default=None,
    )
    fetch_parser.add_argument(
        "--force",
        action="store_true",
        help="Remove overlapping rows before inserting fresh data.",
    )

    backtest_parser = subparsers.add_parser("backtest", help="Run an SMA crossover backtest.")
    backtest_parser.add_argument("symbol", type=str, help="Ticker symbol to backtest.")
    backtest_parser.add_argument(
        "--start",
        type=_parse_date,
        help="Inclusive start date (YYYY-MM-DD). Defaults to two years ago.",
        default=None,
    )
    backtest_parser.add_argument(
        "--end",
        type=_parse_date,
        help="Inclusive end date (YYYY-MM-DD). Defaults to today.",
        default=date.today(),
    )
    backtest_parser.add_argument(
        "--short-window",
        type=int,
        default=20,
        help="Lookback window for the fast SMA. Default: 20 trading days.",
    )
    backtest_parser.add_argument(
        "--long-window",
        type=int,
        default=50,
        help="Lookback window for the slow SMA. Default: 50 trading days.",
    )
    backtest_parser.add_argument(
        "--capital",
        type=float,
        default=10_000.0,
        help="Initial capital for the strategy. Default: 10,000.",
    )
    backtest_parser.add_argument(
        "--fetch-missing",
        action="store_true",
        help="Download any missing price history before running the backtest.",
    )

    return parser


def _resolve_symbol_configs(args) -> List[SymbolConfig]:
    configs: List[SymbolConfig] = []
    if args.config:
        configs.extend(load_symbols_from_config(args.config))

    if args.symbols:
        for symbol in args.symbols.split(","):
            sym = symbol.strip()
            if sym:
                configs.append(SymbolConfig(symbol=sym))

    if not configs:
        raise ValueError("Provide at least one symbol via --symbols or --config.")

    # Deduplicate while preserving order
    seen = set()
    unique_configs: list[SymbolConfig] = []
    for cfg in configs:
        if cfg.symbol not in seen:
            unique_configs.append(cfg)
            seen.add(cfg.symbol)
    return unique_configs


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _print_ingestion_report(report: IngestionReport) -> None:
    print(f"Ingested {report.total_rows} rows across {report.total_symbols} symbols.")
    for summary in report.symbols:
        if summary.rows_written == 0:
            print(f"  - {summary.symbol}: no new data.")
        else:
            print(
                f"  - {summary.symbol}: {summary.rows_written} rows "
                f"from {summary.start} to {summary.end}."
            )


def _print_backtest_result(result: BacktestResult) -> None:
    print(f"SMA Backtest for {result.symbol} ({result.start} -> {result.end})")
    print(f"  Fast SMA: {result.short_window} | Slow SMA: {result.long_window}")
    print(f"  Initial capital: ${result.initial_capital:,.2f}")
    print(f"  Final equity:    ${result.final_value:,.2f}")
    print(f"  Total return:    {result.total_return * 100:,.2f}%")
    print(f"  Trades executed: {result.total_trades}")
    if result.trades:
        print("  Trade log (date | action | price | shares | cash):")
        for trade in result.trades:
            print(
                f"    {trade.traded_at} | {trade.action:<4} | "
                f"${trade.price:,.2f} | {trade.shares:,.4f} | ${trade.cash_after:,.2f}"
            )


if __name__ == "__main__":
    sys.exit(main())
