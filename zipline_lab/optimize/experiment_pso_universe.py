"""全池版 PSO 过拟合对照:现役恒指成分股(HSI)逐票跑 sma8 PSO vs 随机 vs 朴素 vs buy&hold。

这是 `experiment_pso_overfit.py`(3 只港股)的**全池扩展**——复用其逐票寻优/评估/复核函数,
只把编排改为「聚合优先」:81 只逐票长文没法读,故报告头部给聚合统计,尾部才给紧凑逐票表。

与旧论文的关系:旧论文(2018)对港股逐票用 PSO 调 8 参 SMA(fitness=ROI)对比 buy&hold。
本实验用现代框架在**全部现役恒指成分股**上重做该命题,量化「PSO 能否找到跑赢市场的参数」。

★幸存者偏差告警(必须写进报告):股票池用的是**今日**恒指成分股名单回看历史(2013 起),
旧论文当年(2018)的成分股名单已不可考。今日在册的都是活到现在、多数长期上涨的赢家,
用它们回测天然抬高「买入持有」基准、也抬高任何多头择时的表现——结论只作命题骨架,不代表
当年真实可投资集合。

口径(与 walkforward / experiment_pso_overfit 严格一致):
  IS=2013-01-02..2019-12-31,OOS=2020-01-02..2025-12-19;signal{0,1}→position.shift(2)×当日收益;
  PSO 30 粒子×iters,3 seed 取 champion;随机搜索同名义预算;朴素 SMA(20,50) 退化;buy&hold。
  zipline 复核:全池 162 次太贵,只**随机抽 8 只(seed=42)**复核 PSO champion 的 IS 段。

IS 数据不足跳过规则:每票有效 IS session(bundle 内首个交易日起)< 756(约 3 年)的,
  **跳过 PSO,只跑 buy&hold 供参照**,在报告「跳过清单」注明上市日期。

★环境坑(2026-07-06 发现,已 shim,见下 _patch_calendar_bounds):stockdb-hk bundle 的 bcolz
  元数据把 XHKG 日历边界冻结在 ingest 当日(2006-07-05..2027-07-05),而 exchange_calendars 的
  默认日历窗口是 [now-20y, now+1y] 滚动的,今日(07-06)起点滚到 2006-07-06 > 冻结的 2006-07-05,
  读 bundle 触发 DateOutOfBounds。本脚本进程内把 GLOBAL_DEFAULT_START 前移到 2006-01-01 绕过
  (只影响 2013 前的空 session,对 2013-2025 窗口零影响)。根治需 re-ingest 时 pin 日历边界。

跑法(项目根、venv;跑前 set -a; source .env; set +a):
    .venv-zipline/bin/python -m zipline_lab.optimize.experiment_pso_universe
    .venv-zipline/bin/python -m zipline_lab.optimize.experiment_pso_universe --iters 100
    .venv-zipline/bin/python -m zipline_lab.optimize.experiment_pso_universe --publish   # 跑完发 web
"""
from __future__ import annotations

import argparse
import os
import pickle
import random
import statistics
import time
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

# ── 环境 shim:必须在任何 bundle 读之前生效(见模块头注环境坑) ──────────────────
from exchange_calendars import exchange_calendar as _ecal


def _patch_calendar_bounds() -> None:
    """把 exchange_calendars 默认日历起点前移到 2006-01-01,让 stockdb-hk bundle 冻结的
    2006-07-05 起点仍落在日历边界内。所有默认 get_calendar 调用共享同一(加宽的)实例,
    避免 zipline 多 reader 因日历对象不一致而 AssertionError。对 2013-2025 window 零影响。"""
    _ecal.GLOBAL_DEFAULT_START = pd.Timestamp("2006-01-01")


_patch_calendar_bounds()

# ── 复用 3 票实验的逐票函数(不改其逻辑) ──────────────────────────────────────
import sqlalchemy as sa

from zipline_lab.optimize import experiment_pso_overfit as exp
from zipline_lab.rules.rule_factory import run_rule_zipline
from zipline_lab.walkforward import _ensure_registered, fitness, max_drawdown, sharpe

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
SCRATCH = Path("/tmp/claude-1000/-home-eden-code-altas/"
               "7ee7f8ab-c250-40ca-9ab7-f59271cfaef7/scratchpad")

BUNDLE = "stockdb-hk"
CALENDAR = "XHKG"
INDEX_ID = 2                       # 恒指
IS_START, IS_END = "2013-01-02", "2019-12-31"
OOS_START, OOS_END = "2020-01-02", "2025-12-19"
MIN_IS_SESSIONS = 756              # 约 3 年;不足则跳过 PSO
RECHECK_SAMPLE_N = 8               # zipline 复核抽样只数
RECHECK_SEED = 42
WARN_BP = 200.0
NAIVE_PARAMS = exp.NAIVE_PARAMS
SEEDS = exp.SEEDS


def _d(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _pct(x: float) -> str:
    return f"{x * 100:.2f}%"


# ── 股票池:现役恒指成分股(有日线数据的) ─────────────────────────────────────
def load_hsi_universe() -> list[str]:
    url = sa.URL.create(
        "mysql+pymysql",
        username=os.environ.get("DATA_DB_USER", "altas"),
        password=os.environ.get("DATA_DB_PASSWORD", ""),
        host=os.environ.get("DATA_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DATA_DB_PORT", "3306")),
        database=os.environ.get("DATA_DB_NAME", "stockdb"),
        query={"charset": "utf8mb4"},
    )
    eng = sa.create_engine(url)
    sql = (
        "SELECT ic.symbol FROM index_constituents ic "
        "JOIN symbols s ON s.symbol = ic.symbol "
        "JOIN daily_prices dp ON dp.symbol_id = s.id "
        "WHERE ic.index_id = :iid AND ic.expiry_date IS NULL "
        "GROUP BY ic.symbol ORDER BY ic.symbol"
    )
    df = pd.read_sql(sa.text(sql), eng, params={"iid": INDEX_ID})
    return df["symbol"].tolist()


def _clean_close(series: pd.Series) -> pd.Series:
    """裁掉上市前的前导 NaN/0 pad(bundle 对 asset 上市前的 session 返回 NaN)。"""
    valid = series.notna() & (series > 0)
    if not valid.any():
        return series.iloc[0:0]
    return series[valid.cummax()]


# ── 逐票结果结构 ──────────────────────────────────────────────────────────────
@dataclass
class TickerResult:
    ticker: str
    status: str                        # "ok" / "skipped" / "failed"
    is_start: str = ""                 # 有效 IS 起点(bundle 内首个交易日,IS 窗口内)
    n_is: int = 0
    listing_date: str = ""             # bundle 内首个交易日(全区间)
    # ok 时的业绩
    pso_params: list = field(default_factory=list)
    rnd_params: list = field(default_factory=list)
    pso_is: float = 0.0
    pso_oos: float = 0.0
    pso_is_sharpe: float = 0.0
    pso_oos_sharpe: float = 0.0
    rnd_oos: float = 0.0
    naive_oos: float = 0.0
    bh_oos: float = 0.0
    bh_is: float = 0.0
    # zipline 复核(仅抽样票)
    rechecked: bool = False
    recheck_diff_bp: float = 0.0
    recheck_warn: bool = False
    error: str = ""


def _listing_date(ticker: str) -> pd.Timestamp | None:
    from zipline.data import bundles
    _ensure_registered()
    bd = bundles.load(BUNDLE)
    try:
        a = bd.asset_finder.lookup_symbol(ticker, as_of_date=None)
        return pd.Timestamp(a.start_date)
    except Exception:
        return None


def run_one(ticker: str, iters: int, do_recheck: bool) -> TickerResult:
    """单票:读价→(足够 IS 则 PSO+随机+朴素)+B&H。异常在上层 catch。"""
    close_is = _clean_close(
        exp.bundle_close(ticker, _d(IS_START), _d(IS_END), bundle=BUNDLE, calendar=CALENDAR))
    close_oos = _clean_close(
        exp.bundle_close(ticker, _d(OOS_START), _d(OOS_END), bundle=BUNDLE, calendar=CALENDAR))
    ld = _listing_date(ticker)
    listing = ld.date().isoformat() if ld is not None else ""
    n_is = len(close_is)

    # B&H(OOS / IS)——所有票都算
    def _bh(close: pd.Series) -> tuple[float, float]:
        if len(close) < 2:
            return 0.0, 0.0
        total = float(close.iloc[-1] / close.iloc[0] - 1.0)
        return total, sharpe(close.pct_change().fillna(0.0))
    bh_oos_total, _ = _bh(close_oos)
    bh_is_total, _ = _bh(close_is)

    is_start_eff = close_is.index[0].isoformat() if n_is else ""

    # IS 不足 → 跳过 PSO,只留 B&H 参照
    if n_is < MIN_IS_SESSIONS:
        return TickerResult(
            ticker=ticker, status="skipped", is_start=is_start_eff, n_is=n_is,
            listing_date=listing, bh_oos=bh_oos_total, bh_is=bh_is_total,
        )

    objective = exp._make_objective(close_is)
    pso_champ = exp.optimize_one("PSO", objective, SEEDS, iters)
    rnd_champ = exp.optimize_one("Random", objective, SEEDS, iters)

    pso_is = exp._perf(close_is, pso_champ.params)
    pso_oos = exp._perf(close_oos, pso_champ.params)
    rnd_oos = exp._perf(close_oos, rnd_champ.params)
    naive_oos = exp._perf(close_oos, NAIVE_PARAMS)

    res = TickerResult(
        ticker=ticker, status="ok", is_start=is_start_eff, n_is=n_is, listing_date=listing,
        pso_params=list(pso_champ.params.values()), rnd_params=list(rnd_champ.params.values()),
        pso_is=pso_is.total, pso_oos=pso_oos.total,
        pso_is_sharpe=pso_is.sharpe, pso_oos_sharpe=pso_oos.sharpe,
        rnd_oos=rnd_oos.total, naive_oos=naive_oos.total,
        bh_oos=bh_oos_total, bh_is=bh_is_total,
    )

    if do_recheck:
        # ★用有效 IS 起点(而非 IS_START):IS 窗口内才上市的票(如 0288.HK 2014-08-05)从
        # IS_START 起跑 zipline 会在上市前下单而崩("Cannot order ... started trading on")。
        # 预筛 pre_is_total 本就算在裁剪后的 close_is 上,起点一致才是同口径比对。
        rc = exp.zipline_recheck(ticker, pso_champ.params, pso_is.total, is_start_eff, IS_END,
                                 bundle=BUNDLE, calendar=CALENDAR)
        res.rechecked = True
        res.recheck_diff_bp = rc["diff_bp"]
        res.recheck_warn = rc["warn"]
    return res


def run_universe(iters: int) -> tuple[list[TickerResult], dict]:
    tickers = load_hsi_universe()
    print(f"[uni] 现役恒指成分股(有数据):{len(tickers)} 只")

    # 先判每票是否够 IS,再从 runnable 里抽 8 只做 zipline 复核(seed=42)
    # 但 runnable 需先读一遍;为省一次读,复核抽样在得到 runnable 名单后再定——
    # 这里两阶段:第一阶段快速判 n_is(读价),第二阶段跑。为简单,单阶段:先算 runnable 判定用
    # listing_date(不必读全价),抽样定死后逐票跑。
    from zipline.data import bundles
    _ensure_registered()
    bd = bundles.load(BUNDLE)
    from zipline.utils.calendar_utils import get_calendar
    cal = get_calendar(CALENDAR)
    sess_is = cal.sessions_in_range(pd.Timestamp(IS_START), pd.Timestamp(IS_END))

    runnable = []
    for tk in tickers:
        try:
            a = bd.asset_finder.lookup_symbol(tk, as_of_date=None)
            sd = pd.Timestamp(a.start_date)
            n_is = int((sess_is >= sd).sum()) if sd <= sess_is[-1] else 0
        except Exception:
            n_is = 0
        if n_is >= MIN_IS_SESSIONS:
            runnable.append(tk)
    rng = random.Random(RECHECK_SEED)
    sample = set(rng.sample(runnable, min(RECHECK_SAMPLE_N, len(runnable))))
    print(f"[uni] runnable={len(runnable)} 只;zipline 复核抽样(seed={RECHECK_SEED}): {sorted(sample)}")

    results: list[TickerResult] = []
    t0 = time.time()
    for i, tk in enumerate(tickers, 1):
        t1 = time.time()
        try:
            r = run_one(tk, iters, do_recheck=(tk in sample))
        except Exception as ex:  # noqa: BLE001 —— 单票崩溃不许静默丢票
            tb = traceback.format_exc()
            print(f"[uni] !! {tk} FAILED: {ex}\n{tb}")
            r = TickerResult(ticker=tk, status="failed", error=f"{type(ex).__name__}: {ex}")
        results.append(r)
        tag = {"ok": "OK", "skipped": "SKIP", "failed": "FAIL"}[r.status]
        extra = ""
        if r.status == "ok":
            extra = (f"PSO_OOS={_pct(r.pso_oos)} B&H_OOS={_pct(r.bh_oos)} "
                     f"{'[recheck %+.0fbp]' % r.recheck_diff_bp if r.rechecked else ''}")
        elif r.status == "skipped":
            extra = f"listing={r.listing_date} n_is={r.n_is}"
        print(f"[uni] [{i:2d}/{len(tickers)}] {tk} {tag} {extra}  ({time.time()-t1:.1f}s)")

    meta = dict(
        n_total=len(tickers), iters=iters, elapsed=time.time() - t0,
        sample=sorted(sample), tickers=tickers,
    )
    # 落盘 pickle(publish 阶段/重跑复用,避免重算)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with open(SCRATCH / "hsi_universe_results.pkl", "wb") as fh:
        pickle.dump((results, meta), fh)
    print(f"[uni] 结果 pickle → {SCRATCH/'hsi_universe_results.pkl'}  (总耗时 {meta['elapsed']:.0f}s)")
    return results, meta


# ── 聚合报告 ──────────────────────────────────────────────────────────────────
def _q(vals: list[float], p: float) -> float:
    return float(np.percentile(vals, p)) if vals else float("nan")


def write_report(results: list[TickerResult], meta: dict) -> Path:
    ok = [r for r in results if r.status == "ok"]
    skipped = [r for r in results if r.status == "skipped"]
    failed = [r for r in results if r.status == "failed"]
    n_ok = len(ok)
    iters = meta["iters"]
    budget = 30 * iters

    L: list[str] = []
    L.append("# 全池 PSO 过拟合对照 —— 现役恒指成分股(sma8）")
    L.append("")
    L.append(
        "旧论文(2018)命题的全池现代重做:对**全部现役恒指成分股**逐票用 PSO 调 8 参 SMA 规则"
        "(fitness=总收益)对比 buy&hold,量化「PSO 能否找到跑赢市场的参数」。"
    )
    L.append("")
    L.append("## 实验设定")
    L.append("")
    L.append(f"- 股票池:现役恒指成分股(index_id={INDEX_ID}, expiry_date IS NULL,且库内有日线),"
             f"共 **{meta['n_total']}** 只;bundle `{BUNDLE}`/{CALENDAR},close≡adj_close,不连 MySQL 取价。")
    L.append(f"- 样本内 IS:{IS_START}..{IS_END};样本外 OOS:{OOS_START}..{OOS_END}(OOS 绝不参与选参)。")
    L.append(f"- 规则:sma8 状态机(8 窗口 t1..t8∈[2,200] 整数);signal{{0,1}}→position.shift(2)×当日收益"
             f"(T+1 收盘成交等效,同 walkforward)。")
    L.append(f"- PSO:30 粒子×{iters} iters(名义预算 {budget} 次/seed),3 seed 取 champion(最优 seed);"
             f"随机搜索同名义预算 {budget} 次/seed;朴素 = SMA(20,50) 退化;buy&hold OOS 首日买入持有。")
    L.append(f"- IS 数据不足跳过:有效 IS session(bundle 内上市日起)< {MIN_IS_SESSIONS}(约 3 年)的票"
             f"**跳过 PSO,只跑 buy&hold 参照**(见跳过清单)。")
    L.append(f"- zipline 复核:全池 {n_ok}×2 次 zipline 太贵,只**随机抽 {len(meta['sample'])} 只"
             f"(seed={RECHECK_SEED})**复核 PSO champion 的 IS 段,bp 差>{WARN_BP:.0f} 警告。")
    L.append(f"- 运行:{n_ok} 只跑 PSO、{len(skipped)} 只跳过、{len(failed)} 只失败;总耗时 {meta['elapsed']:.0f}s。")
    L.append("")
    L.append("### ★幸存者偏差告警(结论前必读)")
    L.append("")
    L.append(
        "股票池用的是**今日**恒指成分股名单回看历史(2013 起),**旧论文当年(2018)的成分股名单已不可考**。"
        "今日在册的都是活到现在、多数长期上涨的赢家——用它们回测天然抬高「买入持有」基准,也抬高任何"
        "多头择时的表现。本报告结论只作**命题骨架**(PSO 样本内调参→样本外衰减这一结构),不代表当年"
        "真实可投资集合的收益,更不能外推为「该策略能赚钱」。"
    )
    L.append("")

    if n_ok == 0:
        L.append("> 无可跑 PSO 的标的,聚合统计略。")
    else:
        # 聚合口径
        pso_beat_bh = sum(1 for r in ok if r.pso_oos > r.bh_oos)
        rnd_beat_bh = sum(1 for r in ok if r.rnd_oos > r.bh_oos)
        naive_beat_bh = sum(1 for r in ok if r.naive_oos > r.bh_oos)
        pso_vs_rnd_win = sum(1 for r in ok if r.pso_oos > r.rnd_oos)
        pso_vs_rnd_tie = sum(1 for r in ok if r.pso_oos == r.rnd_oos)
        pso_vs_rnd_loss = n_ok - pso_vs_rnd_win - pso_vs_rnd_tie
        decays = [r.pso_oos_sharpe - r.pso_is_sharpe for r in ok]
        excess = [r.pso_oos - r.bh_oos for r in ok]

        L.append("## 聚合统计(样本外 OOS,核心裁决)")
        L.append("")
        L.append("### 跑赢 buy&hold 的只数/占比")
        L.append("")
        L.append("| 方法 | OOS 跑赢 B&H 只数 | 占比 |")
        L.append("|---|---|---|")
        for name, cnt in [("PSO champion", pso_beat_bh), ("随机搜索 champion", rnd_beat_bh),
                          ("朴素 SMA(20,50)", naive_beat_bh)]:
            L.append(f"| {name} | {cnt}/{n_ok} | {cnt/n_ok*100:.1f}% |")
        L.append("")
        L.append("### PSO vs 同预算随机搜索(OOS 总收益,逐票对拍)")
        L.append("")
        L.append(f"- 胜 / 平 / 负 = **{pso_vs_rnd_win} / {pso_vs_rnd_tie} / {pso_vs_rnd_loss}**"
                 f"(共 {n_ok} 只)。PSO 的 OOS 中位总收益 {_pct(statistics.median(r.pso_oos for r in ok))}"
                 f" vs 随机 {_pct(statistics.median(r.rnd_oos for r in ok))}。")
        L.append("")
        L.append("### IS→OOS Sharpe 衰减(PSO champion,过拟合的量)")
        L.append("")
        L.append("| 分位 | Sharpe 衰减(OOS−IS) |")
        L.append("|---|---|")
        for lab, p in [("Q1(25%)", 25), ("中位(50%)", 50), ("Q3(75%)", 75)]:
            L.append(f"| {lab} | {_q(decays, p):+.3f} |")
        L.append(f"| 均值 | {statistics.mean(decays):+.3f} |")
        L.append("")
        L.append("### OOS 超额收益(PSO champion − buy&hold)分布")
        L.append("")
        L.append("| 分位 | 超额(pct) |")
        L.append("|---|---|")
        for lab, p in [("最小", 0), ("Q1(25%)", 25), ("中位(50%)", 50),
                       ("Q3(75%)", 75), ("最大", 100)]:
            L.append(f"| {lab} | {_pct(_q(excess, p))} |")
        L.append(f"| 均值 | {_pct(statistics.mean(excess))} |")
        L.append("")

        # zipline 复核抽样小结
        sampled = [r for r in ok if r.rechecked]
        if sampled:
            max_bp = max(abs(r.recheck_diff_bp) for r in sampled)
            warns = [r.ticker for r in sampled if r.recheck_warn]
            L.append("### zipline 复核(抽样)")
            L.append("")
            L.append(f"- 抽样口径:从 {len(meta['sample'])} 只 runnable 里随机抽(seed={RECHECK_SEED});"
                     f"复核 PSO champion 的 IS 段预筛 vs zipline 总收益。")
            L.append("")
            L.append("| 标的 | PSO IS 预筛 | zipline IS | 差(bp) | 警告 |")
            L.append("|---|---|---|---|---|")
            for r in sampled:
                w = f"⚠ >{WARN_BP:.0f}bp" if r.recheck_warn else ""
                L.append(f"| {r.ticker} | {_pct(r.pso_is)} | {_pct(r.pso_is + r.recheck_diff_bp/1e4)} "
                         f"| {r.recheck_diff_bp:+.1f} | {w} |")
            L.append("")
            L.append(f"- 最大 |bp 差| = {max_bp:.1f} bp"
                     + ("(均在阈内 → 预筛与 zipline 执行口径一致,IS fitness 可采信)。"
                        if not warns else
                        f"(**{', '.join(warns)} 超阈,已标警**:path-dependent 状态机的执行口径扰动,"
                        "见 signals.py sma8 注释)。"))
            L.append("")

        # 紧凑逐票表
        L.append("## 紧凑逐票表(runnable,按 OOS 超额降序)")
        L.append("")
        L.append("| 标的 | IS 起点 | PSO IS | PSO OOS | 随机 OOS | 朴素 OOS | B&H OOS | PSO−B&H | 胜B&H |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for r in sorted(ok, key=lambda x: x.pso_oos - x.bh_oos, reverse=True):
            win = "✓" if r.pso_oos > r.bh_oos else ""
            L.append(f"| {r.ticker} | {r.is_start} | {_pct(r.pso_is)} | {_pct(r.pso_oos)} "
                     f"| {_pct(r.rnd_oos)} | {_pct(r.naive_oos)} | {_pct(r.bh_oos)} "
                     f"| {(r.pso_oos-r.bh_oos)*1e4:+.0f}bp | {win} |")
        L.append("")

    # 跳过清单
    L.append("## 跳过清单(IS 数据不足,只跑 buy&hold 参照)")
    L.append("")
    if skipped:
        L.append("| 标的 | 上市日期(bundle 内首个交易日) | 有效 IS session | B&H OOS |")
        L.append("|---|---|---|---|")
        for r in sorted(skipped, key=lambda x: x.listing_date):
            L.append(f"| {r.ticker} | {r.listing_date or '—'} | {r.n_is} | {_pct(r.bh_oos)} |")
    else:
        L.append("(无)")
    L.append("")

    # 失败清单
    L.append("## 失败清单(catch 记录,未静默丢票)")
    L.append("")
    if failed:
        L.append("| 标的 | 错误 |")
        L.append("|---|---|")
        for r in failed:
            L.append(f"| {r.ticker} | {r.error} |")
    else:
        L.append("(无)")
    L.append("")

    # 结论
    L.append("## 结论(诚实口径,与旧论文命题 + 7-05 三票小样本对照)")
    L.append("")
    if n_ok > 0:
        pso_beat_bh = sum(1 for r in ok if r.pso_oos > r.bh_oos)
        pso_vs_rnd_win = sum(1 for r in ok if r.pso_oos > r.rnd_oos)
        med_decay = statistics.median(r.pso_oos_sharpe - r.pso_is_sharpe for r in ok)
        med_excess = statistics.median(r.pso_oos - r.bh_oos for r in ok)
        L.append(
            f"1. **PSO 能否找到跑赢市场的参数(旧论文命题)**:全池 {n_ok} 只里,PSO champion 的 OOS 总收益"
            f"跑赢 buy&hold 仅 **{pso_beat_bh}/{n_ok}**({pso_beat_bh/n_ok*100:.0f}%),OOS 超额中位 "
            f"**{_pct(med_excess)}**。"
            + ("多数标的连不择时的 buy&hold 都跑不赢——旧论文命题在全池现役恒指上**不成立**:"
               "样本内精心调出的择时优势,样本外主要蒸发。"
               if pso_beat_bh <= n_ok / 2 else
               "过半标的 OOS 跑赢 buy&hold,但须扣除下述幸存者偏差再审视。")
        )
        L.append(
            f"2. **PSO vs 同预算随机(现代公平裁决)**:PSO 的 OOS 胜随机 **{pso_vs_rnd_win}/{n_ok}**。"
            + ("PSO 的群体协同未转化为对随机搜索的稳定 OOS 优势——在这个 8 维状态机上,它主要把 IS fitness"
               "顶得更高(过拟合更狠),不产 OOS alpha。"
               if pso_vs_rnd_win <= n_ok / 2 else
               "PSO 在过半标的上 OOS 胜随机,但 IS 早停使随机臂评估更多,该读数对 PSO 已偏保守。")
        )
        L.append(
            f"3. **过拟合的量**:PSO champion 的 IS→OOS Sharpe 衰减中位 **{med_decay:+.3f}**——"
            "样本内高 Sharpe 在样本外大幅回落,是过拟合的直接证据(评估预算越大越易撞 IS 尖峰)。"
        )
        L.append(
            "4. **与 7-05 三票小样本对照**:三票(0005/0700/0941)上曾得「PSO OOS 0/3 胜 B&H、"
            "港股择时是弱基准错觉」。全池扩到几十只后,"
            + ("这一结论**得到放大确认**:样本从 3 扩到几十,PSO 跑赢 B&H 的比例仍是少数,"
               "小样本不是偶然。"
               if pso_beat_bh <= n_ok / 2 else
               "跑赢比例较三票有所回升,但主因是全池含更多今日赢家(幸存者偏差),非择时变强。")
        )
    L.append(
        "5. **幸存者偏差(再次强调)**:池子是今日恒指成分,含幸存偏差,B&H 基准被系统性抬高;"
        "任何「跑赢/跑不赢 B&H」的读数都要放在这个抬高的基准上理解。稳健化需当年真实成分名单 + "
        "rolling/anchored 多窗前推 + 参数高原 + 交易成本(港股印花税 0.1%/手,只会让择时更差)。"
    )
    L.append("")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "hsi_universe_pso.md"
    path.write_text("\n".join(L), encoding="utf-8")
    print(f"[uni] 报告 → {path}")
    return path


# ── 发布到 web(bt 表) ────────────────────────────────────────────────────────
def publish_all(results: list[TickerResult], meta: dict, report_md: str) -> list[int]:
    from zipline_lab import publish as pub

    run_ids: list[int] = []
    ok = [r for r in results if r.status == "ok"]

    # ① 报告元 run。★口径修正:任务说 symbol=NULL,但 bt_run.symbol 是 NOT NULL(见 SHOW COLUMNS),
    #    且既有全池报告 run(run_id 24)用 symbol='ALL' 的约定 —— 故从代码/约定用 'ALL'
    #    (亦让 publish_run 的自然键幂等生效,重跑先删后插,不累积重复行)。
    rid = pub.publish_run(
        strategy="report", symbol="ALL", segment="hsi_universe",
        start=IS_START, end=OOS_END, params={}, report_md=report_md,
        bundle=BUNDLE, source="experiment_pso_universe",
        metrics={"n_ok": len(ok), "n_skipped": sum(1 for r in results if r.status == "skipped"),
                 "n_failed": sum(1 for r in results if r.status == "failed"), "iters": meta["iters"]},
    )
    run_ids.append(rid)
    print(f"[pub] report run_id={rid}")

    # ② OOS 超额最高前 3 只:PSO champion OOS zipline 复跑 + 配对 buy_hold 基线
    top3 = sorted(ok, key=lambda x: x.pso_oos - x.bh_oos, reverse=True)[:3]
    for r in top3:
        params = {f"t{i+1}": int(v) for i, v in enumerate(r.pso_params)}
        perf = run_rule_zipline("sma8", r.ticker, OOS_START, OOS_END, params=dict(params),
                                capital=10_000.0, bundle=BUNDLE, calendar_name=CALENDAR)
        rid_p = pub.publish_run(
            strategy="sma8_pso", symbol=r.ticker, segment="hsi_universe_oos",
            start=OOS_START, end=OOS_END, params=params, perf=perf,
            bundle=BUNDLE, source="experiment_pso_universe",
        )
        run_ids.append(rid_p)
        print(f"[pub] {r.ticker} PSO OOS run_id={rid_p}")

        # 配对 buy_hold 基线(同 symbol+segment):OOS 首日买入持有净值
        close_oos = _clean_close(
            exp.bundle_close(r.ticker, _d(OOS_START), _d(OOS_END), bundle=BUNDLE, calendar=CALENDAR))
        eq = 10_000.0 * (close_oos / close_oos.iloc[0])
        rid_b = pub.publish_run(
            strategy="buy_hold", symbol=r.ticker, segment="hsi_universe_oos",
            start=OOS_START, end=OOS_END, params={}, equity=eq,
            bundle=BUNDLE, source="experiment_pso_universe",
        )
        run_ids.append(rid_b)
        print(f"[pub] {r.ticker} buy_hold OOS run_id={rid_b}")

    return run_ids


def main() -> None:
    ap = argparse.ArgumentParser(description="全池 PSO 过拟合对照(现役恒指成分股)")
    ap.add_argument("--iters", type=int, default=200, help="PSO 迭代数(随机预算=30×iters)")
    ap.add_argument("--publish", action="store_true", help="跑完发布到 web(bt 表)")
    ap.add_argument("--from-pickle", action="store_true", help="跳过计算,从上次 pickle 出报告/发布")
    args = ap.parse_args()

    if args.from_pickle:
        with open(SCRATCH / "hsi_universe_results.pkl", "rb") as fh:
            results, meta = pickle.load(fh)
        print(f"[uni] 从 pickle 载入 {len(results)} 票结果")
    else:
        results, meta = run_universe(args.iters)

    path = write_report(results, meta)
    if args.publish:
        report_md = path.read_text(encoding="utf-8")
        ids = publish_all(results, meta, report_md)
        print(f"[pub] 发布完成 run_ids = {ids}")


if __name__ == "__main__":
    main()
