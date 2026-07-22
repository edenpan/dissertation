"""现代 gbest 粒子群优化(PSO)—— numpy 向量化,供 sma8 等高维规则做样本内调参。

为什么用 PSO(而非网格):sma8 有 8 个整数窗口 t1..t8 ∈ [2,200],空间 ~200^8 ≈ 2.6e18,
网格穷举完全不可行——这正是旧论文(strategies/pso_sma.py)用 PSO 的理由。PSO 用一小群
「粒子」在空间里协同搜索,每个粒子记住自己历史最优(pbest)并被全局最优(gbest)吸引,
用固定的评估预算(pop_size × iters)逼近好参数。

════════════════════════════════════════════════════════════════════════════
与旧论文超参的差异及理由(旧 = strategies/componentTradingRules/pso/ + pso_sma.py)
════════════════════════════════════════════════════════════════════════════
旧超参(pso_sma.py):popSize=5、c1=c2=2、w=1.3(常量)、iterMax=10000、VMax=80、
  且**无惯性权重衰减 / 无收缩因子**。这套在现代视角有两处不稳:
    (a) w=1.3 且 c1=c2=2 时,PSO 的更新不满足收敛条件(Clerc-Kennedy 稳定域约为
        w<1 且 w>0.5*(c1+c2)-1),速度易发散、靠 VMax=80 硬夹——搜索退化为大步乱撞;
    (b) popSize=5 对 8 维空间太小,群体多样性不足;靠 iterMax=10000 弥补 ⇒ 5×10000
        =5e4 次评估,大量浪费在发散轨迹上。
本模块默认用**现代标准常量 PSO**(Clerc & Kennedy 2002 的 constriction 等价参数):
    pop_size=30、iters=200、w=0.729、c1=c2=1.49445。
  这组 (w, c1, c2) 落在稳定域内(0.729 < 1 且 > 0.5*(1.49445+1.49445)-1 = 0.494),
  速度自然收敛、无需 VMax 硬夹;pop=30 给足多样性;30×200=6000 次评估即预算,远少于旧
  5e4 却更稳。旧超参保留为可选 preset="legacy"(见 LEGACY_PRESET),便于与旧论文对拍。

整数参数:粒子位置是连续 float(PSO 数学需要),评估/返回前对 int_mask 指定的维度做
  **round → clip 到 bounds**,保证喂给 sma8 的窗口是合法整数(rule_factory / signals 同口径)。

fitness 契约:本模块只认「objective(param_vector: np.ndarray) -> float,越大越好」的回调,
  与 walkforward.fitness(returns)->float 解耦——调用方负责把 param 向量→signal→等效收益→
  fitness 串起来注入(见 optimize/experiment_pso_overfit.py)。PSO 只管在 bounds 内最大化它。

早停:连续 `patience` 轮 gbest 无实质改进(< tol)即停,返回时标注实际用掉的迭代/评估数。
随机种子:seed 可传,PSO 全过程(初始化 + 每轮 r1/r2)用同一个 np.random.Generator,可复现。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import numpy as np

# 旧论文超参(strategies/pso_sma.py)——保留为可选 preset,便于与旧命题对拍。
LEGACY_PRESET = dict(pop_size=5, iters=10000, w=1.3, c1=2.0, c2=2.0, vmax=80.0)
# 现代标准常量 PSO(Clerc & Kennedy 2002 收缩因子的等价惯性权重形式)。
MODERN_PRESET = dict(pop_size=30, iters=200, w=0.729, c1=1.49445, c2=1.49445, vmax=None)


@dataclass
class PSOResult:
    best_params: np.ndarray          # 全局最优参数(已按 int_mask 投影为整数)
    best_fitness: float              # 对应 objective 值(越大越好)
    n_evals: int                     # 实际 objective 评估次数
    iters_run: int                   # 实际跑的迭代轮数(早停可能 < iters)
    history: list[float]             # 每轮结束时的 gbest_fitness(收敛曲线)
    stopped_early: bool = False


@dataclass
class SearchResult:
    best_params: np.ndarray
    best_fitness: float
    n_evals: int
    history: list[float] = field(default_factory=list)  # 累计 best(评估序上的 running max)


def _project(pos: np.ndarray, lo: np.ndarray, hi: np.ndarray, int_mask: np.ndarray) -> np.ndarray:
    """把连续位置投影成合法参数:int 维 round,再整体 clip 到 [lo, hi]。"""
    out = pos.copy()
    if int_mask.any():
        out[..., int_mask] = np.round(out[..., int_mask])
    return np.clip(out, lo, hi)


def pso_optimize(
    objective: Callable[[np.ndarray], float],
    bounds: Sequence[tuple[float, float]],
    *,
    preset: str = "modern",
    pop_size: Optional[int] = None,
    iters: Optional[int] = None,
    w: Optional[float] = None,
    c1: Optional[float] = None,
    c2: Optional[float] = None,
    vmax: Optional[float] = None,
    int_mask: Optional[Sequence[bool]] = None,
    seed: Optional[int] = None,
    patience: int = 30,
    tol: float = 1e-9,
    verbose: bool = False,
) -> PSOResult:
    """gbest PSO 最大化 objective。

    Args:
      objective: param_vector(1D, 已投影为合法参数) -> float,越大越好。
      bounds:    [(lo, hi), ...] 每维取值域(含端点)。
      preset:    "modern"(默认现代常量 PSO)/ "legacy"(旧论文超参 pop=5,c=2,w=1.3,iter=1e4)。
                 显式传 pop_size/iters/w/c1/c2/vmax 会覆盖 preset 对应项。
      int_mask:  逐维 bool,True 表示该维取整(round+clip);None = 全整数(sma8 场景)。
      seed:      随机种子(可复现)。
      patience:  连续多少轮 gbest 无改进(< tol)即早停。
      vmax:      速度上限(每维绝对值);None = 不夹(现代默认,靠 w<1 自收敛)。
    """
    base = dict(LEGACY_PRESET if preset == "legacy" else MODERN_PRESET)
    if pop_size is not None: base["pop_size"] = pop_size
    if iters is not None: base["iters"] = iters
    if w is not None: base["w"] = w
    if c1 is not None: base["c1"] = c1
    if c2 is not None: base["c2"] = c2
    if vmax is not None: base["vmax"] = vmax
    pop_size = int(base["pop_size"]); iters = int(base["iters"])
    w = float(base["w"]); c1 = float(base["c1"]); c2 = float(base["c2"])
    vmax = base["vmax"]

    bounds = np.asarray(bounds, dtype=float)
    dim = bounds.shape[0]
    lo, hi = bounds[:, 0], bounds[:, 1]
    span = hi - lo
    if int_mask is None:
        int_mask = np.ones(dim, dtype=bool)
    else:
        int_mask = np.asarray(int_mask, dtype=bool)

    rng = np.random.default_rng(seed)

    # 初始化:位置均匀撒在 bounds 内,速度撒在 ±span 内(对称、有界)。
    pos = lo + rng.random((pop_size, dim)) * span
    vel = (rng.random((pop_size, dim)) * 2.0 - 1.0) * span

    n_evals = 0

    def _eval_pop(p: np.ndarray) -> np.ndarray:
        nonlocal n_evals
        proj = _project(p, lo, hi, int_mask)
        vals = np.empty(pop_size, dtype=float)
        for i in range(pop_size):
            vals[i] = float(objective(proj[i]))
        n_evals += pop_size
        return vals

    fit = _eval_pop(pos)
    pbest_pos = pos.copy()
    pbest_fit = fit.copy()
    g_idx = int(np.argmax(pbest_fit))
    gbest_pos = pbest_pos[g_idx].copy()
    gbest_fit = float(pbest_fit[g_idx])

    history: list[float] = [gbest_fit]
    stale = 0
    iters_run = 0
    stopped_early = False

    for it in range(iters):
        iters_run = it + 1
        r1 = rng.random((pop_size, dim))
        r2 = rng.random((pop_size, dim))
        vel = w * vel + c1 * r1 * (pbest_pos - pos) + c2 * r2 * (gbest_pos - pos)
        if vmax is not None:
            vel = np.clip(vel, -float(vmax), float(vmax))
        pos = pos + vel
        # 出界的位置夹回 bounds,并把该维速度归零(避免贴墙反复冲出)
        below = pos < lo
        above = pos > hi
        pos = np.clip(pos, lo, hi)
        vel[below | above] = 0.0

        fit = _eval_pop(pos)
        improved = fit > pbest_fit
        pbest_pos[improved] = pos[improved]
        pbest_fit[improved] = fit[improved]

        g_idx = int(np.argmax(pbest_fit))
        if pbest_fit[g_idx] > gbest_fit + tol:
            gbest_fit = float(pbest_fit[g_idx])
            gbest_pos = pbest_pos[g_idx].copy()
            stale = 0
        else:
            stale += 1
        history.append(gbest_fit)

        if verbose and (it % max(1, iters // 10) == 0):
            print(f"  [pso] iter {it:4d}  gbest={gbest_fit:.6f}  evals={n_evals}")

        if stale >= patience:
            stopped_early = True
            break

    best_params = _project(gbest_pos, lo, hi, int_mask)
    return PSOResult(
        best_params=best_params,
        best_fitness=gbest_fit,
        n_evals=n_evals,
        iters_run=iters_run,
        history=history,
        stopped_early=stopped_early,
    )


def random_search(
    objective: Callable[[np.ndarray], float],
    bounds: Sequence[tuple[float, float]],
    n_evals: int,
    *,
    int_mask: Optional[Sequence[bool]] = None,
    seed: Optional[int] = None,
) -> SearchResult:
    """同预算随机搜索(公平对照 PSO):在 bounds 内均匀采 n_evals 个点,取最优。

    与 PSO 唯一的差别是「怎么选下一个点」——随机搜索无记忆、无群体协同,是「PSO 的搜索
    策略是否真带来 OOS 优势」这一命题的对照臂。评估预算与 PSO 严格相等(pop_size×iters)。
    """
    bounds = np.asarray(bounds, dtype=float)
    dim = bounds.shape[0]
    lo, hi = bounds[:, 0], bounds[:, 1]
    span = hi - lo
    if int_mask is None:
        int_mask = np.ones(dim, dtype=bool)
    else:
        int_mask = np.asarray(int_mask, dtype=bool)

    rng = np.random.default_rng(seed)
    best_params = None
    best_fit = -np.inf
    history: list[float] = []
    for _ in range(int(n_evals)):
        cand = _project(lo + rng.random(dim) * span, lo, hi, int_mask)
        val = float(objective(cand))
        if val > best_fit:
            best_fit = val
            best_params = cand
        history.append(best_fit)
    return SearchResult(
        best_params=best_params,
        best_fitness=best_fit,
        n_evals=int(n_evals),
        history=history,
    )
