"""通用 zipline 适配器:把 rules/signals.py 的任一向量化规则接进 zipline。

设计与 sma_crossover 同思路,但把「信号逻辑」外包给 signals.py 的同一个函数——
回测(此适配器)与预筛(直接调 signals.py)共用**同一份**信号代码,是「向量化预筛
可代表 zipline」的前提;test_parity.py 对此做逐日构造性证明。

每 bar(handle_data):
  1. bar 计数门闩:bar_count < MIN_WINDOW → 信号强制 0(挡 warm-up,同 sma_crossover);
  2. 取 history(n, OHLCV),n = min(bar_count, lookback_bars);lookback = MIN_WINDOW+缓冲。
     用 min(bar_count, lookback) 而非死给 lookback:
       - 模拟早期 bundle 里可用 bar 不足 lookback 时,zipline 会返回前导 NaN 污染指标;
       - 且 test_parity 的逐 bar 模拟喂的正是「trailing lookback 或更短(不足则全历史)」窗口,
         二者语义必须一致(t < lookback 时 trailing 窗口 == 至今全历史)。
  3. 调同一个 signals 函数,取**最后一格**作当日信号;
  4. order_target_percent(asset, signal) + record(signal=..., price=...)。

★-1 语义(2026-07-05 主会话裁决):signals.py 保留旧规则 -1/0/1 三态原样记录(record),
但**下单默认 long/flat**——-1 映射为 0 仓位(平仓回现金),忠于旧 backtester 的状态机语义,
保证 PSO/网格对照与旧论文口径可比。要真做空需显式传 params={"allow_short": True},
此时 -1 → 做空 100%。无论哪种,record 的 signal 都是规则原始三态,研究侧不失真。
"""
from __future__ import annotations

from zipline.api import order_target_percent, record, symbol

from zipline_lab.rules.signals import (
    MIN_WINDOW,
    SIGNAL_FUNCS,
    DEFAULT_PARAMS,
    lookback_bars,
)
from zipline_lab.strategy_base import run_strategy

_OHLCV = ("open", "high", "low", "close", "volume")


def make_rule_factory(rule_name: str, params: dict):
    """factory:闭包 rule_name + params,返回 (initialize, handle_data)。纯函数,不读 IO。"""
    if rule_name not in SIGNAL_FUNCS:
        raise ValueError(f"unknown rule '{rule_name}'; known={sorted(SIGNAL_FUNCS)}")

    signal_fn = SIGNAL_FUNCS[rule_name]
    merged = dict(DEFAULT_PARAMS[rule_name])
    merged.update(params or {})
    ticker = merged.pop("ticker")            # ticker 只用于选标的,不进信号函数
    allow_short = bool(merged.pop("allow_short", False))  # 默认 long/flat(旧口径)
    min_win = MIN_WINDOW[rule_name](merged)
    look = lookback_bars(rule_name, merged)

    def initialize(context):
        context.asset = symbol(ticker)
        context.bar_count = 0
        context.min_win = min_win
        context.look = look

    def handle_data(context, data):
        context.bar_count += 1
        asset = context.asset

        if context.bar_count < context.min_win:
            sig = 0
        else:
            n = min(context.bar_count, context.look)
            # 每 bar 取 OHLCV 的 trailing n 根(zipline 会回看 bundle 内 start 之前的数据)
            hist = data.history(asset, list(_OHLCV), n, "1d")
            # data.history 多标的多字段返回 columns=fields 的 DataFrame;取本资产的 OHLCV
            prices = hist.copy()
            prices.columns = list(_OHLCV)
            series = signal_fn(prices, **merged)
            sig = int(series.iloc[-1])

        # 下单:默认 long/flat(-1 平仓回现金,旧口径);allow_short 时 -1 真做空
        target = float(sig) if allow_short else float(max(sig, 0))
        order_target_percent(asset, target)
        record(signal=sig, price=data.current(asset, "price"))

    return initialize, handle_data


def run_rule_zipline(
    rule_name: str,
    ticker: str,
    start,
    end,
    *,
    params: dict | None = None,
    capital: float = 10_000.0,
    bundle: str = "stockdb",
):
    """便捷入口:跑某规则的 zipline 回测,返回每日 performance DataFrame(含 record 的 signal 列)。"""
    p = dict(params or {})
    p["ticker"] = ticker
    return run_strategy(
        lambda pp: make_rule_factory(rule_name, pp),
        p,
        start=start,
        end=end,
        capital=capital,
        bundle=bundle,
    )
