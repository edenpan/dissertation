"""SMA 金叉策略,复刻 strategies/backtester.py 的 run_sma_backtest 口径。

旧口径(对齐基准):
  - price = adj_close(bundle 已把 adj_close 烧进 close,故 data.history "price" ≡ adj_close);
  - short_ma / long_ma = price.rolling(short/long).mean();
  - 信号 = (short_ma > long_ma) ? 1 : 0,全仓进出;
  - **前 long_window-1 天强制信号 0**(旧口径 signals.iloc[long_window-1:] 才赋值,
    且 rolling 在切片内算、窗口不足处为 NaN)。

对齐要害——zipline 的 data.history 会回看模拟开始之前的 bundle 数据,而旧口径的
rolling 只在"从 start 起加载的切片"内计算(切片外无数据、前面是 NaN→0)。若不挡,
前 long_window-1 天的信号会与旧口径系统性不同。故用 context 里的 bar 计数(含当天)做
门闩:bar_count < long_window 时信号强制 0,第 long_window 个 bar 起才算真信号——此时
data.history(asset,"price",long_window) 恰好落在 [start .. 第 long_window 天] 内,无越界回看,
窗口与旧 rolling 完全对齐。
"""
from __future__ import annotations

from zipline.api import order_target_percent, record, symbol

from zipline_lab.strategy_base import run_strategy


def make_sma_factory(params: dict):
    """factory:params 需含 ticker / short_window / long_window,返回 (initialize, handle_data)。

    纯函数——只闭包 params,不读文件/DB/网络。
    """
    ticker = params["ticker"]
    short_window = int(params["short_window"])
    long_window = int(params["long_window"])
    if short_window <= 0 or long_window <= 0:
        raise ValueError("Moving-average windows must be positive integers.")
    if short_window >= long_window:
        raise ValueError("`short_window` must be smaller than `long_window` for SMA crossover.")

    def initialize(context):
        context.asset = symbol(ticker)
        context.short_window = short_window
        context.long_window = long_window
        context.bar_count = 0  # 含当天的 bar 计数

    def handle_data(context, data):
        context.bar_count += 1
        asset = context.asset
        if context.bar_count < context.long_window:
            # 前 long_window-1 天:旧口径 rolling 窗口不足 → 强制 0
            sig = 0
        else:
            # long_window 根 bar(含当天)对齐旧 rolling 窗口:
            #   sig = mean(last short_window) > mean(long_window)
            closes = data.history(asset, "price", context.long_window, "1d")
            sig = int(closes[-context.short_window:].mean() > closes.mean())

        # 幂等:每天把仓位摆到 100%*sig,不看当前持仓
        order_target_percent(asset, float(sig))
        # signal 是后续对齐脚本的关键输出,必须每天记
        record(signal=sig, price=data.current(asset, "price"))

    return initialize, handle_data


def run_sma_zipline(
    ticker: str,
    start,
    end,
    *,
    short_window: int = 20,
    long_window: int = 50,
    capital: float = 10_000.0,
    bundle: str = "stockdb",
):
    """便捷入口:走 strategy_base.run_strategy 跑 SMA 金叉,返回每日 performance DataFrame。"""
    params = {
        "ticker": ticker,
        "short_window": short_window,
        "long_window": long_window,
    }
    return run_strategy(
        make_sma_factory,
        params,
        start=start,
        end=end,
        capital=capital,
        bundle=bundle,
    )
