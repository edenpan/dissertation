"""接法三证伪回测:S1/S2 双信号 × Q5−Q1 多空 / Q5 纯多,等权,年度调仓(phase2-spec §4)。

引擎 zipline-reloaded,bundle `techdiff`(bundle_techdiff.py)。复用 strategy_base 的
零收益 benchmark + tz-naive 约定(此处直接调 run_algorithm,同款套路)。

信号 = screener 的 signals.parquet(gvkey→ticker 经 crosswalk.csv + crosswalk_v2 accepts)。
可交易域 = 映射到 bundle 内 ticker 的 gvkey 子集,组合形成时在**可交易域内**重排分位。

调仓规则(段一滚动 + 段二冻结,一条式覆盖):
  持有日历年 Y 的信号年 signal_year = min(Y-1, 2019)。
    Y ≤ 2019 → 滚动(段一);Y ≥ 2020 → 全部指向 2019 冻结名单(段二)。
  每年首个交易日(1 月 month_start)按 signal_year 的分位重建仓、等权。
  S1: 可交易域内按 S1 直接分五分位。
  S2: 规模中性化——先按 total_jobs 分五桶,桶内对 S2 排百分位,合并后再分五分位(防退化为大公司组合)。
  S2 起始 Y=2012(signal_year 2011;2010 S2 为 NULL 左删失)。

口径:多空 = 多 Q5(各 +1/n)空 Q1(各 −1/n),组合日收益 ≈ mean(Q5)−mean(Q1);
      纯多 = 多 Q5(各 +1/n)。退市/停牌由 zipline auto_close 处理,消失即空出权重。
产出:逐月组合收益 CSV(每 signal×construction 一列)→ 供 evaluate.py 做 FF3 归因。

用法:
    export TECHDIFF_PRICES_DIR=/home/eden/code/altas/screener/papers/tech-diffusion/data/prices
    .venv-zipline/bin/python zipline_lab/techdiff_backtest.py \
        --out /home/eden/code/altas/screener/papers/tech-diffusion/data/monthly_returns.csv
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from zipline import run_algorithm
from zipline.api import (order_target_percent, schedule_function, date_rules,
                         time_rules, symbol)
from zipline.api import set_commission, set_slippage
from zipline.errors import SymbolNotFound
from zipline.finance.commission import PerShare
from zipline.finance.slippage import FixedSlippage
from zipline.utils.calendar_utils import get_calendar

from zipline_lab.bundle_techdiff import register_techdiff_bundle, _prices_dir

SCREENER = "/home/eden/code/altas/screener/papers/tech-diffusion"
SIGNALS = os.path.join(SCREENER, "data", "signals.parquet")
CROSSWALK = os.path.join(SCREENER, "data", "crosswalk.csv")
WHITELIST = os.path.join(SCREENER, "data", "crosswalk_v2_whitelist.csv")
FREEZE_YEAR = 2019

# module-level config stash (run_algorithm's initialize takes no extra args)
_CFG: dict = {}


def _yf_ticker(t: str) -> str:
    return t.strip().upper().replace(".", "-")


def load_gvkey_ticker() -> dict[int, str]:
    """gvkey -> yfinance ticker,crosswalk matched + whitelist accepts。"""
    m: dict[int, str] = {}
    cw = pd.read_csv(CROSSWALK)
    for _, r in cw.iterrows():
        t = str(r["ticker"]).strip()
        if t and t.lower() != "nan":
            m[int(r["gvkey"])] = _yf_ticker(t)
    if os.path.exists(WHITELIST):
        wl = pd.read_csv(WHITELIST)
        for _, r in wl[wl["verdict"] == "accept"].iterrows():
            t = str(r["candidate_ticker"]).strip()
            if t and t.lower() != "nan":
                m[int(r["gvkey"])] = _yf_ticker(t)
    return m


def bundle_tickers() -> set[str]:
    """bundle 内真实可交易 ticker 集(manifest status=ok 且 parquet 存在)。"""
    man = os.path.join(_prices_dir(), "_manifest.csv")
    ok = set()
    if os.path.exists(man):
        df = pd.read_csv(man)
        for _, r in df[df["status"] == "ok"].iterrows():
            ok.add(str(r["ticker"]).strip().upper())
    return ok


def _quintile_labels(score: pd.Series) -> pd.Series:
    """稳定五分位(强制等大小桶,避免 S2 大量并列导致 qcut 边界重复)。0=Q1..4=Q5。"""
    r = score.rank(method="first")
    return pd.qcut(r, 5, labels=False)


def build_targets(signals: pd.DataFrame, gv2tk: dict[int, str],
                  tradable: set[str]) -> dict[str, dict[int, dict]]:
    """对每个 signal_year 产出 S1/S2 的 Q1/Q5 ticker 列表(可交易域内分位)。

    返回 {'S1': {year: {'q5':[..], 'q1':[..], 'n':int}}, 'S2': {...}}。"""
    out = {"S1": {}, "S2": {}}
    sig = signals.copy()
    sig["ticker"] = sig["gvkey"].map(lambda g: gv2tk.get(int(g)))
    sig = sig[sig["ticker"].notna() & sig["ticker"].isin(tradable)]

    for yr, grp in sig.groupby("year"):
        yr = int(yr)
        # --- S1: 可交易域内直接五分位 ---
        s1 = grp[grp["S1"].notna()].copy()
        if len(s1) >= 25:
            s1["q"] = _quintile_labels(s1["S1"])
            out["S1"][yr] = {
                "q5": s1.loc[s1["q"] == 4, "ticker"].tolist(),
                "q1": s1.loc[s1["q"] == 0, "ticker"].tolist(),
                "n": len(s1),
            }
        # --- S2: 规模中性化(total_jobs 分桶 → 桶内 S2 百分位 → 合并再分位) ---
        s2 = grp[grp["S2"].notna()].copy()
        if yr >= 2011 and len(s2) >= 25:
            s2["tj_bucket"] = _quintile_labels(s2["total_jobs"])
            s2["s2_pct"] = s2.groupby("tj_bucket")["S2"].rank(pct=True)
            s2["q"] = _quintile_labels(s2["s2_pct"])
            out["S2"][yr] = {
                "q5": s2.loc[s2["q"] == 4, "ticker"].tolist(),
                "q1": s2.loc[s2["q"] == 0, "ticker"].tolist(),
                "n": len(s2),
            }
    return out


def _resolve(tickers):
    """ticker list -> tradable zipline assets(SymbolNotFound 跳过)。"""
    assets = []
    for t in dict.fromkeys(tickers):  # dedup, keep order
        try:
            assets.append(symbol(t))
        except SymbolNotFound:
            continue
    return assets


def make_algo(signal: str, construction: str):
    """construction ∈ {'ls','long'};signal ∈ {'S1','S2'}。"""
    targets = _CFG["targets"][signal]

    def initialize(context):
        set_slippage(FixedSlippage(spread=0.0))
        set_commission(PerShare(cost=0.0, min_trade_cost=0.0))
        context.cur_longs = []
        context.cur_shorts = []
        schedule_function(rebalance, date_rules.month_start(),
                          time_rules.market_open(minutes=30))

    def rebalance(context, data):
        if data.current_session.month != 1:  # 每年首个交易月才调仓
            return
        hold_year = data.current_session.year
        sig_year = min(hold_year - 1, FREEZE_YEAR)
        conf = targets.get(sig_year)
        if not conf:
            return
        longs = _resolve(conf["q5"])
        shorts = _resolve(conf["q1"]) if construction == "ls" else []

        # 清空不在新目标里的老仓
        newset = set(longs) | set(shorts)
        for a in list(context.portfolio.positions):
            if a not in newset and data.can_trade(a):
                order_target_percent(a, 0.0)

        if longs:
            wl = 1.0 / len(longs)
            for a in longs:
                if data.can_trade(a):
                    order_target_percent(a, wl)
        if shorts:
            ws = -1.0 / len(shorts)
            for a in shorts:
                if data.can_trade(a):
                    order_target_percent(a, ws)
        context.cur_longs, context.cur_shorts = longs, shorts

    return initialize


def run_one(signal: str, construction: str, start, end) -> pd.Series:
    cal = get_calendar("XNYS")
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    sessions = cal.sessions_in_range(start_ts, end_ts)
    bench = pd.Series(0.0, index=sessions)
    initialize = make_algo(signal, construction)
    perf = run_algorithm(
        start=start_ts, end=end_ts, initialize=initialize,
        capital_base=10_000_000.0, data_frequency="daily",
        bundle="techdiff", benchmark_returns=bench, trading_calendar=cal,
    )
    return perf["returns"]


def to_monthly(daily: pd.Series) -> pd.Series:
    d = daily.copy()
    d.index = pd.to_datetime(d.index)
    return (1.0 + d).resample("ME").prod() - 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(SCREENER, "data", "monthly_returns.csv"))
    ap.add_argument("--end", default=None, help="回测末日(默认 bundle 末 session)")
    args = ap.parse_args()

    register_techdiff_bundle()
    gv2tk = load_gvkey_ticker()
    tradable = bundle_tickers()
    print(f"[universe] gvkey->ticker {len(gv2tk)} | bundle tradable tickers {len(tradable)}")

    signals = pd.read_parquet(SIGNALS)
    _CFG["targets"] = build_targets(signals, gv2tk, tradable)
    for s in ("S1", "S2"):
        yrs = sorted(_CFG["targets"][s])
        print(f"[targets] {s}: signal-years {yrs}")
        for y in yrs:
            c = _CFG["targets"][s][y]
            print(f"    {y}: n={c['n']} Q5={len(c['q5'])} Q1={len(c['q1'])}")

    cal = get_calendar("XNYS")
    today = pd.Timestamp.today().normalize()
    end = args.end or str(cal.sessions_in_range("2010-12-01", today)[-1].date())

    series = {}
    runs = [("S1", "ls", "2011-01-01"), ("S1", "long", "2011-01-01"),
            ("S2", "ls", "2012-01-01"), ("S2", "long", "2012-01-01")]
    for signal, constr, start in runs:
        col = f"{signal}_{'Q5mQ1' if constr == 'ls' else 'Q5long'}"
        print(f"\n=== running {col} ({start}..{end}) ===", flush=True)
        try:
            daily = run_one(signal, constr, start, end)
            series[col] = to_monthly(daily)
            print(f"    {col}: {len(series[col])} months, "
                  f"cum={((1+series[col]).prod()-1)*100:.1f}%")
        except Exception as e:  # noqa: BLE001
            print(f"    {col} FAILED: {type(e).__name__}: {e}", flush=True)
            import traceback
            traceback.print_exc()

    out = pd.DataFrame(series)
    out.index.name = "month"
    out.to_csv(args.out)
    print(f"\n[done] wrote {out.shape[0]} months × {out.shape[1]} series -> {args.out}")


if __name__ == "__main__":
    main()
