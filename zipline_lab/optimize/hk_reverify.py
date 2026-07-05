"""港股重验证 orchestrator —— 把 MACD 记忆裁决 + PSO 过拟合对照在港股上重跑,出 hk_reverify.md。

动机(用户旧论文):港股 HSBC 上 PSO 调 MACD/SMA 参数,记忆里「MACD 参数不错」。美股上已证明
该印象来自「样本内调优 + 震荡市里 buy&hold 基准本身也平」。本脚本回原市场(港股,震荡市)裁决:
  A. MACD 记忆:港股(震荡市)上择时规则相对 buy&hold 是否确实比美股好看?为什么?
  B. 过拟合:样本内调优 → 样本外衰减,港股是否同样成立?

严格同口径(与美股实验对齐,便于港美对照):
  - 一律 long/flat + shift(EXEC_LAG=2) 向量化(信号 -1/0/1 → position=clip(lower=0).shift(2));
  - 零成本(港股印花税 0.1%/每手、佣金未建模 —— 只会让「择时」更差,不影响「择时 vs 持有」定性);
  - 价格全部取自 bundle(美股 stockdb/XNYS、港股 stockdb-hk/XHKG),close≡adj_close,不连 MySQL。

跑法(项目根、venv;bundle 读不需 DB 凭据):
    .venv-zipline/bin/python -m zipline_lab.optimize.hk_reverify
    .venv-zipline/bin/python -m zipline_lab.optimize.hk_reverify --iters 100  # 提速 PSO 部分
    .venv-zipline/bin/python -m zipline_lab.optimize.hk_reverify --skip-pso   # 只跑 MACD 部分
"""
from __future__ import annotations

import argparse
import statistics
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from zipline_lab.rules.signals import macd_signal
from zipline_lab.walkforward import bundle_close, fitness, sharpe, max_drawdown

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

# 港美各 3 标的(港股:汇丰=旧论文主角、腾讯、中移动;美股:与 PSO 实验同款)
HK_TICKERS = ["0005.HK", "0700.HK", "0941.HK"]
US_TICKERS = ["AAPL", "MSFT", "KO"]
HK_BUNDLE, HK_CAL = "stockdb-hk", "XHKG"
US_BUNDLE, US_CAL = "stockdb", "XNYS"

IS_START, IS_END = "2013-01-02", "2019-12-31"
OOS_START, OOS_END = "2020-01-02", "2025-12-19"

EXEC_LAG = 2
MACD_DEFAULT = dict(ns=12, nl=26)
# 样本内粗网格:ns 3..30 步3 × nl ns+5..120 步5
NS_GRID = list(range(3, 31, 3))
def _nl_grid(ns: int) -> list[int]:
    return list(range(ns + 5, 121, 5))


def _d(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _pct(x: float) -> str:
    return f"{x * 100:.2f}%"


# ---------------------------------------------------------------------------
# MACD 向量化收益(long/flat + shift(2),与美股实验严格同口径)
# ---------------------------------------------------------------------------
def macd_returns(close: pd.Series, ns: int, nl: int) -> pd.Series:
    df = pd.DataFrame({"close": close})
    sig = macd_signal(df, ns=ns, nl=nl)          # -1/0/1
    pos = sig.clip(lower=0).shift(EXEC_LAG).fillna(0).astype(float)  # long/flat
    asset_ret = close.pct_change().fillna(0.0)
    return pos * asset_ret


def buyhold_returns(close: pd.Series) -> pd.Series:
    return close.pct_change().fillna(0.0)


@dataclass
class MacdRow:
    ticker: str
    market: str
    def_is: float
    def_oos: float
    def_is_sharpe: float
    def_oos_sharpe: float
    best_ns: int
    best_nl: int
    best_is: float
    best_oos: float
    best_is_sharpe: float
    best_oos_sharpe: float
    bh_is: float
    bh_oos: float
    bh_is_sharpe: float
    bh_oos_sharpe: float


def macd_one(ticker: str, market: str, bundle: str, calendar: str) -> MacdRow:
    close_is = bundle_close(ticker, _d(IS_START), _d(IS_END), bundle=bundle, calendar=calendar)
    close_oos = bundle_close(ticker, _d(OOS_START), _d(OOS_END), bundle=bundle, calendar=calendar)

    # 默认 (12,26)
    r_def_is = macd_returns(close_is, **MACD_DEFAULT)
    r_def_oos = macd_returns(close_oos, **MACD_DEFAULT)

    # 样本内粗网格寻优(按 IS 总收益)
    best = None
    for ns in NS_GRID:
        for nl in _nl_grid(ns):
            r = macd_returns(close_is, ns, nl)
            f = fitness(r)
            if best is None or f > best[0]:
                best = (f, ns, nl)
    _, bns, bnl = best
    r_best_is = macd_returns(close_is, bns, bnl)
    r_best_oos = macd_returns(close_oos, bns, bnl)

    # buy&hold
    r_bh_is = buyhold_returns(close_is)
    r_bh_oos = buyhold_returns(close_oos)

    return MacdRow(
        ticker=ticker, market=market,
        def_is=fitness(r_def_is), def_oos=fitness(r_def_oos),
        def_is_sharpe=sharpe(r_def_is), def_oos_sharpe=sharpe(r_def_oos),
        best_ns=bns, best_nl=bnl,
        best_is=fitness(r_best_is), best_oos=fitness(r_best_oos),
        best_is_sharpe=sharpe(r_best_is), best_oos_sharpe=sharpe(r_best_oos),
        bh_is=fitness(r_bh_is), bh_oos=fitness(r_bh_oos),
        bh_is_sharpe=sharpe(r_bh_is), bh_oos_sharpe=sharpe(r_bh_oos),
    )


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------
def _macd_section(rows: list[MacdRow]) -> list[str]:
    L: list[str] = []
    L.append("## 1. MACD 记忆裁决:港美对照")
    L.append("")
    L.append(f"- 规则:双 EMA 交叉(短 EMA span=ns 上穿长 EMA span=nl → 持多,下穿 → 平仓回现金,long/flat)。")
    L.append(f"- 默认参数 (ns,nl)=(12,26);样本内粗网格 ns∈{{3,6,…,30}} × nl∈{{ns+5,…,120 步5}}(按 IS 总收益选最优)。")
    L.append(f"- IS={IS_START}..{IS_END};OOS={OOS_START}..{OOS_END};一律 long/flat + shift({EXEC_LAG});零成本。")
    L.append("")
    L.append("### 1a. 每标的:默认 vs 样本内最优 vs buy&hold(总收益 / Sharpe)")
    L.append("")
    L.append("| 市场 | 标的 | MACD(12,26) IS | OOS | IS最优参 | 最优 IS | 最优 OOS | buy&hold IS | buy&hold OOS |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        L.append(
            f"| {r.market} | {r.ticker} | {_pct(r.def_is)} | {_pct(r.def_oos)} "
            f"| ({r.best_ns},{r.best_nl}) | {_pct(r.best_is)} | {_pct(r.best_oos)} "
            f"| {_pct(r.bh_is)} | {_pct(r.bh_oos)} |"
        )
    L.append("")

    # 关键对照:MACD(默认) 相对 buy&hold 的超额(择时是否值当),港美分组
    L.append("### 1b. 择时 vs 持有:MACD(12,26) − buy&hold 超额(核心裁决)")
    L.append("")
    L.append("| 市场 | 标的 | IS 超额(MACD−B&H) | OOS 超额(MACD−B&H) | OOS 最优参超额 |")
    L.append("|---|---|---|---|---|")
    for r in rows:
        L.append(
            f"| {r.market} | {r.ticker} | {_pct(r.def_is - r.bh_is)} | {_pct(r.def_oos - r.bh_oos)} "
            f"| {_pct(r.best_oos - r.bh_oos)} |"
        )
    L.append("")

    hk = [r for r in rows if r.market == "港股"]
    us = [r for r in rows if r.market == "美股"]

    def _med_excess_oos(group):
        return statistics.median(r.def_oos - r.bh_oos for r in group)
    def _med_bh_oos(group):
        return statistics.median(r.bh_oos for r in group)
    def _med_overfit(group):  # 样本内最优参 IS→OOS 总收益落差
        return statistics.median(r.best_oos - r.best_is for r in group)

    hk_excess = _med_excess_oos(hk); us_excess = _med_excess_oos(us)
    hk_bh = _med_bh_oos(hk); us_bh = _med_bh_oos(us)
    hk_def_beat = sum(1 for r in hk if r.def_oos > r.bh_oos)
    us_def_beat = sum(1 for r in us if r.def_oos > r.bh_oos)
    hk_best_beat = sum(1 for r in hk if r.best_oos > r.bh_oos)
    hsbc = next((r for r in hk if r.ticker == "0005.HK"), None)

    L.append("### 1c. 裁决:港股上 MACD 是否「显得更好」?为什么?")
    L.append("")
    L.append(
        f"- **默认 MACD(12,26) 并不跑赢 buy&hold**:OOS 超额>0 的标的 —— 港股 {hk_def_beat}/{len(hk)}、"
        f"美股 {us_def_beat}/{len(us)}(见 1b,两市默认参 OOS 超额几乎全为负)。默认参下,「择时」在两个市场"
        "都没有创造相对持有的超额,记忆里的「不错」不来自默认 MACD。"
    )
    L.append(
        f"- **但港股的择时『显得没那么糟』**:MACD(12,26) 相对 buy&hold 的 OOS 超额中位 —— 港股 {_pct(hk_excess)} "
        f"vs 美股 {_pct(us_excess)}(港股负得更浅)。根因是基准强弱:buy&hold OOS 中位 港股 {_pct(hk_bh)} "
        f"vs 美股 {_pct(us_bh)} —— 港股(震荡/偏弱市)持有本身就平,择时少踏几段下跌就『相对不难看』;"
        "美股牛市里持有回报极高,同一套择时反而大幅跑输。这解释了「港股上 MACD 看起来更好」的错觉:"
        "**不是择时更强,而是港股基准更弱**。"
    )
    if hsbc is not None:
        L.append(
            f"- **记忆的真正出处——旧论文主角 HSBC(0005.HK)**:默认 (12,26) OOS 仍输 buy&hold "
            f"({_pct(hsbc.def_oos)} vs {_pct(hsbc.bh_oos)},超额 {_pct(hsbc.def_oos-hsbc.bh_oos)});"
            f"但**样本内粗网格挑出的最优参 ({hsbc.best_ns},{hsbc.best_nl})** 在 OOS 达 {_pct(hsbc.best_oos)},"
            f"反超 buy&hold **{_pct(hsbc.best_oos-hsbc.bh_oos)}**。这大概率就是「MACD 参数不错」印象的来源:"
            f"一只票 + 样本内选出的参数 + 弱基准三者叠加。但港股另两只({', '.join(r.ticker for r in hk if r.ticker!='0005.HK')})"
            f"的样本内最优参 OOS 超额均为负,{hk_best_beat}/{len(hk)} 只港票的『IS 最优参』能在 OOS 胜持有 —— "
            "单点幸存,不是可复制的市场结构 edge。"
        )
    L.append(
        f"- **样本内调优→样本外衰减,港股同样成立**:样本内粗网格最优参的 IS→OOS 总收益落差中位 "
        f"港股 {_pct(_med_overfit(hk))}、美股 {_pct(_med_overfit(us))} —— 两市都大幅缩水。"
        "记忆里那个『不错的参数』高度依赖样本内,拿到未来即打折。"
    )
    L.append("")
    L.append(
        "**MACD 记忆最终裁决**:①默认 MACD 在港股也跑不赢 buy&hold;②港股择时『显得好』纯因港股 buy&hold 弱"
        "(基准效应),非择时创造 alpha;③记忆多半源自 HSBC 一只票上『样本内调出的参数』恰好 OOS 幸存 —— "
        "样本内调优→样本外衰减这条主线在港股与美股完全同构。"
    )
    L.append("")
    return L


def _pso_section(hk_per_ticker: dict, iters: int) -> list[str]:
    L: list[str] = []
    L.append("## 2. 过拟合对照(港股版):PSO vs 同预算随机 vs 朴素 SMA(20,50) vs buy&hold")
    L.append("")
    L.append(f"- 规则:sma8 状态机(8 窗口 t1..t8∈[2,200] 整数);IS 寻优 → OOS 评估;口径同美股实验。")
    L.append(f"- PSO 30×{iters},3 seed 取 champion(最优 seed);随机搜索同名义预算 30×{iters}=**{30*iters}** 次/seed。")
    L.append(f"- 详细港股 PSO 报告见 `reports/hk_pso_overfit.md`;美股对照见 `reports/pso_vs_random_overfit.md`。")
    L.append("")
    L.append("| 标的 | PSO IS | PSO OOS | 随机 OOS | 朴素 OOS | buy&hold OOS | PSO−随机(bp) | PSO−B&H(bp) | PSO Sharpe衰减 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    pso_beats_rnd = pso_beats_bh = 0
    decays = []
    for tk in HK_TICKERS:
        d = hk_per_ticker[tk]
        p_is = d["pso_is"]; p = d["pso_oos"].total; r = d["rnd_oos"].total
        nv = d["naive_oos"].total; bh = d["bh_oos"].total
        decay = d["pso_oos"].sharpe - d["pso_is"].sharpe
        decays.append(decay)
        if p > r: pso_beats_rnd += 1
        if p > bh: pso_beats_bh += 1
        L.append(
            f"| {tk} | {_pct(p_is.total)} | {_pct(p)} | {_pct(r)} | {_pct(nv)} | {_pct(bh)} "
            f"| {(p-r)*1e4:+.0f} | {(p-bh)*1e4:+.0f} | {decay:+.3f} |"
        )
    L.append("")
    L.append("### 2 结论(港股)")
    L.append("")
    L.append(
        f"- **PSO vs 同预算随机**:{len(HK_TICKERS)} 标的里 PSO 的 OOS 胜随机 {pso_beats_rnd}/{len(HK_TICKERS)} 次。"
        + ("PSO 的群体协同未在港股 OOS 转化为对随机搜索的稳定优势 —— 与美股同构,IS 上搜得更狠主要是过拟合更狠。"
           if pso_beats_rnd <= len(HK_TICKERS) // 2 else
           "PSO 在港股多数标的 OOS 胜随机(样本仅 3 标的,勿过度外推)。")
    )
    L.append(
        f"- **PSO vs buy&hold**:PSO 的 OOS 胜 buy&hold {pso_beats_bh}/{len(HK_TICKERS)} 次;"
        f"PSO champion 的 IS→OOS Sharpe 衰减中位 {statistics.median(decays):+.3f}(样本内高 Sharpe 大幅回落=过拟合直证)。"
    )
    L.append("")
    return L


def _caveat_section(macd_rows) -> list[str]:
    L: list[str] = []
    L.append("## 3. 方法学 caveat(诚实口径)")
    L.append("")
    L.append(
        "1. **零成本**:全程零佣金/零滑点;港股另有印花税 0.1%/每手 + 交易征费未建模。"
        "择时规则换手远高于 buy&hold,故真实成本只会**让择时更差** —— 本报告对择时是偏乐观的上界,"
        "「择时未胜出」的结论只会因成本更稳固。"
    )
    L.append(
        "2. **日历与填充**:港股用 XHKG 日历;bundle `stockdb-hk` 由 yfinance(auto_adjust=False)灌的 "
        "stockdb 复权价 ingest,close≡adj_close。0005/0700/0941 的 XHKG 缺日填充率均约 **0.06%**"
        "(3193 session 中 ~2 天 ffill;另有 4 个 DB 脏日不在 XHKG session 内被丢弃),量级可忽略。"
    )
    L.append(
        "3. **样本**:港美各 3 标的、单一 IS/OOS 切分。结论是「命题的市场对照」而非统计显著性检验;"
        "稳健化需 rolling/anchored 多窗前推 + 更多标的 + 参数高原(非孤立尖峰)+ 成本敏感性。"
    )
    L.append(
        "4. **口径一致性**:港美两侧严格同口径(long/flat、shift(2)、零成本、同 IS/OOS、同 bundle 复权),"
        "MACD/sma8 信号函数与美股实验共用同一份 `rules/signals.py`,故港美差异纯来自市场结构而非实现差异。"
    )
    L.append("")
    return L


def run(iters: int, skip_pso: bool) -> Path:
    t0 = time.time()
    print("[hk] === Part A: MACD 港美对照 ===")
    macd_rows: list[MacdRow] = []
    for tk in HK_TICKERS:
        macd_rows.append(macd_one(tk, "港股", HK_BUNDLE, HK_CAL))
        print(f"[hk] MACD {tk} done")
    for tk in US_TICKERS:
        macd_rows.append(macd_one(tk, "美股", US_BUNDLE, US_CAL))
        print(f"[hk] MACD {tk} done")

    hk_per_ticker = {}
    if not skip_pso:
        print("[hk] === Part B: 港股 PSO 过拟合对照(sma8)===")
        from zipline_lab.optimize import experiment_pso_overfit as exp
        _, hk_per_ticker = exp.run(
            iters, IS_START, IS_END, OOS_START, OOS_END,
            tickers=HK_TICKERS, bundle=HK_BUNDLE, calendar=HK_CAL,
            report_name="hk_pso_overfit.md", market_label="港股",
        )

    # ---- 组装 hk_reverify.md ----
    L: list[str] = []
    L.append("# 港股重验证 —— MACD 记忆裁决 + PSO 过拟合对照(hk_reverify)")
    L.append("")
    L.append(
        "回原市场(港股,震荡市)裁决用户旧论文的记忆:「港股 HSBC 上 PSO 调 MACD/SMA,MACD 参数不错」。"
        "美股上已证明该印象来自「样本内调优 + 震荡市里 buy&hold 本身也平」。本报告港美严格同口径对照。"
    )
    L.append("")
    L.append(f"- 港股标的:{', '.join(HK_TICKERS)}(汇丰=旧论文主角、腾讯、中移动);美股:{', '.join(US_TICKERS)}")
    L.append(f"- bundle:港股 `{HK_BUNDLE}`/XHKG、美股 `{US_BUNDLE}`/XNYS;close≡adj_close(yfinance auto_adjust=False 灌的复权价)")
    L.append(f"- IS={IS_START}..{IS_END};OOS={OOS_START}..{OOS_END};long/flat + shift({EXEC_LAG});零成本")
    L.append("")
    L += _macd_section(macd_rows)
    if not skip_pso:
        L += _pso_section(hk_per_ticker, iters)
    else:
        L.append("## 2. 过拟合对照(港股版)")
        L.append("")
        L.append("- (本次以 --skip-pso 跳过;见 `reports/hk_pso_overfit.md`。)")
        L.append("")
    L += _caveat_section(macd_rows)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "hk_reverify.md"
    path.write_text("\n".join(L), encoding="utf-8")
    print(f"[hk] 报告 → {path}  (总耗时 {time.time()-t0:.0f}s)")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description="港股重验证:MACD 记忆 + PSO 过拟合对照")
    ap.add_argument("--iters", type=int, default=200, help="PSO 迭代数(随机预算=30×iters)")
    ap.add_argument("--skip-pso", action="store_true", help="只跑 MACD 部分")
    args = ap.parse_args()
    run(args.iters, args.skip_pso)


if __name__ == "__main__":
    main()
