"""Parity 测试:向量化全区间信号 ⇄ 逐 bar trailing 窗口信号,逐日必须相等。

这是「向量化预筛可代表 zipline」的构造性证明的**信号层**:
  ① 全区间:一次性把 AAPL 2013-2017 全历史喂给 signals 函数,得 signal_series;
  ② 逐 bar:对每个 t,只喂 trailing `lookback_bars` 根(不足则至今全历史)窗口,
     调**同一个**函数,取末格作 t 的信号。
两序列逐日整数相等 ⇒ 该函数「当日信号只需有限 trailing 窗口即可复现全历史结果」,
即 rule_factory 里 zipline 每 bar 用 history 窗口调同一函数,与全区间预筛口径一致。

有限窗规则(bollinger/rsi/stochastic)理应精确一致;EMA 类(macd/momentum_rule)靠
足够大的 lookback 缓冲让 EMA seed 衰减到不翻整数信号——若出现差异日,本脚本会列出,
即证明缓冲不够(需调大 signals._EMA_BUFFER)。

跑法(无需 pytest):
    .venv-zipline/bin/python -m zipline_lab.rules.test_parity
    .venv-zipline/bin/python -m zipline_lab.rules.test_parity --ticker AAPL --start 2013-01-02 --end 2017-12-29
退出码 0 = 全过。
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from zipline_lab.rules.signals import (
    DEFAULT_PARAMS,
    SIGNAL_FUNCS,
    compute_signal,
    is_stateful,
    lookback_bars,
)

_OHLCV = ["open", "high", "low", "close", "volume"]


def load_ohlcv(ticker: str, start: str, end: str, bundle: str = "stockdb") -> pd.DataFrame:
    """从 bundle 拉 OHLCV(close≡adj_close),索引为 tz-naive 交易日。"""
    from zipline.data import bundles
    from zipline.utils.calendar_utils import get_calendar

    from zipline_lab.bundle_stockdb import register_stockdb_bundle

    register_stockdb_bundle()
    bd = bundles.load(bundle)
    cal = get_calendar("XNYS")
    sess = cal.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
    asset = bd.asset_finder.lookup_symbol(ticker, as_of_date=None)
    arr = bd.equity_daily_bar_reader.load_raw_arrays(
        _OHLCV, sess[0], sess[-1], [asset.sid]
    )
    idx = pd.DatetimeIndex([s.tz_localize(None) if s.tz else s for s in sess])
    return pd.DataFrame({c: arr[i][:, 0] for i, c in enumerate(_OHLCV)}, index=idx)


def per_bar_signal(rule_name: str, prices: pd.DataFrame, params: dict) -> pd.Series:
    """逐 bar 模拟:每个 t 只喂 trailing lookback 窗口,调同一函数取末格。"""
    look = lookback_bars(rule_name, {**DEFAULT_PARAMS[rule_name], **(params or {})})
    out = []
    n = len(prices)
    for t in range(n):
        lo = max(0, t - look + 1)
        window = prices.iloc[lo : t + 1]
        s = compute_signal(rule_name, window, params)
        out.append(int(s.iloc[-1]))
    return pd.Series(out, index=prices.index, dtype=int)


def check_rule(rule_name: str, prices: pd.DataFrame, params: dict | None = None):
    params = params or {}
    full = compute_signal(rule_name, prices, params).astype(int)
    perbar = per_bar_signal(rule_name, prices, params)
    diff = full[full != perbar]
    ok = len(diff) == 0
    return ok, full, perbar, diff


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="AAPL")
    ap.add_argument("--start", default="2013-01-02")
    ap.add_argument("--end", default="2017-12-29")
    ap.add_argument("--bundle", default="stockdb")
    args = ap.parse_args()

    prices = load_ohlcv(args.ticker, args.start, args.end, args.bundle)
    print(f"[parity] {args.ticker} {args.start}..{args.end}  bars={len(prices)}\n")

    all_ok = True
    for rule in SIGNAL_FUNCS:
        ok, full, perbar, diff = check_rule(rule, prices)
        params = DEFAULT_PARAMS[rule]
        look = lookback_bars(rule, params)
        # 状态机规则(sma8,或含 stateful 成员的 weighted)lookback 是「全段哨兵」——逐 bar
        # 用自起点起的扩张窗口重放;显示成 full-seg 而非那个 10^9 巨数(见 signals.is_stateful)。
        look_disp = "full-seg" if is_stateful(rule, params) else f"{look:4d}"
        nz = int((full != 0).sum())
        status = "PASS" if ok else f"FAIL ({len(diff)} diff days)"
        print(f"  {rule:14s} look={look_disp:>8s} nonzero={nz:4d}/{len(full)}  -> {status}")
        if not ok:
            all_ok = False
            head = diff.index[:10]
            for d in head:
                print(f"       {d.date()}  full={int(full.loc[d])}  perbar={int(perbar.loc[d])}")
            if len(diff) > 10:
                print(f"       ... {len(diff) - 10} more")

    print()
    print("ALL PASS" if all_ok else "SOME FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
