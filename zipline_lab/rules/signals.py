"""向量化技术指标信号 —— 从 dissertation 旧 componentTradingRules 迁移(迁逻辑不迁代码)。

统一契约(每规则一个函数):
    def <rule>_signal(prices: pd.DataFrame, **params) -> pd.Series
  - prices:含 open/high/low/close/volume 列的日线 DataFrame(bundle 口径 close≡adj_close);
    每个函数只取自己需要的列;
  - 返回与 prices 同索引的整型持仓信号 Series。旧规则的 score 是 -1/0/1 三态
    (buy=+1 / sell=-1 / hold=0),这里**如实沿用**,不压成 0/1(见各函数 docstring 的
    「信号语义」小节 —— 注意旧 backtester 把 -1 当「平仓到现金」而非做空,zipline 适配器
    若直接 order_target_percent(-1) 会真做空,这是迁移时的新解释,已在 rule_factory 注明)。
  - 窗口不足的前段一律 0(见 MIN_WINDOW);

纯 trailing:signal[t] 只依赖 t 及之前的行。rolling/ewm 默认即满足;
**禁止** center=True / shift(-n)。唯一例外见 momentum_rule 的 docstring:旧代码用了
shift(-1)(未来函数 bug),本迁移按其注释所述意图改成 shift(+1) 并高声标注。

MIN_WINDOW[rule_name](params) -> int:
  信号自第几根 bar(1-based,含当天)起「有效」——即前 MIN_WINDOW-1 根强制 0,
  第 MIN_WINDOW 根起才可能非零。与旧 rolling 的 warm-up(窗口不足→NaN→score 0)对齐。
  纯 EMA 规则(macd)旧代码用 min_periods=0,自 bar 1 就出信号,故 MIN_WINDOW=1。

旧文件目录:strategies/componentTradingRules/(Python2 风格 / postgres / HSI 标的,只读参考)。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 1) Bollinger Bands —— BollingerBandsStrategy.py
# ---------------------------------------------------------------------------
def bollinger_signal(prices: pd.DataFrame, *, n: int = 20, k: float = 2.0) -> pd.Series:
    """布林带均值回归(单标的)。

    旧文件:strategies/componentTradingRules/BollingerBandsStrategy.py
    旧判据(score 伪代码,逐行照搬):
        middle = adjclose.rolling(n).mean()
        std    = adjclose.rolling(n).std()          # pandas 默认 ddof=1(样本标准差)
        upper  = middle + k*std ; lower = middle - k*std
        if adjclose < lower:  score = +1   # 触下轨 → 买
        elif adjclose > upper: score = -1   # 触上轨 → 卖
        else:                  score = 0
    旧参数:parseparams 取 n(MA 长度)、k(std 倍数);defaultParam 是网格
        n=range(10,255)、k=frange(1.5,2.6,0.1)。这里取教科书常用单值 n=20,k=2.0 作默认
        (网格无单一默认值,属迁移时的取值选择)。

    信号语义:-1/0/1 状态信号(非事件);价在下轨外持续为 +1、上轨外持续为 -1。
    这是**触带即反转**判据,不是「回中轨卖」——旧文件顶部注释提过中轨,但 score 里
    并无回中轨逻辑,以 score 代码为准。

    旧代码 bug(如实标注,未在此「修正」逻辑,仅说明其无害):
      score() 首行 `if row['middle'] == np.nan: return 0` 是死代码——`x == np.nan`
      恒为 False(NaN 不等于任何值,含自身),该 NaN 守卫从不触发。但 warm-up 段
      middle/upper/lower 皆为 NaN,`adjclose < NaN` / `adjclose > NaN` 均为 False,
      故仍自然落到 return 0。行为上无差异,本函数用 MIN_WINDOW 显式挡 warm-up。
    """
    n = int(n)
    k = float(k)
    close = prices["close"].astype(float)
    sig = pd.Series(0, index=prices.index, dtype=int)
    if len(close) < n:
        return sig
    middle = close.rolling(n).mean()
    std = close.rolling(n).std()  # ddof=1,同旧 .std()
    upper = middle + k * std
    lower = middle - k * std
    sig = sig.mask(close < lower, 1).mask(close > upper, -1)
    # rolling(n) 前 n-1 根为 NaN → 比较为 False → 已是 0;此处再显式保证
    sig.iloc[: n - 1] = 0
    return sig.astype(int)


# ---------------------------------------------------------------------------
# 2) RSI —— RelativeStrengthIndex.py
# ---------------------------------------------------------------------------
def rsi_signal(prices: pd.DataFrame, *, n: int = 14, ob: int = 70, os: int = 30) -> pd.Series:
    """相对强弱指数超买超卖(**SMA 平滑,非 Wilder**)。

    旧文件:strategies/componentTradingRules/RelativeStrengthIndex.py
    旧 RSI 计算(逐行照搬,注意平滑口径):
        对每个 rolling(n) 窗口(n 个 close):
          calcUp   = Σ(上涨日的涨幅) / n      # 窗口内 i=1..n-1 共 n-1 个差分
          calcDown = Σ(下跌日的跌幅) / n
        rsi = 100 - 100/(1 + calcUp/calcDown)   # numpy 除法:x/0→inf, 0/0→nan
      —— 这是**简单平均(SMA)平滑**,不是 Wilder 平滑;且分子分母同除 n,ratio 上
      /n 相消 ⇒ 等价 RS = ΣUp/ΣDown。用 n 个 close 的窗口 ⇒ 只有 n-1 个价格变化
      (标准 n 期 RSI 用 n 个变化),旧口径这里差一个变化,本迁移照旧(见下方实现)。
    旧参数:n(回看)、ob(超买阈)、os(超卖阈);defaultParam 网格
        n=range(10,31)、ob=range(70,96)、os=range(10,32)。取教科书单值 n=14,ob=70,os=30。

    旧判据(score 伪代码,b=ob, s=os):
        if rsi > s:  score = +1     # 注释写「涨回超卖线上方 → 买」
        elif rsi < b: score = -1    # 注释写「跌回超买线下方 → 卖」
        else:        score = 0

    ★旧代码 bug(如实标注,本函数**照旧复现不修**):
      判据无「穿越」检测,且阈值方向反了。因 os<ob(如 30<70),`rsi > os` 几乎恒真
      且被先判 ⇒ 实际退化为:rsi>os → +1;否则(rsi<=os,此时 rsi<ob 必真)→ -1。
      即 ob 阈值几乎失效,信号约等于「rsi>30 买 / rsi<=30 卖」。这与注释的本意
      (超卖买/超买卖)相悖,是明显逻辑 bug,但旧口径以旧代码行为为准,故如实保留。

    信号语义:-1/0/1;因上述 bug,几乎全程在 +1/-1 之间(极少 0)。
    """
    n = int(n)
    ob = int(ob)
    os_ = int(os)
    close = prices["close"].astype(float)
    sig = pd.Series(0, index=prices.index, dtype=int)
    if len(close) < n:
        return sig
    diff = close.diff()
    up = diff.clip(lower=0.0)          # 上涨日涨幅,其余 0
    down = (-diff).clip(lower=0.0)     # 下跌日跌幅(正值),其余 0
    # 旧 calcUp/calcDown:窗口 n 个 close 内 n-1 个差分求和,再 /n
    ave_u = up.rolling(n - 1).sum() / n
    ave_d = down.rolling(n - 1).sum() / n
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = ave_u.to_numpy() / ave_d.to_numpy()     # x/0→inf, 0/0→nan(同旧 numpy 除法)
        rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = pd.Series(rsi, index=prices.index)
    # 旧 score:rsi>os → +1(先判);elif rsi<ob → -1;NaN → 0
    s = np.where(rsi.to_numpy() > os_, 1, np.where(rsi.to_numpy() < ob, -1, 0))
    s = np.where(np.isnan(rsi.to_numpy()), 0, s)
    sig = pd.Series(s, index=prices.index, dtype=int)
    sig.iloc[: n - 1] = 0
    return sig.astype(int)


# ---------------------------------------------------------------------------
# 3) MACD (EMA 交叉) —— MovingAveConvergeDiver.py
# ---------------------------------------------------------------------------
def macd_signal(prices: pd.DataFrame, *, nl: int = 26, ns: int = 12) -> pd.Series:
    """双 EMA 交叉(短 EMA 上穿/下穿长 EMA 的持仓状态)。

    旧文件:strategies/componentTradingRules/MovingAveConvergeDiver.py
    旧判据(伪代码):
        smal = EMA(adjclose, span=nl)   # 长周期
        smas = EMA(adjclose, span=ns)   # 短周期,ns<nl
        buy  = smas > smal  →  score=+1
        sell = smas < smal  →  score=-1
        (smas==smal 或 NaN → 0)
    EMA 口径:旧代码 `.ewm(span=?, min_periods=0, adjust=False, ignore_na=False)`,
    即递归 EMA、adjust=False、无 warm-up 门(min_periods=0)⇒ 自 bar 1 就出信号。
    旧参数:nl(长)、ns(短);defaultParam 网格 nl/ns 为离散表。取教科书 MACD 常用
        span:nl=26、ns=12(注:该二值不在旧网格列表里,是迁移时选的规范默认)。

    ★旧代码 bug(如实标注,本函数按显然意图迁移 = 补 .mean()):
      旧 run() 写 `pd.Series(stockData['adjclose'].ewm(span=l, ...), index=...)` ——
      **漏调 .mean()**!ewm(...) 返回的是 ExponentialMovingWindow 对象而非序列,
      直接塞进 pd.Series 无法算出 EMA(实跑会报错/得垃圾值)。同仓 MovingMomentum.py
      对同样的 ewm 是有 .mean() 的,且本文件顶部注释明确写 E.Avg 递归 EMA 公式,
      故意图无歧义:EMA=ewm(span).mean()。本迁移补上 .mean(),并在此高声标注旧文件
      此处实际跑不通(不是「悄悄修正逻辑」,而是让漏写的算子可运行)。

    信号语义:-1/0/1 状态(EMA 上/下关系),非交叉事件。EMA min_periods=0 ⇒ 无强制
    warm-up(MIN_WINDOW=1);bar 0 时两 EMA 相等 → 0。
    """
    nl = int(nl)
    ns = int(ns)
    close = prices["close"].astype(float)
    smal = close.ewm(span=nl, adjust=False, min_periods=0, ignore_na=False).mean()
    smas = close.ewm(span=ns, adjust=False, min_periods=0, ignore_na=False).mean()
    sig = pd.Series(0, index=prices.index, dtype=int)
    sig = sig.mask(smas > smal, 1).mask(smas < smal, -1)
    return sig.astype(int)


# ---------------------------------------------------------------------------
# 4) Stochastic Oscillator —— StochasticOscillator.py
# ---------------------------------------------------------------------------
def stochastic_signal(
    prices: pd.DataFrame, *, n: int = 14, m: int = 3, ob: int = 80, os: int = 20
) -> pd.Series:
    """随机指标 %K/%D 交叉(结合超买超卖区)。

    旧文件:strategies/componentTradingRules/StochasticOscillator.py
    旧判据(伪代码):
        lowest  = low.rolling(n).min()
        highest = high.rolling(n).max()
        K = 100*(close - lowest)/(highest - lowest)     # %K,记作 sto
        D = K.rolling(m).mean()                          # %D,记作 _D
        buy  : (D < os) and (K > D)  →  +1   # %D 在超卖区下方 且 %K 上穿在 %D 之上
        sell : (D > ob) and (K < D)  →  -1   # %D 在超买区上方 且 %K 在 %D 之下
        (K 或 D 为 NaN → 0)
    旧参数:n(回看)、m(平滑)、ob(超买)、os(超卖);defaultParam 网格
        n=range(5,15)+range(15,200,5)、m=range(3,12)、ob=range(70,96)、os=range(10,32)。
        取教科书单值 n=14,m=3,ob=80,os=20。

    注:旧代码用 close(非 adjclose)算 %K,high/low 用原始列;bundle 已 close≡adj_close
    且 OHLC 同乘复权因子,故口径一致。

    信号语义:-1/0/1 状态。判据是「区间 + 同向」的即时状态,非严格穿越事件
    (未要求 %K 恰好在本 bar 穿过 %D)。
    """
    n = int(n)
    m = int(m)
    ob = int(ob)
    os_ = int(os)
    close = prices["close"].astype(float)
    low = prices["low"].astype(float)
    high = prices["high"].astype(float)
    sig = pd.Series(0, index=prices.index, dtype=int)
    if len(close) < n + m - 1:
        return sig
    lowest = low.rolling(n).min()
    highest = high.rolling(n).max()
    with np.errstate(divide="ignore", invalid="ignore"):
        k = 100.0 * (close - lowest) / (highest - lowest)   # 高=低时 → inf/nan(同旧)
    d = k.rolling(m).mean()
    buy = (d < os_) & (k > d)
    sell = (d > ob) & (k < d)
    sig = sig.mask(buy, 1).mask(sell, -1)
    # k/d 的 NaN 段:比较为 False → 已 0;再显式挡 warm-up
    sig.iloc[: n + m - 1] = 0
    return sig.astype(int)


# ---------------------------------------------------------------------------
# 5) Moving Momentum —— MovingMomentum.py(stockcharts「Moving Momentum」系统)
# ---------------------------------------------------------------------------
def momentum_rule_signal(
    prices: pd.DataFrame,
    *,
    hnl: int = 26,
    hns: int = 12,
    htime: int = 9,
    snl: int = 40,
    sns: int = 30,
    sto_n: int = 3,
    sto_m: int = 7,
    sto_ob: int = 75,
    sto_os: int = 25,
) -> pd.Series:
    """Moving Momentum 三重确认(MACD 柱翻向 + 双 SMA 趋势 + 随机指标)。

    旧文件:strategies/componentTradingRules/MovingMomentum.py
    (对应 stockcharts.com moving_momentum 策略。与 zipline_lab/momentum_ts.py 的
     12-1 月度横截面动量**完全无关**,勿混。)

    旧计算(逐行照搬):
        smal = SMA(adjclose, snl) ; smas = SMA(adjclose, sns)        # 趋势:长/短 SMA
        emal = EMA(adjclose, span=hnl, adjust=False)                  # MACD 柱用
        emas = EMA(adjclose, span=hns, adjust=False)
        macd = emal - emas          # ★注意:长-短(与标准 MACD=快-慢 反号),照旧
        signalLine = macd.ewm(span=htime).mean()   # ★此处 adjust=True(旧代码未写 adjust=False)
        diverse    = macd - signalLine              # MACD 柱状(histogram)
        prediverse = diverse.shift(-1)              # ★见下「未来函数 bug」
        K = 100*(close - low.rolling(sto_n).min())/(high.rolling(sto_n).max()-low.rolling(sto_n).min())
        D = K.rolling(sto_m).mean()   # 旧变量名 sto_k,实为 %D 平滑线
        buy  : prediverse<0 and diverse>0 and smas>smal and K>D and D<sto_os  → +1
        sell : prediverse>0 and diverse<0 and smas<smal and K<D and D>sto_ob  → -1
    旧参数(parseparams 名):hnl,hns,htime,snl,sns,sto_n,sto_m,sto_ob,sto_os。
        defaultParam 是大网格,但文件内注释掉的「单值」即规范默认:hns=12,hnl=26,
        htime=9,snl=40,sns=30,sto_n=3,sto_m=7,sto_ob=75,sto_os=25 —— 照搬为函数默认。

    ★★旧代码严重 bug(未来函数)—— 本迁移**未照抄,改为 trailing-safe 并高声标注**:
      旧 `prediverse = diverse.shift(-1)` 取的是**下一交易日(t+1)**的柱值,是明确的
      未来函数(lookahead)。而文件顶注写「buy signal: when the value from negative to
      positive」(柱由负转正),该意图对应「昨日<0 且 今日>0」= diverse.shift(+1)<0 且
      diverse>0。故旧 shift(-1) 既是未来函数、方向也与注释相反(双重错)。
      本框架硬规则禁止未来函数(禁 shift(-n)),且此为确凿 bug 而非语义歧义,
      因此按其**书面意图**迁为 prediverse = diverse.shift(+1)(昨日柱)。这是全批迁移中
      唯一一处偏离旧代码字面行为的地方,特此显式声明,便于人核。

    信号语义:-1/0/1;三条件同时满足才触发,故信号稀疏(多数为 0)。
    """
    hnl = int(hnl); hns = int(hns); htime = int(htime)
    snl = int(snl); sns = int(sns)
    sto_n = int(sto_n); sto_m = int(sto_m)
    sto_ob = int(sto_ob); sto_os = int(sto_os)

    close = prices["close"].astype(float)
    low = prices["low"].astype(float)
    high = prices["high"].astype(float)

    sig = pd.Series(0, index=prices.index, dtype=int)
    min_win = max(snl, sns, sto_n + sto_m - 1)
    if len(close) < min_win:
        return sig

    smal = close.rolling(snl).mean()
    smas = close.rolling(sns).mean()
    emal = close.ewm(span=hnl, adjust=False, min_periods=0, ignore_na=False).mean()
    emas = close.ewm(span=hns, adjust=False, min_periods=0, ignore_na=False).mean()
    macd = emal - emas
    signal_line = macd.ewm(span=htime).mean()  # adjust 默认 True,同旧
    diverse = macd - signal_line
    prediverse = diverse.shift(1)  # ★ 旧为 shift(-1)(未来函数 bug),按意图改 +1,见 docstring

    lowest = low.rolling(sto_n).min()
    highest = high.rolling(sto_n).max()
    with np.errstate(divide="ignore", invalid="ignore"):
        k = 100.0 * (close - lowest) / (highest - lowest)
    d = k.rolling(sto_m).mean()

    buy = (prediverse < 0) & (diverse > 0) & (smas > smal) & (k > d) & (d < sto_os)
    sell = (prediverse > 0) & (diverse < 0) & (smas < smal) & (k < d) & (d > sto_ob)
    # NaN 参与的比较结果为 False,自然落到 0(等价旧 score 的 isnan 守卫)
    sig = sig.mask(buy, 1).mask(sell, -1)
    sig.iloc[:min_win] = 0
    return sig.astype(int)


# ---------------------------------------------------------------------------
# 注册表 + MIN_WINDOW + 供 rule_factory 用的取数窗口长度
# ---------------------------------------------------------------------------
SIGNAL_FUNCS = {
    "bollinger": bollinger_signal,
    "rsi": rsi_signal,
    "macd": macd_signal,
    "stochastic": stochastic_signal,
    "momentum_rule": momentum_rule_signal,
}

DEFAULT_PARAMS = {
    "bollinger": dict(n=20, k=2.0),
    "rsi": dict(n=14, ob=70, os=30),
    "macd": dict(nl=26, ns=12),
    "stochastic": dict(n=14, m=3, ob=80, os=20),
    "momentum_rule": dict(
        hnl=26, hns=12, htime=9, snl=40, sns=30,
        sto_n=3, sto_m=7, sto_ob=75, sto_os=25,
    ),
}

# 每规则:给定 params 返回「信号自第几根 bar(1-based)起有效」= 前 MIN_WINDOW-1 根强制 0。
MIN_WINDOW = {
    "bollinger": lambda p: int(p.get("n", 20)),
    "rsi": lambda p: int(p.get("n", 14)),
    # 纯 EMA(min_periods=0)自 bar1 出信号,旧无 warm-up 门
    "macd": lambda p: 1,
    "stochastic": lambda p: int(p.get("n", 14)) + int(p.get("m", 3)) - 1,
    "momentum_rule": lambda p: max(
        int(p.get("snl", 40)),
        int(p.get("sns", 30)),
        int(p.get("sto_n", 3)) + int(p.get("sto_m", 7)) - 1,
    ),
}

# EMA 类规则的 last 值依赖全历史(递归),trailing 窗口须给足缓冲让 seed 衰减到不翻整数信号;
# 有限窗规则(rolling)last 值只依赖窗口内 MIN_WINDOW 根,缓冲无关正确性(给点余量即可)。
_EMA_BUFFER = 300   # macd / momentum_rule 的 EMA seed 衰减缓冲
_FINITE_BUFFER = 5  # bollinger / rsi / stochastic


def lookback_bars(rule_name: str, params: dict) -> int:
    """rule_factory / test_parity 每 bar 取数(以及逐 bar 模拟)用的 trailing 窗口长度
    = MIN_WINDOW(params) + 缓冲。EMA 类给大缓冲。"""
    mw = MIN_WINDOW[rule_name](params)
    buf = _EMA_BUFFER if rule_name in ("macd", "momentum_rule") else _FINITE_BUFFER
    return int(mw + buf)


def compute_signal(rule_name: str, prices: pd.DataFrame, params: dict) -> pd.Series:
    """按 rule_name 调对应向量化函数(params 缺省用 DEFAULT_PARAMS 补全)。"""
    merged = dict(DEFAULT_PARAMS[rule_name])
    merged.update(params or {})
    return SIGNAL_FUNCS[rule_name](prices, **merged)
