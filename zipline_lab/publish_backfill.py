"""回填稳定实验到 altas_media.bt_*(CLI 可重跑,幂等)。

覆盖(IS=2013-01-02..2019-12-31,OOS=2020-01-02..2025-12-19,bundle=stockdb):
  1. sma_crossover AAPL/MSFT/KO ×(20,50)× IS/OOS;
  2. sma_crossover AAPL (25,190)(walkforward IS 冠军)× IS/OOS;
  3. momentum_ts AAPL × IS/OOS;pairs_bollinger KO/PEP × IS/OOS(默认参);
  4. buy_hold 基线:上述每个 (symbol,segment) 一条(单标的等权;KO/PEP 配对 50/50 不再平衡);
  5. report_md:对齐/walkforward/momentum/pairs 报告塞进代表性 run;塞不上的报告各建
     strategy='report' 元 run(segment='FULL',metrics={})挂全文。

★本轮不回填 PSO/HK 成果(pso_vs_random_overfit.md / hk_reverify.md 由别的 agent 处理)。

用法:
  set -a; source .env; set +a            # (可选)DATA_DB_* 仅 ingest 才需要,读已 ingest 的 bundle 不需要
  ALTAS_DB_PASSWORD=... .venv-zipline/bin/python -m zipline_lab.publish_backfill
  # 或让 publish.py 从 private.keys 取密码(需 ALTAS_ADMIN_ENV_FILE 指向含 eden 的 .env)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text

from zipline_lab.sma_crossover import run_sma_zipline
from zipline_lab.momentum_ts import run_momentum_zipline
from zipline_lab.pairs_bollinger import run_pairs_zipline
from zipline_lab.walkforward import bundle_close
from zipline_lab.publish import publish_run, get_engine

BUNDLE = "stockdb"
IS_START, IS_END = "2013-01-02", "2019-12-31"
OOS_START, OOS_END = "2020-01-02", "2025-12-19"
ALIGN_START, ALIGN_END = "2013-01-02", "2017-12-29"  # 对齐报告区间
CAPITAL = 10_000.0

SEGMENTS = {"IS": (IS_START, IS_END), "OOS": (OOS_START, OOS_END)}
REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def _report(name: str) -> str:
    return (REPORTS_DIR / name).read_text(encoding="utf-8")


def _rel(name: str) -> str:
    return f"zipline_lab/reports/{name}"


# 代表性 run 的报告归属(仅 IS 段挂):(strategy, symbol) -> 报告文件名
SMA_REP_REPORTS = {
    ("AAPL", 20, 50): "align_AAPL_20_50_2013-01-02_2017-12-29.md",
    ("MSFT", 20, 50): "align_MSFT_20_50_2013-01-02_2017-12-29.md",
    ("KO", 20, 50): "align_KO_20_50_2013-01-02_2017-12-29.md",
    ("AAPL", 25, 190): "walkforward_AAPL.md",
}

# 塞不上任何 run 的报告 → strategy='report' 元 run
META_REPORTS = [
    # (symbol, params, report_file)
    ("AAPL", {"report": "align_AAPL_10_30", "short_window": 10, "long_window": 30},
     "align_AAPL_10_30_2013-01-02_2017-12-29.md"),
    ("MSFT", {"report": "align_MSFT_10_30", "short_window": 10, "long_window": 30},
     "align_MSFT_10_30_2013-01-02_2017-12-29.md"),
    ("KO", {"report": "align_KO_10_30", "short_window": 10, "long_window": 30},
     "align_KO_10_30_2013-01-02_2017-12-29.md"),
    ("ALL", {"report": "align_summary"}, "align_summary.md"),
]


def _buy_hold_equity_single(symbol: str, start: str, end: str) -> pd.Series:
    close = bundle_close(symbol, start, end, bundle=BUNDLE).astype(float)
    return CAPITAL * (close / close.iloc[0])


def _buy_hold_equity_pair(a: str, b: str, start: str, end: str) -> pd.Series:
    ca = bundle_close(a, start, end, bundle=BUNDLE).astype(float)
    cb = bundle_close(b, start, end, bundle=BUNDLE).astype(float)
    df = pd.concat([ca.rename("a"), cb.rename("b")], axis=1).dropna()
    # 初始 50/50,不再平衡:两腿各买 CAPITAL/2 的名义,持有
    eq = CAPITAL * (0.5 * df["a"] / df["a"].iloc[0] + 0.5 * df["b"] / df["b"].iloc[0])
    return eq


def main() -> None:
    published: list[int] = []

    # ---- 1 & 2: sma_crossover ----
    sma_specs = [("AAPL", 20, 50), ("MSFT", 20, 50), ("KO", 20, 50), ("AAPL", 25, 190)]
    for sym, sw, lw in sma_specs:
        for seg, (s, e) in SEGMENTS.items():
            perf = run_sma_zipline(sym, s, e, short_window=sw, long_window=lw,
                                   capital=CAPITAL, bundle=BUNDLE)
            rmd = None
            if seg == "IS" and (sym, sw, lw) in SMA_REP_REPORTS:
                rmd = _report(SMA_REP_REPORTS[(sym, sw, lw)])
            rid = publish_run(
                strategy="sma_crossover", symbol=sym, segment=seg, start=s, end=e,
                params={"short_window": sw, "long_window": lw},
                perf=perf, report_md=rmd,
                source="sma_crossover.run_sma_zipline", bundle=BUNDLE)
            published.append(rid)
            print(f"  sma {sym} ({sw},{lw}) {seg} -> run_id={rid}")

    # ---- 3a: momentum_ts AAPL ----
    for seg, (s, e) in SEGMENTS.items():
        perf = run_momentum_zipline("AAPL", s, e, capital=CAPITAL, bundle=BUNDLE)
        rmd = _report("momentum_AAPL.md") if seg == "IS" else None
        rid = publish_run(
            strategy="momentum_ts", symbol="AAPL", segment=seg, start=s, end=e,
            params={"lookback_months": 12, "skip_months": 1},
            perf=perf, report_md=rmd,
            source="momentum_ts.run_momentum_zipline", bundle=BUNDLE)
        published.append(rid)
        print(f"  momentum AAPL {seg} -> run_id={rid}")

    # ---- 3b: pairs_bollinger KO/PEP ----
    for seg, (s, e) in SEGMENTS.items():
        perf = run_pairs_zipline("KO", "PEP", s, e, capital=CAPITAL, bundle=BUNDLE)
        rmd = _report("pairs_KO_PEP.md") if seg == "IS" else None
        rid = publish_run(
            strategy="pairs_bollinger", symbol="KO/PEP", segment=seg, start=s, end=e,
            params={"lookback": 20, "beta_window": 60, "entry_z": 2.0, "exit_z": 0.5},
            perf=perf, report_md=rmd,
            source="pairs_bollinger.run_pairs_zipline", bundle=BUNDLE)
        published.append(rid)
        print(f"  pairs KO/PEP {seg} -> run_id={rid}")

    # ---- 4: buy_hold 基线 ----
    for sym in ("AAPL", "MSFT", "KO"):
        for seg, (s, e) in SEGMENTS.items():
            eq = _buy_hold_equity_single(sym, s, e)
            rid = publish_run(
                strategy="buy_hold", symbol=sym, segment=seg, start=s, end=e,
                params={}, equity=eq,
                source="publish_backfill:bundle_close", bundle=BUNDLE)
            published.append(rid)
            print(f"  buy_hold {sym} {seg} -> run_id={rid}")
    for seg, (s, e) in SEGMENTS.items():
        eq = _buy_hold_equity_pair("KO", "PEP", s, e)
        rid = publish_run(
            strategy="buy_hold", symbol="KO/PEP", segment=seg, start=s, end=e,
            params={}, equity=eq,
            source="publish_backfill:bundle_close(50/50)", bundle=BUNDLE)
        published.append(rid)
        print(f"  buy_hold KO/PEP {seg} -> run_id={rid}")

    # ---- 5: 塞不上的报告 → 元 run ----
    for sym, params, fname in META_REPORTS:
        rid = publish_run(
            strategy="report", symbol=sym, segment="FULL",
            start=ALIGN_START, end=ALIGN_END,
            params=params, metrics={}, report_md=_report(fname),
            source=_rel(fname), bundle=BUNDLE)
        published.append(rid)
        print(f"  report meta {fname} -> run_id={rid}")

    # ---- 汇总 ----
    _summary()


def _summary() -> None:
    eng = get_engine()
    with eng.connect() as c:
        n_run = c.execute(text("SELECT COUNT(*) FROM bt_run")).scalar()
        n_eq = c.execute(text("SELECT COUNT(*) FROM bt_equity")).scalar()
        n_sig = c.execute(text("SELECT COUNT(*) FROM bt_signal")).scalar()
        rows = c.execute(text(
            "SELECT run_id, strategy, symbol, segment, "
            "JSON_EXTRACT(metrics,'$.total_return') AS tr "
            "FROM bt_run ORDER BY run_id")).mappings().all()
    print("\n==== 表行数 ====")
    print(f"bt_run={n_run}  bt_equity={n_eq}  bt_signal={n_sig}")
    print("\n==== run 清单 ====")
    print(f"{'run_id':>6} | {'strategy':<14} | {'symbol':<8} | {'seg':<4} | total_return")
    print("-" * 62)
    for r in rows:
        tr = r["tr"]
        trs = f"{float(tr) * 100:+.2f}%" if tr is not None else "—"
        print(f"{r['run_id']:>6} | {r['strategy']:<14} | {r['symbol']:<8} | "
              f"{r['segment']:<4} | {trs}")


if __name__ == "__main__":
    main()
