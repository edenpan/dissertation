"""zipline_lab.rules —— 旧 componentTradingRules 技术指标规则的向量化迁移 + zipline 适配。

- signals.py       每规则一个向量化 <rule>_signal(prices, **params) -> pd.Series(-1/0/1)
- rule_factory.py  make_rule_factory / run_rule_zipline:通用 zipline 适配器
- test_parity.py   向量化 ⇄ 逐 bar trailing 一致性(可直接跑的脚本,不依赖 pytest)
"""
from zipline_lab.rules.signals import (
    SIGNAL_FUNCS,
    DEFAULT_PARAMS,
    MIN_WINDOW,
    compute_signal,
    lookback_bars,
)

__all__ = [
    "SIGNAL_FUNCS",
    "DEFAULT_PARAMS",
    "MIN_WINDOW",
    "compute_signal",
    "lookback_bars",
]
