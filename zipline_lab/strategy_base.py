"""策略模板层:把书里的策略以统一接口喂进 zipline,信号逻辑与执行环境分离。

这一层是后续迁 nautilus(灰度/实盘)的接缝——策略只负责"给定行情产出信号+下单意图",
执行环境(引擎、滑点、手续费、日历、基准)全由本层封装,换引擎时策略侧不动。

策略契约(factory 必须遵守):
  - factory 是纯函数:factory(params: dict) -> (initialize, handle_data)。
    不得在 factory 体内读文件/DB/网络,不得依赖闭包外的可变全局;所有输入走 params。
  - handle_data(context, data) 里取数只准用 data.history / data.current(zipline 行情 API),
    严禁外读文件/DB——保证信号在回测/纸交易/实盘三处口径一致、可复现。
  - initialize(context) 负责登记 asset、初始化 context 状态;滑点/手续费不用自己设,
    本层已在外层套壳统一注入(见下),需要覆盖时通过 run_strategy 的 slippage/commission 传。

zipline-reloaded 3.1.1 约定:全程 tz-naive;benchmark 外传零收益序列(规避联网拉基准)。
"""
from __future__ import annotations

from typing import Callable, Optional

import pandas as pd
from zipline import run_algorithm
from zipline.api import set_commission, set_slippage
from zipline.finance.commission import PerShare
from zipline.finance.slippage import FixedSlippage
from zipline.utils.calendar_utils import get_calendar

Factory = Callable[[dict], tuple]


def _to_naive_ts(x) -> pd.Timestamp:
    """str / Timestamp / datetime → tz-naive pd.Timestamp(3.x 全程 tz-naive)。"""
    ts = pd.Timestamp(x)
    if ts.tz is not None:
        ts = ts.tz_localize(None)
    return ts


def run_strategy(
    factory: Factory,
    params: dict,
    *,
    start,
    end,
    capital: float = 10_000.0,
    bundle: str = "stockdb",
    slippage=None,
    commission=None,
    calendar_name: str = "XNYS",
) -> pd.DataFrame:
    """跑一个策略,返回 zipline 的每日 performance DataFrame(含 record 出的列)。

    factory(params) -> (initialize, handle_data);slippage/commission 缺省为零成本,
    传入自定义对象即覆盖。start/end 接受 str 或 Timestamp,内部转 tz-naive。
    """
    start_ts, end_ts = _to_naive_ts(start), _to_naive_ts(end)
    user_initialize, handle_data = factory(params)

    slip = slippage if slippage is not None else FixedSlippage(spread=0.0)
    comm = commission if commission is not None else PerShare(cost=0.0, min_trade_cost=0.0)

    def initialize(context):
        # set_slippage/set_commission 只能在 initialize 内调用 → 给 factory 的 initialize 套壳
        set_slippage(slip)
        set_commission(comm)
        user_initialize(context)

    # 零收益基准序列:索引用交易日历的 sessions,规避 run_algorithm 默认联网拉基准。
    sessions = get_calendar(calendar_name).sessions_in_range(start_ts, end_ts)
    benchmark_returns = pd.Series(0.0, index=sessions)

    return run_algorithm(
        start=start_ts,
        end=end_ts,
        initialize=initialize,
        handle_data=handle_data,
        capital_base=capital,
        data_frequency="daily",
        bundle=bundle,
        benchmark_returns=benchmark_returns,
    )
