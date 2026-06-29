"""冒烟测试:zipline 3.1.1 + 旧 quandl bundle 端到端跑通一个 SMA crossover。

目的只在证明「环境 + bundle + 回测引擎」能端到端产出业绩,不追求策略好坏。
标的 AAPL,区间 2013–2017(quandl WIKI 数据止于 2018-03)。

跑:  .venv-zipline/bin/python zipline_lab/smoke_test_quandl.py
"""
import pandas as pd
from zipline import run_algorithm
from zipline.api import order_target_percent, symbol, record
from zipline.utils.calendar_utils import get_calendar

START = pd.Timestamp("2013-01-02")
END = pd.Timestamp("2017-12-29")
SHORT, LONG = 20, 50


def initialize(context):
    context.asset = symbol("AAPL")


def handle_data(context, data):
    short_ma = data.history(context.asset, "price", SHORT, "1d").mean()
    long_ma = data.history(context.asset, "price", LONG, "1d").mean()
    if short_ma > long_ma:
        order_target_percent(context.asset, 1.0)
    else:
        order_target_percent(context.asset, 0.0)
    record(price=data.current(context.asset, "price"), short_ma=short_ma, long_ma=long_ma)


def main():
    # 零基准,避免 zipline 默认去联网拉 benchmark(经典坑)
    cal = get_calendar("XNYS")
    sessions = cal.sessions_in_range(START, END)
    if getattr(sessions, "tz", None) is not None:
        sessions = sessions.tz_localize(None)
    benchmark = pd.Series(0.0, index=sessions)

    perf = run_algorithm(
        start=START, end=END,
        initialize=initialize, handle_data=handle_data,
        capital_base=100_000,
        bundle="quandl",
        benchmark_returns=benchmark,
        data_frequency="daily",
    )

    ret = perf["portfolio_value"].iloc[-1] / perf["portfolio_value"].iloc[0] - 1
    n_trades = int(perf["transactions"].map(len).sum())
    print("=== 冒烟测试结果 ===")
    print("回测天数      :", len(perf))
    print("起始组合价值  :", round(perf["portfolio_value"].iloc[0], 2))
    print("结束组合价值  :", round(perf["portfolio_value"].iloc[-1], 2))
    print(f"总收益        : {ret:.1%}")
    print("成交笔数      :", n_trades)


if __name__ == "__main__":
    main()
