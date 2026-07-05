"""时间序列动量(12-1),Chan《Algorithmic Trading》的 time-series momentum 模板。

信号口径:
  - price = adj_close(bundle 已把 adj_close 烧进 close,故 data.history "price" ≡ adj_close);
  - 月度重估:每月首个交易日按 12-1 动量决定满仓/空仓,持有到下次重估(hold≡重估频率);
  - 动量 = 过去 lookback_months 个月剔除最近 skip_months 个月的收益,用日 bar 近似月
    (21 交易日/月):mom = P(t-skip_days)/P(t-lookback_days) - 1;mom > 0 → 满仓(sig=1),
    否则空仓(sig=0)。默认 12/1 → lookback_days=252、skip_days=21。

warm-up 门闩(与 sma_crossover 同思路):data.history 会回看模拟开始之前的 bundle 数据,
而 IS/OOS 分两段独立跑时,不能让 t-lookback_days 的价格落到本段起点之前。故用 context 的
bar 计数(含当天)做门闩:要触到 t-lookback_days 的价格需 window=lookback_days+1 根 bar,
bar_count < window 时不动作;第 window 个 bar 起,history(window) 恰落在 [本段起点 .. 当天]
内,无越界回看。

执行时序(已核对 zipline 3.1.1 源码):用户 handle_data 以 prepend=True 注册,
每个 bar 先于 schedule_function 触发。故 handle_data 先自增 bar_count 并 record,
随后同一 bar 内 rebalance 触发时 bar_count 已含当天 —— 两处门闩口径一致。

局限:月度近似用固定 21 交易日/月(非真日历月);单标的、无风险预算/波动目标(Chan 原文
含波动缩放),此处为模板验证故简化为满仓/空仓二元。
"""
from __future__ import annotations

import numpy as np
from zipline.api import (
    date_rules,
    order_target_percent,
    record,
    schedule_function,
    symbol,
    time_rules,
)

from zipline_lab.strategy_base import run_strategy

_TRADING_DAYS_PER_MONTH = 21


def make_momentum_factory(params: dict):
    """factory:params 需含 ticker,可选 lookback_months / skip_months。

    纯函数——只闭包 params,不读文件/DB/网络。返回 (initialize, handle_data)。
    """
    ticker = params["ticker"]
    lookback_months = int(params.get("lookback_months", 12))
    skip_months = int(params.get("skip_months", 1))
    if lookback_months <= 0 or skip_months < 0:
        raise ValueError("lookback_months must be > 0 and skip_months must be >= 0.")
    if skip_months >= lookback_months:
        raise ValueError("skip_months must be smaller than lookback_months.")

    lookback_days = lookback_months * _TRADING_DAYS_PER_MONTH  # 12 → 252
    skip_days = skip_months * _TRADING_DAYS_PER_MONTH  # 1 → 21
    # 需触到 t-lookback_days 的价格:history(window) 的第 0 根即 t-lookback_days
    window = lookback_days + 1

    def _momentum_signal(context, data):
        """返回 (sig, mom);warm-up 未满则返回 (None, None)。

        history(window) 索引 -window..-1(-1 为当天 t):
          P(t-lookback_days) = closes[-(lookback_days+1)] = closes[0]
          P(t-skip_days)     = closes[-(skip_days+1)]
        """
        if context.bar_count < window:
            return None, None
        closes = data.history(context.asset, "price", window, "1d")
        p_start = closes.iloc[-(lookback_days + 1)]
        p_end = closes.iloc[-(skip_days + 1)]
        mom = p_end / p_start - 1.0
        sig = 1 if mom > 0 else 0
        return sig, mom

    def initialize(context):
        context.asset = symbol(ticker)
        context.window = window
        context.bar_count = 0  # 含当天的 bar 计数(handle_data 每 bar 自增)
        # 月度重估:每月首个交易日开盘登记(在 initialize 内登记即可,strategy_base 只透传
        # initialize/handle_data;rebalance 通过 schedule_function 挂到 event_manager)
        schedule_function(
            _rebalance,
            date_rule=date_rules.month_start(),
            time_rule=time_rules.market_open(),
        )

    def _rebalance(context, data):
        # 此刻 bar_count 已含当天(handle_data 先于 schedule_function 触发)
        sig, _ = _momentum_signal(context, data)
        if sig is None:
            return  # warm-up 未满,不动作
        order_target_percent(context.asset, float(sig))

    def handle_data(context, data):
        context.bar_count += 1
        sig, mom = _momentum_signal(context, data)
        # signal 是后续对齐/观察脚本的关键输出,每日都记(warm-up 期记 0/NaN)
        record(
            signal=(sig if sig is not None else 0),
            momentum=(mom if mom is not None else np.nan),
            price=data.current(context.asset, "price"),
        )

    return initialize, handle_data


def run_momentum_zipline(
    ticker: str,
    start,
    end,
    *,
    lookback_months: int = 12,
    skip_months: int = 1,
    capital: float = 10_000.0,
    bundle: str = "stockdb",
):
    """便捷入口:走 strategy_base.run_strategy 跑 12-1 动量,返回每日 performance DataFrame。"""
    params = {
        "ticker": ticker,
        "lookback_months": lookback_months,
        "skip_months": skip_months,
    }
    return run_strategy(
        make_momentum_factory,
        params,
        start=start,
        end=end,
        capital=capital,
        bundle=bundle,
    )
