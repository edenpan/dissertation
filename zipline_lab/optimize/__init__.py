"""参数寻优子包:现代 PSO + 同预算随机搜索(供 sma8 等多维规则调参 / 过拟合对照用)。"""
from zipline_lab.optimize.pso import (
    PSOResult,
    SearchResult,
    pso_optimize,
    random_search,
)

__all__ = ["PSOResult", "SearchResult", "pso_optimize", "random_search"]
