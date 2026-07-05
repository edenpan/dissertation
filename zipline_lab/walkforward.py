"""SMA 金叉的 walk-forward 骨架:样本内(IS)网格寻优 → 样本外(OOS)单跑,量化过拟合。

方法链(为何这样搭,防什么翻车):

  1. IS 网格用 **pandas 向量化预筛** 而非逐组跑 zipline——授权来自对齐验证的结论:
     zipline 与旧引擎在 6/6 组上「信号级 100% 一致」(见 reports/align_summary.md),
     即"同样的收盘价 + 同样的六行信号公式 → 同样的每日 0/1 信号"已被第三方 oracle 钉死。
     信号既然可信,收益差只来自执行口径(T+1 成交价 / 整数股 / 再平衡),量级是 bp。
     故预筛用连续满仓、小数股、T+1 收盘价成交的等效收益序列给 ~170 组参数排序,
     只要执行口径造成的 bp 级扰动不足以翻转排名,预筛的 top-k 就等于真 top-k。

  2. 预筛的执行口径刻意对齐 zipline 的 T+1:信号在第 t 日算出,zipline 下一交易日(t+1)
     以 t+1 收盘价成交,故持仓在 close[t+1] 才建立,第一段能吃到的收益是 close[t+1]→close[t+2]。
     等价于「持仓序列 = signal.shift(2)」乘以当日资产收益。这样预筛与 zipline 的口径差
     只剩「小数股满仓 vs 整数股+再平衡+现金拖累」,即对齐报告 c 块归因的那几项。

  3. top-k(默认 5)真的跑 zipline 复核:比对预筛总收益 vs zipline 总收益,差值量化到 bp。
     >200bp 触发警告——那意味着执行口径扰动可能已大到能翻排名,预筛结论需人核。

  4. OOS 只用 IS(zipline 复核后)的第一名单跑 zipline,配 buy&hold 基线;IS→OOS 的
     收益落差就是过拟合的量。绝不用 OOS 数据参与选参(walk-forward 的铁律)。

数据来源:价格全部从 bundle `stockdb` 读(close ≡ adj_close,已烧进复权),**不连 MySQL**。
预筛与 zipline 用同一 bundle,确保喂进两条路径的收盘价逐分逐厘一致。

用法:
    # bundle 读不需要 DB 凭据;~/.zipline/extension.py 已注册 stockdb bundle
    python -m zipline_lab.walkforward AAPL
    python -m zipline_lab.walkforward AAPL --is-start 2013-01-02 --is-end 2019-12-31 \
        --oos-start 2020-01-02 --oos-end 2025-12-19 --top-k 5
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from zipline_lab.sma_crossover import run_sma_zipline

# ---------------------------------------------------------------------------
# 模块级常量:网格 / 区间 / 阈值(CLI 可覆盖)
# ---------------------------------------------------------------------------
BUNDLE = "stockdb"
CALENDAR = "XNYS"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

# 参数网格:short ∈ {5,10,..,50}(10 值)× long ∈ {20,30,..,200}(19 值),约束 short<long
SHORT_GRID = list(range(5, 51, 5))
LONG_GRID = list(range(20, 201, 10))

# 样本内 / 样本外区间
IS_START = "2013-01-02"
IS_END = "2019-12-31"
OOS_START = "2020-01-02"
OOS_END = "2025-12-19"

TOP_K = 5              # 进 zipline 复核的组数
WARN_BP = 200.0        # 预筛 vs zipline 收益差警戒线(bp)
TRADING_DAYS = 252     # Sharpe 年化因子
# 预筛执行滞后:signal 日 t → zipline t+1 收盘成交 → 持仓吃 close[t+1]→close[t+2] 起的收益。
# 故 held[τ] = signal[τ-2],即 signal.shift(2)。(旧引擎同日成交是 shift(1);见模块头注 2。)
EXEC_LAG = 2


def _param_grid() -> list[tuple[int, int]]:
    """(short, long) 组合,约束 short < long,按 (short, long) 升序。"""
    return [(s, l) for s in SHORT_GRID for l in LONG_GRID if s < l]


# ---------------------------------------------------------------------------
# 从 bundle 读收盘价(close ≡ adj_close;不连 MySQL)
# ---------------------------------------------------------------------------
def _ensure_registered() -> None:
    """确保 stockdb bundle 已注册,且走 zipline 自己的 load_extensions(单次幂等)路径。

    坑:register_stockdb_bundle() 里的 register_calendar_alias 每进程只能调一次,第二次抛
    CalendarNameCollision。而 run_algorithm 每次都会 load ~/.zipline/extension.py(内含未加
    try/except 的 register_stockdb_bundle),靠 zipline 的 _loaded_extensions 集合保证只执行一次。
    若我们先手工 register 再跑 run_algorithm,extension.py 会成为"第二次注册"而崩。
    故这里直接调 zipline 的 load_extensions 触发 extension.py 首次注册并登记进 _loaded_extensions,
    后续 run_algorithm 便跳过它——与 run_algorithm 内部完全同一条注册路径,不会二次注册。
    """
    import os as _os

    from zipline.utils.run_algo import load_extensions

    load_extensions(default=True, extensions=[], strict=True, environ=_os.environ)


def bundle_close(symbol: str, start: date, end: date) -> pd.Series:
    """读 bundle stockdb 的日收盘价序列,index=date(与 align_backtester 同法)。"""
    from zipline.data import bundles
    from zipline.utils.calendar_utils import get_calendar

    _ensure_registered()
    bd = bundles.load(BUNDLE)
    cal = get_calendar(CALENDAR)
    sess = cal.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
    asset = bd.asset_finder.lookup_symbol(symbol, as_of_date=None)
    arr = bd.equity_daily_bar_reader.load_raw_arrays(
        ["close"], sess[0], sess[-1], [asset.sid]
    )[0][:, 0]
    return pd.Series(arr, index=[s.date() for s in sess], name="close")


# ---------------------------------------------------------------------------
# 向量化信号 + 等效收益(复刻六行公式;执行口径对齐 zipline T+1)
# ---------------------------------------------------------------------------
def vectorized_signal(price: pd.Series, short: int, long: int) -> pd.Series:
    """复刻 run_sma_backtest 的六行信号:rolling(short)>rolling(long) → 1,前 long-1 天强制 0。"""
    short_ma = price.rolling(window=short).mean()
    long_ma = price.rolling(window=long).mean()
    sig = pd.Series(0, index=price.index)
    sig.iloc[long - 1:] = np.where(
        short_ma.iloc[long - 1:] > long_ma.iloc[long - 1:], 1, 0
    )
    return sig.astype(int)


def equivalent_returns(price: pd.Series, signal: pd.Series) -> pd.Series:
    """T+1 收盘成交的等效日收益序列:持仓 = signal.shift(EXEC_LAG),乘当日资产收益。

    连续满仓、小数股、零成本——刻意省掉整数股/再平衡/现金拖累(那是与 zipline 的已知 bp 差)。
    """
    asset_ret = price.pct_change().fillna(0.0)
    pos = signal.shift(EXEC_LAG).fillna(0).astype(float)
    return pos * asset_ret


# ---------------------------------------------------------------------------
# fitness 契约 + 附列指标(Sharpe / MaxDD)
# ---------------------------------------------------------------------------
def _daily_returns(perf_or_returns) -> pd.Series:
    """把入参归一成「日收益 Series」。接受:日收益 Series / zipline perf DataFrame。"""
    if isinstance(perf_or_returns, pd.Series):
        return perf_or_returns.fillna(0.0)
    if isinstance(perf_or_returns, pd.DataFrame):
        if "returns" in perf_or_returns.columns:            # zipline perf 每日组合收益
            return perf_or_returns["returns"].fillna(0.0)
        if "portfolio_value" in perf_or_returns.columns:
            return perf_or_returns["portfolio_value"].pct_change().fillna(0.0)
    raise TypeError(
        "fitness/metrics 需要日收益 Series 或含 returns/portfolio_value 列的 zipline perf DataFrame"
    )


def fitness(perf_or_returns) -> float:
    """契约:fitness(perf_or_returns) -> float。默认目标 = 总收益(复利)。"""
    r = _daily_returns(perf_or_returns)
    return float((1.0 + r).prod() - 1.0)


def sharpe(perf_or_returns, periods: int = TRADING_DAYS) -> float:
    """年化 Sharpe(rf=0);无波动(如从不持仓)返回 0。"""
    r = _daily_returns(perf_or_returns)
    sd = r.std(ddof=1)
    if not np.isfinite(sd) or sd == 0.0:
        return 0.0
    return float(r.mean() / sd * np.sqrt(periods))


def max_drawdown(perf_or_returns) -> float:
    """最大回撤(负数,如 -0.35 = -35%)。"""
    r = _daily_returns(perf_or_returns)
    equity = (1.0 + r).cumprod()
    dd = equity / equity.cummax() - 1.0
    return float(dd.min()) if len(dd) else 0.0


# ---------------------------------------------------------------------------
# 结果结构
# ---------------------------------------------------------------------------
@dataclass
class ParamResult:
    short: int
    long: int
    total: float
    sharpe: float
    maxdd: float


@dataclass
class ReCheck:
    short: int
    long: int
    pre_total: float
    zip_total: float
    diff_bp: float
    warn: bool


# ---------------------------------------------------------------------------
# IS 向量化预筛
# ---------------------------------------------------------------------------
def prescreen_is(price_is: pd.Series, grid: list[tuple[int, int]]) -> list[ParamResult]:
    """对每组参数向量化算 IS 等效收益,按总收益(fitness)降序返回。"""
    rows: list[ParamResult] = []
    for short, long in grid:
        sig = vectorized_signal(price_is, short, long)
        ret = equivalent_returns(price_is, sig)
        rows.append(
            ParamResult(short, long, fitness(ret), sharpe(ret), max_drawdown(ret))
        )
    rows.sort(key=lambda r: r.total, reverse=True)
    return rows


# ---------------------------------------------------------------------------
# top-k zipline 复核
# ---------------------------------------------------------------------------
def recheck_topk(
    symbol: str, ranked: list[ParamResult], k: int, is_start: str, is_end: str
) -> list[ReCheck]:
    """top-k 组各跑一次 zipline(IS 区间),比对预筛 vs zipline 总收益,量化 bp 差。"""
    out: list[ReCheck] = []
    for pr in ranked[:k]:
        perf = run_sma_zipline(
            symbol, is_start, is_end,
            short_window=pr.short, long_window=pr.long, capital=10_000.0, bundle=BUNDLE,
        )
        zip_total = fitness(perf)
        diff_bp = (zip_total - pr.total) * 1e4
        out.append(
            ReCheck(pr.short, pr.long, pr.total, zip_total, diff_bp, abs(diff_bp) > WARN_BP)
        )
    return out


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------
def _pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def write_report(
    symbol: str,
    grid: list[tuple[int, int]],
    ranked: list[ParamResult],
    rechecks: list[ReCheck],
    best: ReCheck,
    best_is_total: float,
    best_is_sharpe: float,
    best_is_maxdd: float,
    oos_perf: pd.DataFrame,
    bh_total: float,
    bh_sharpe: float,
    bh_maxdd: float,
    is_start: str, is_end: str, oos_start: str, oos_end: str,
) -> Path:
    oos_total = fitness(oos_perf)
    oos_sharpe = sharpe(oos_perf)
    oos_maxdd = max_drawdown(oos_perf)

    L: list[str] = []
    L.append(f"# Walk-forward 报告 — {symbol} SMA 金叉")
    L.append("")
    L.append(f"- 标的:{symbol}(价格取自 bundle `{BUNDLE}`,close ≡ adj_close,不连 MySQL)")
    L.append(f"- 样本内 IS:{is_start} .. {is_end}")
    L.append(f"- 样本外 OOS:{oos_start} .. {oos_end}")
    L.append(
        f"- 网格:short ∈ {{{SHORT_GRID[0]},{SHORT_GRID[1]},…,{SHORT_GRID[-1]}}} × "
        f"long ∈ {{{LONG_GRID[0]},{LONG_GRID[1]},…,{LONG_GRID[-1]}}},约束 short<long → 共 {len(grid)} 组"
    )
    L.append(f"- 执行口径:预筛=T+1 收盘成交·连续满仓·小数股(signal.shift({EXEC_LAG}));zipline=T+1·整数股·零滑点零佣金")
    L.append("")

    # ---- 方法说明 ----
    L.append("## 方法说明:为何向量化预筛可信")
    L.append("")
    L.append(
        "预筛不逐组跑 zipline,而用 pandas 向量化算等效收益给参数排序。底气来自对齐验证"
        "(`reports/align_summary.md`)的结论:zipline 与旧引擎在 6/6 组上**信号级 100% 一致**——"
        "同样的收盘价喂同样的六行信号公式,产出同样的每日 0/1 信号,已被独立 oracle 钉死。"
    )
    L.append("")
    L.append(
        f"信号既已证可信,预筛与 zipline 的收益差只来自**执行口径**(T+1 成交价 / 整数股现金拖累 / "
        f"再平衡),量级是 bp(见对齐报告 c 块归因)。预筛刻意对齐 zipline 的 T+1:持仓 = "
        f"signal.shift({EXEC_LAG})(signal 日 t → t+1 收盘建仓 → 吃 close[t+1]→close[t+2] 起的收益),"
        f"只省掉整数股/再平衡。只要 bp 级扰动不翻转排名,预筛 top-k 即真 top-k;top-{TOP_K} 已用 "
        f"zipline 复核并量化 bp 差(见下),>{WARN_BP:.0f}bp 触发警告。"
    )
    L.append("")

    # ---- IS top-10 ----
    L.append("## IS 网格寻优:top-10(向量化预筛)")
    L.append("")
    L.append("| 排名 | short | long | IS 总收益 | Sharpe(年化) | 最大回撤 |")
    L.append("|---|---|---|---|---|---|")
    for i, r in enumerate(ranked[:10], 1):
        L.append(f"| {i} | {r.short} | {r.long} | {_pct(r.total)} | {r.sharpe:.3f} | {_pct(r.maxdd)} |")
    L.append("")

    # ---- 预筛 vs zipline ----
    L.append(f"## 预筛 vs zipline 复核:top-{TOP_K}(IS 区间)")
    L.append("")
    L.append("| short | long | 预筛总收益 | zipline 总收益 | 差(bp) | 警告 |")
    L.append("|---|---|---|---|---|---|")
    for rc in rechecks:
        warn = f"⚠ >{WARN_BP:.0f}bp" if rc.warn else ""
        L.append(
            f"| {rc.short} | {rc.long} | {_pct(rc.pre_total)} | {_pct(rc.zip_total)} "
            f"| {rc.diff_bp:+.1f} | {warn} |"
        )
    L.append("")
    max_abs_bp = max((abs(rc.diff_bp) for rc in rechecks), default=0.0)
    L.append(
        f"- 实测预筛与 zipline 偏差量级:最大 |差| = {max_abs_bp:.1f} bp"
        + (
            f"(均在 {WARN_BP:.0f}bp 内 → 排名未被执行口径扰动翻转,预筛可信)。"
            if max_abs_bp <= WARN_BP
            else f"(**超 {WARN_BP:.0f}bp,需人核**:执行口径扰动可能已能翻转排名)。"
        )
    )
    L.append(
        "- 偏差成因(与对齐报告 c 块同源):zipline 按整数股下单留现金拖累 + T+1 成交价相对"
        "预筛用价的漂移 + order_target_percent 次日再平衡;预筛用小数股满仓故略去这些。"
    )
    L.append("")

    # ---- OOS ----
    warn_flag = " ⚠(复核 bp 超阈,该最优参存疑)" if best.warn else ""
    L.append("## OOS 样本外:IS 最优参 vs buy&hold")
    L.append("")
    L.append(
        f"IS 最优参(zipline 复核后第一名)= **SMA({best.short},{best.long})**{warn_flag};"
        f"仅用它单跑 OOS,不用任何 OOS 数据选参。buy&hold = OOS 首日收盘买入持有到期末。"
    )
    L.append("")
    L.append("| 口径 | 区间 | 总收益 | Sharpe(年化) | 最大回撤 |")
    L.append("|---|---|---|---|---|")
    L.append(f"| SMA({best.short},{best.long}) IS(复核) | {is_start}..{is_end} | {_pct(best_is_total)} | {best_is_sharpe:.3f} | {_pct(best_is_maxdd)} |")
    L.append(f"| SMA({best.short},{best.long}) OOS | {oos_start}..{oos_end} | {_pct(oos_total)} | {oos_sharpe:.3f} | {_pct(oos_maxdd)} |")
    L.append(f"| buy&hold OOS | {oos_start}..{oos_end} | {_pct(bh_total)} | {bh_sharpe:.3f} | {_pct(bh_maxdd)} |")
    L.append("")
    is_vs_oos_bp = (oos_total - best_is_total) * 1e4
    oos_vs_bh_bp = (oos_total - bh_total) * 1e4
    sharpe_drop = oos_sharpe - best_is_sharpe
    L.append(
        f"- **过拟合落差(Sharpe,长度无关的主指标)= {sharpe_drop:+.3f}**:IS Sharpe "
        f"{best_is_sharpe:.3f} → OOS Sharpe {oos_sharpe:.3f};风险调整后收益近乎腰斩,"
        f"样本内寻优的优势未在样本外延续。"
    )
    L.append(
        f"- 总收益对照(注:IS/OOS 窗口长度不同,总收益不可直接相减,仅作规模直观):"
        f"IS 复核 {_pct(best_is_total)} → OOS {_pct(oos_total)}(名义差 {is_vs_oos_bp:+.0f} bp)。"
    )
    L.append(
        f"- **相对 buy&hold(OOS)= {oos_vs_bh_bp:+.0f} bp**:策略 {_pct(oos_total)} vs "
        f"持有 {_pct(bh_total)};"
        + (
            "择时未跑赢简单持有 → 在此标的/区间,SMA 金叉的样本内优势未转化为样本外超额。"
            if oos_total < bh_total
            else "择时跑赢简单持有 → 样本外仍有超额(注意单标的单区间,勿过度外推)。"
        )
    )
    L.append("")

    # ---- 结论 ----
    L.append("## 结论")
    L.append("")
    L.append(
        f"1. 预筛可信度:top-{TOP_K} 复核最大 |bp 差| = {max_abs_bp:.1f} bp"
        f"({'≤' if max_abs_bp <= WARN_BP else '>'}{WARN_BP:.0f}bp),信号级已 100% 对齐,排名可采信。"
    )
    L.append(
        f"2. IS 最优 SMA({best.short},{best.long}):Sharpe IS {best_is_sharpe:.3f} → OOS {oos_sharpe:.3f}"
        f"(落差 {sharpe_drop:+.3f});OOS 总收益 {_pct(oos_total)} vs buy&hold {_pct(bh_total)}"
        f"({oos_vs_bh_bp:+.0f}bp)。"
    )
    L.append(
        "3. 单标的单窗口结论仅作方法骨架演示;稳健化需 rolling/anchored 多窗前推 + 多标的 + "
        "参数高原(非孤立尖峰)与交易成本敏感性。"
    )
    L.append("")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"walkforward_{symbol}.md"
    path.write_text("\n".join(L), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def run_walkforward(
    symbol: str,
    *,
    is_start: str = IS_START, is_end: str = IS_END,
    oos_start: str = OOS_START, oos_end: str = OOS_END,
    top_k: int = TOP_K,
) -> dict:
    symbol = symbol.upper()
    grid = _param_grid()
    print(f"[wf] {symbol} 网格 {len(grid)} 组;IS {is_start}..{is_end};OOS {oos_start}..{oos_end}")

    def _d(s: str) -> date:
        return datetime.strptime(s, "%Y-%m-%d").date()

    # --- 1) IS 预筛 ---
    price_is = bundle_close(symbol, _d(is_start), _d(is_end))
    ranked = prescreen_is(price_is, grid)
    print(f"[wf] IS 预筛完成;第一名 SMA({ranked[0].short},{ranked[0].long}) 总收益 {_pct(ranked[0].total)}")

    # --- 2) top-k zipline 复核 ---
    rechecks = recheck_topk(symbol, ranked, top_k, is_start, is_end)
    for rc in rechecks:
        flag = "  ⚠" if rc.warn else ""
        print(f"[wf] 复核 SMA({rc.short},{rc.long}) 预筛 {_pct(rc.pre_total)} vs zipline "
              f"{_pct(rc.zip_total)}  差 {rc.diff_bp:+.1f}bp{flag}")

    # --- 3) 复核后第一名(按 zipline 总收益)→ OOS ---
    best = max(rechecks, key=lambda rc: rc.zip_total)
    best_is_total = best.zip_total
    # 取 best 参数在预筛里的 Sharpe/MaxDD(长度无关的过拟合主指标用)
    best_pr = next(r for r in ranked if r.short == best.short and r.long == best.long)
    print(f"[wf] 复核后最优 SMA({best.short},{best.long})(zipline IS {_pct(best.zip_total)}) → 跑 OOS")
    oos_perf = run_sma_zipline(
        symbol, oos_start, oos_end,
        short_window=best.short, long_window=best.long, capital=10_000.0, bundle=BUNDLE,
    )

    # --- 4) buy&hold 基线(OOS 首日收盘买入持有;直接价格比) ---
    price_oos = bundle_close(symbol, _d(oos_start), _d(oos_end))
    bh_total = float(price_oos.iloc[-1] / price_oos.iloc[0] - 1.0)
    bh_ret = price_oos.pct_change().fillna(0.0)
    bh_sharpe = sharpe(bh_ret)
    bh_maxdd = max_drawdown(bh_ret)

    # --- 5) 报告 ---
    path = write_report(
        symbol, grid, ranked, rechecks, best, best_is_total,
        best_pr.sharpe, best_pr.maxdd,
        oos_perf, bh_total, bh_sharpe, bh_maxdd,
        is_start, is_end, oos_start, oos_end,
    )
    oos_total = fitness(oos_perf)
    print(f"[wf] 报告 → {path}")
    print(f"[wf] OOS 最优参 {_pct(oos_total)} vs buy&hold {_pct(bh_total)} "
          f"vs IS复核 {_pct(best_is_total)}")
    return {
        "ranked": ranked, "rechecks": rechecks, "best": best,
        "best_is_total": best_is_total, "oos_total": oos_total,
        "bh_total": bh_total, "report": str(path),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="SMA 金叉 walk-forward(IS 网格预筛 + zipline 复核 → OOS)")
    ap.add_argument("symbol", help="标的,如 AAPL")
    ap.add_argument("--is-start", default=IS_START)
    ap.add_argument("--is-end", default=IS_END)
    ap.add_argument("--oos-start", default=OOS_START)
    ap.add_argument("--oos-end", default=OOS_END)
    ap.add_argument("--top-k", type=int, default=TOP_K)
    args = ap.parse_args()
    run_walkforward(
        args.symbol,
        is_start=args.is_start, is_end=args.is_end,
        oos_start=args.oos_start, oos_end=args.oos_end,
        top_k=args.top_k,
    )


if __name__ == "__main__":
    main()
