"""Bollinger 配对均值回归,Chan《Algorithmic Trading》mean-reversion 章的配对模板。

信号口径:
  - price = adj_close(bundle 已把 adj_close 烧进 close,故 data.history "price" ≡ adj_close);
  - 对冲比:滚动 beta —— 在最近 beta_window 根 bar 上对 log 价做 OLS
    (logPa 对 logPb 回归,含截距,取斜率为 beta);
  - 价差:spread = log(Pa) - beta*log(Pb);
  - z-score:在最近 lookback 根 bar 的 spread 上算滚动均值/标准差,
    z = (spread_t - mean)/std;
  - 交易(半仓/腿):
      z >  entry_z → 空 A 多 B(A=-0.5, B=+0.5),direction=-1
      z < -entry_z → 多 A 空 B(A=+0.5, B=-0.5),direction=+1
      |z| < exit_z → 平仓,direction=0
      exit_z <= |z| <= entry_z → 维持上一状态(迟滞带,避免频繁抖动)。

对冲比选型(rolling beta 而非固定比价):
  - 选 rolling beta:随两标的关系漂移自适应,比固定 1:1 比价更贴近真实对冲敞口,
    是配对交易的常规做法;log 价回归让 beta 有"弹性/对数收益比"的解释、量纲一致。
  - 局限:beta 用滚动窗口估计有噪声、结构突变时滞后;更重要的是**本模板未做协整检验**
    —— Chan 原文用协整(Johansen / CADF)先筛出真正均值回归的配对再交易,这里先固定
    pair、跳过协整。TODO:接入协整检验(ADF on spread / Johansen)做配对准入与 beta 求解。

warm-up 门闩(与 sma_crossover 同思路):data.history 会回看模拟开始之前的 bundle 数据,
IS/OOS 分两段独立跑时不能越界。window=max(beta_window, lookback);bar_count < window
不动作,第 window 个 bar 起 history(window) 恰落在 [本段起点 .. 当天] 内。
"""
from __future__ import annotations

import numpy as np
from zipline.api import order_target_percent, record, symbol

from zipline_lab.strategy_base import run_strategy


def make_pairs_factory(params: dict):
    """factory:params 需含 ticker_a / ticker_b,可选 lookback / beta_window / entry_z / exit_z。

    纯函数——只闭包 params,不读文件/DB/网络。返回 (initialize, handle_data)。
    """
    ticker_a = params["ticker_a"]
    ticker_b = params["ticker_b"]
    lookback = int(params.get("lookback", 20))
    beta_window = int(params.get("beta_window", 60))
    entry_z = float(params.get("entry_z", 2.0))
    exit_z = float(params.get("exit_z", 0.5))
    if lookback <= 1 or beta_window <= 1:
        raise ValueError("lookback and beta_window must be > 1.")
    if not (0.0 <= exit_z < entry_z):
        raise ValueError("require 0 <= exit_z < entry_z.")

    window = max(beta_window, lookback)

    def _zscore(context, data):
        """返回 (z, spread, beta);warm-up 未满则返回 (nan, nan, nan)。"""
        if context.bar_count < window:
            return np.nan, np.nan, np.nan
        pa = data.history(context.asset_a, "price", window, "1d")
        pb = data.history(context.asset_b, "price", window, "1d")
        la = np.log(pa.values)
        lb = np.log(pb.values)
        # 滚动 beta:最近 beta_window 根做 logPa 对 logPb 的 OLS(含截距)
        xb = lb[-beta_window:]
        ya = la[-beta_window:]
        X = np.column_stack([np.ones_like(xb), xb])
        # 最小二乘:coef = [alpha, beta]
        coef, *_ = np.linalg.lstsq(X, ya, rcond=None)
        beta = coef[1]
        spread_full = la - beta * lb  # 用当前 beta 复算整段 spread
        spread_win = spread_full[-lookback:]
        mu = spread_win.mean()
        sd = spread_win.std(ddof=0)
        spread_t = spread_full[-1]
        if sd == 0 or not np.isfinite(sd):
            return np.nan, spread_t, beta
        z = (spread_t - mu) / sd
        return z, spread_t, beta

    def initialize(context):
        context.asset_a = symbol(ticker_a)
        context.asset_b = symbol(ticker_b)
        context.window = window
        context.bar_count = 0  # 含当天的 bar 计数
        context.direction = 0  # 当前持仓方向:+1 多A空B / -1 空A多B / 0 平

    def handle_data(context, data):
        context.bar_count += 1
        z, spread, beta = _zscore(context, data)

        if np.isfinite(z):
            # 迟滞状态机:先判平仓,再判进场
            if abs(z) < exit_z:
                context.direction = 0
            elif z > entry_z:
                context.direction = -1  # 价差过高 → 空 A 多 B
            elif z < -entry_z:
                context.direction = 1   # 价差过低 → 多 A 空 B
            # else: exit_z <= |z| <= entry_z → 维持 context.direction

            d = context.direction
            order_target_percent(context.asset_a, 0.5 * d)
            order_target_percent(context.asset_b, -0.5 * d)

        record(
            z=z,
            spread=spread,
            beta=beta,
            signal=context.direction,
        )

    return initialize, handle_data


def run_pairs_zipline(
    ticker_a: str,
    ticker_b: str,
    start,
    end,
    *,
    lookback: int = 20,
    beta_window: int = 60,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    capital: float = 10_000.0,
    bundle: str = "stockdb",
):
    """便捷入口:走 strategy_base.run_strategy 跑 Bollinger 配对,返回每日 performance DataFrame。"""
    params = {
        "ticker_a": ticker_a,
        "ticker_b": ticker_b,
        "lookback": lookback,
        "beta_window": beta_window,
        "entry_z": entry_z,
        "exit_z": exit_z,
    }
    return run_strategy(
        make_pairs_factory,
        params,
        start=start,
        end=end,
        capital=capital,
        bundle=bundle,
    )
