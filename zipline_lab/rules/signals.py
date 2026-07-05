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
# 6) 8-SMA 状态机 —— smaTrading.py / pso_sma.py(旧 PSO 的适应度标的,PSO 对照主角)
# ---------------------------------------------------------------------------
def sma8_signal(
    prices: pd.DataFrame,
    *,
    t1: int = 5, t2: int = 120, t3: int = 60, t4: int = 200,
    t5: int = 5, t6: int = 120, t7: int = 60, t8: int = 200,
) -> pd.Series:
    """8 条 SMA 的买/卖/持有状态机(**含持仓记忆,path-dependent**)。

    旧文件:strategies/componentTradingRules/smaTrading.py、strategies/smaTrading.py、
            strategies/pso_sma.py(三处互参;PSO 的适应度标的)。
    旧交易逻辑(文件顶部注释逐字):
        signal = buy,   if (SMA_t1 > SMA_t2) and (SMA_t3 > SMA_t4)
               = sell,  if (SMA_t5 < SMA_t6) and (SMA_t7 < SMA_t8)
               = hold,  otherwise（保持上一状态）
    旧 smaCross 的状态机(逐行照搬语义):
        state=False(持币/flat) / True(持股/long);从 flat 起步。
        for row in stockData[200:]:                 # 旧硬编码从第 200 根起(默认最长窗=200)
            if buy_trigger  and state==False: state=True    # 只在 flat 时买入
            if sell_trigger and state==True:  state=False   # 只在 long 时卖出(在 buy 块之后判)
      —— 旧引擎只有两态(现金/满仓),**无做空**。故本规则信号取值 {0,1}(不是 -1/0/1);
         这与 rule_factory 的 long/flat 下单口径天然一致(position=signal.clip(lower=0) 即恒等)。
    旧参数:8 个 SMA 窗口 t1..t8;pso_sma.py 里 PSO 在 [1,200] 整数域搜这 8 维。默认取旧
        `smaCross([5,120,60,200,5,120,60,200])` = (t1..t4=5,120,60,200 / t5..t8=5,120,60,200)。

    ★★path 依赖 —— 迁移要害(状态机无法用固定 trailing 窗口精确重放):
      状态在一次 buy_trigger 后会**无限保持 long**,直到某天 sell_trigger 才翻 flat(反之亦然)。
      故第 t 日的仓位状态依赖自 warm-up 起的**完整触发路径**,而非任何固定长度的 trailing 窗口:
      若某段 400 天内无翻转触发,固定 300 根窗口就会截断掉更早的那次进场、错判状态。
      因此 sma8 的 lookback 必须取「全段」(见 lookback_bars 的 _STATEFUL 特判 + test_parity),
      即 rule_factory 每 bar 用 min(bar_count, 全段)= 自模拟起点至今的**扩张窗口**重算,
      逐 bar 重放才能与全区间向量化逐日一致(有限窗规则不需要这样)。

    向量化状态机(等价旧逐 bar 循环,买卖触发序列 → set + ffill):
        buy_trigger  = (SMA_t1>SMA_t2) & (SMA_t3>SMA_t4)
        sell_trigger = (SMA_t5<SMA_t6) & (SMA_t7<SMA_t8)
        state = NaN 序列;state[buy_trigger]=1;**再** state[sell_trigger]=0(sell 后置);
        state = state.ffill().fillna(0)
      「sell 后置覆盖 buy」精确复现旧代码同 bar 双触发的收口:旧代码 buy 块先执行(flat→long)、
      sell 块后执行(long→flat),故一根 bar 上 buy 与 sell **同时**成立时,无论前态如何,收盘恒为
      flat(0)。set+ffill 里让 sell 的 0 覆盖 buy 的 1,结果同为 0,逐 bar 等价(单触发/无触发
      场景 set+ffill 与「只在反态动作」也已等价:单 buy → 置 1 恰是两旧分支的收口,单 sell →
      置 0 同理,无触发 → NaN→ffill=保持前态)。warm-up(SMA 未满)比较为 False → 不置态 →
      ffill 保持 NaN → fillna(0),即前 max(t..)-1 根强制 flat。

    与旧代码字面的两处已知偏离(如实标注,均不改变命题):
      (a) 旧 smaCross 硬编码从第 200 根起迭代(因默认最长窗恰为 200);本函数按参数取
          max(t1..t8)-1 作 warm-up——参数化的正确推广(PSO 搜 [2,200] 时窗口常 <200,
          硬编 200 会平白砍掉可交易段)。
      (b) 旧 SMA 列带 `.fillna(method='backfill')`(用未来值填 warm-up 的 NaN,潜在
          lookahead)——但旧循环从第 200 根起,被 backfill 的段永远读不到,实际无害;
          本迁移直接丢弃 backfill(warm-up 强制 flat),行为等价且根绝 lookahead。
    """
    ts = [int(t1), int(t2), int(t3), int(t4), int(t5), int(t6), int(t7), int(t8)]
    close = prices["close"].astype(float)
    sig = pd.Series(0, index=prices.index, dtype=int)
    max_win = max(ts)
    if len(close) < max_win:
        return sig  # 全段窗口都不足 → 恒 flat
    smas = [close.rolling(w).mean() for w in ts]
    buy = (smas[0] > smas[1]) & (smas[2] > smas[3])       # SMA_t1>t2 且 SMA_t3>t4
    sell = (smas[4] < smas[5]) & (smas[6] < smas[7])      # SMA_t5<t6 且 SMA_t7<t8
    state = pd.Series(np.nan, index=prices.index, dtype=float)
    state[buy] = 1.0
    state[sell] = 0.0            # ★ sell 后置:同 bar 双触发时覆盖 buy → 收盘 flat(复现旧收口)
    state = state.ffill().fillna(0.0)
    sig = state.astype(int)
    sig.iloc[: max_win - 1] = 0  # SMA 未满段强制 flat(旧 warm-up)
    return sig.astype(int)


# ===========================================================================
# 第三批(最后一批)迁移:macd_hist / obv / range_breakout / ma_cross / weighted
# ===========================================================================

# ---------------------------------------------------------------------------
# 7) MACD 柱状图转向 —— MacdHistogram.py
# ---------------------------------------------------------------------------
def macd_hist_signal(prices: pd.DataFrame, *, nl: int = 26, ns: int = 12, t: int = 9) -> pd.Series:
    """MACD 柱状图(histogram)符号翻转判据 —— **与已迁 `macd` 是两个不同规则**。

    旧文件:strategies/componentTradingRules/MacdHistogram.py
    (对应 stockcharts.com moving_momentum 的 MACD-histogram 分量;与 MovingMomentum.py
     的 diverse 计算同源,但 MacdHistogram 只用「柱翻向」一条,不叠加趋势/随机确认。)

    与已迁 `macd`(MovingAveConvergeDiver.py)的区别 —— 务必分清:
      - `macd`      = 双 EMA **相对位置**的状态:smas>smal → +1(短 EMA 在长 EMA 上方)。
                       是「快慢线谁在上」的持续状态。
      - `macd_hist` = MACD 线与其**信号线(signal line)之差**(即柱状图 diverse)的**符号翻转事件**:
                       柱由负转正 → +1、由正转负 → -1。是「柱状图过零」的动量加速判据。
      用户旧论文里「MACD 不错」的记忆很可能来自本规则(柱翻向),而非单纯的 EMA 交叉。

    旧计算(calculate() 逐行照搬):
        smal = EMA(adjclose, span=nl, min_periods=0, adjust=False, ignore_na=False)   # 长
        smas = EMA(adjclose, span=ns, min_periods=0, adjust=False, ignore_na=False)   # 短(ns<nl)
        macd = smal - smas          # ★ 长-短(与标准 MACD=快-慢 反号!),照旧不改
        signalLine = macd.ewm(span=t).mean()    # ★ adjust 默认 True(旧未写 adjust=False)
        diverse    = macd - signalLine           # MACD 柱状图(histogram)
        prediverse = diverse.shift(-1)           # ★ 见下「未来函数 bug」
        # 旧 calculate() 还算了 buy=smas>smal / sell=smas<smal,但 score() **完全没用**它们
        # (score 只读 prediverse/diverse),故本迁移忽略这两列死代码。
    旧 score(row):
        if isnan(prediverse) or isnan(diverse): return 0
        if prediverse < 0 and diverse > 0: return +1     # 柱由负→正(注释:from negative to positive)
        if prediverse > 0 and diverse < 0: return -1     # 柱由正→负
        return 0
    旧参数:nl(长)、ns(短)、t(MACD 的 t 日 EMA=信号线跨度)。defaultParam 活动网格
        ns=range(8,21)、nl=range(24,40,2)、t=range(8,15);注释掉的单值有两组
        (ns=12/nl=26/t=9 与 ns=8/nl=32/t=8)。取教科书 + 第一组单值 nl=26,ns=12,t=9 作默认
        (网格无唯一默认,属迁移取值选择)。

    ★旧代码 sign-convention 量:macd=长-短 = -(标准 MACD)⇒ 柱=-（标准柱）⇒ 本规则的
      「柱负→正买入」实际对应**标准 MACD 柱由正→负**(教科书里偏空信号)。即本规则买卖方向
      与标准 MACD-柱解读相反。此为旧代码 sign 约定使然(与 momentum_rule 同源同 quirk),
      照旧保留、如实标注,不做「修正」。

    ★★旧代码严重 bug(未来函数)—— 本迁移**未照抄,改 trailing-safe 并高声标注**:
      旧 `prediverse = diverse.shift(-1)` 取**下一交易日(t+1)**的柱值 = 明确未来函数(lookahead),
      且方向也与文件注释「柱由负转正」相反(注释意图 = 昨日<0 且 今日>0 = shift(+1))。
      与 momentum_rule 里同一处 bug 一模一样(双重错:未来函数 + 方向反)。本框架硬规则禁未来
      函数,且此为确凿 bug(非语义歧义),故按其书面意图迁为 prediverse = diverse.shift(+1)(昨日柱)。
      这是本批唯一偏离旧代码字面行为处(与第一批 momentum_rule 同性质),特此显式声明供人核。

    信号语义:-1/0/1 事件型(柱过零);多数 bar 为 0(仅在符号翻转日触发)。
    EMA min_periods=0 ⇒ 无强制 warm-up(MIN_WINDOW=1);bar0 因 prediverse=NaN 自然为 0。
    EMA 递归 ⇒ last 值依赖全历史,trailing 取数须给足 _EMA_BUFFER(见 lookback_bars)。
    """
    nl = int(nl); ns = int(ns); t = int(t)
    close = prices["close"].astype(float)
    smal = close.ewm(span=nl, adjust=False, min_periods=0, ignore_na=False).mean()  # 长
    smas = close.ewm(span=ns, adjust=False, min_periods=0, ignore_na=False).mean()  # 短
    macd = smal - smas                       # ★ 长-短,照旧(反号于标准 MACD)
    signal_line = macd.ewm(span=t).mean()    # adjust 默认 True,同旧
    diverse = macd - signal_line
    prediverse = diverse.shift(1)            # ★ 旧为 shift(-1)(未来函数 bug),按意图改 +1
    sig = pd.Series(0, index=prices.index, dtype=int)
    buy = (prediverse < 0) & (diverse > 0)
    sell = (prediverse > 0) & (diverse < 0)  # NaN 参与比较→False→自然落 0(等价旧 isnan 守卫)
    sig = sig.mask(buy, 1).mask(sell, -1)
    return sig.astype(int)


# ---------------------------------------------------------------------------
# 8) 「OnBalanceVolAve」—— OnBalanceVolAve.py（★实为成交量双 SMA 交叉,非累计 OBV,见下）
# ---------------------------------------------------------------------------
def obv_signal(prices: pd.DataFrame, *, nl: int = 50, ns: int = 10) -> pd.Series:
    """成交量(volume)双 SMA 交叉判据 —— **文件名叫 OBV,但实现里没有任何累计 OBV**。

    旧文件:strategies/componentTradingRules/OnBalanceVolAve.py
    ★★命名 vs 实现的重大出入(如实标注,本迁移忠于**实现**,不擅自补真 OBV):
      文件名/注释自称 "On-Balance Volume Average",但**代码逻辑**是(run() 逐行):
          smal = volume.rolling(nl).mean()     # 长周期成交量 SMA
          smas = volume.rolling(ns).mean()     # 短周期成交量 SMA(ns<nl)
          buy  = smas > smal ; sell = smas < smal
      文件注释自己也写明「OBVA is the same as MA except that OBVA calculates moving average
      with stock volume instead of stock price」——即**只是把 MovingAverage 的价格换成成交量**,
      而非标准 OBV(标准 OBV = 按涨跌方向对成交量做**自起点累计**的能量线,再取其均线)。
      故本规则:
        · **不是** path-dependent,**不进 _STATEFUL**(有限 rolling 窗即可精确复现,parity 可逐日等);
        · 与 ma_cross 结构完全相同,仅数据列 close→volume。
      全仓库(含旧 strategies/)grep 无任何 cumsum/累计 OBV 实现 —— 真 OBV 从未被写过。
      ⇒ 若日后要「真·OBV 能量潮」,那是**新规则**(需新写累计线,届时才 _STATEFUL),
         不属本次「迁移」范畴。此处特意留证,交用户裁决是否另立新规则。

    旧 score(row):
        if isnan(smas) or isnan(smal): return 0
        if buy:  return +1     # 短量均线在长量均线上方(放量趋势)
        if sell: return -1
        return 0
    旧参数:nl(长)、ns(短);defaultParam 网格 nl=range(5,250,5)、ns=range(1,10)+range(15,200,5)。
        取 nl=50,ns=10 作默认(网格无唯一默认,迁移取值选择;checkParams 要求 nl>ns,满足)。

    信号语义:-1/0/1 状态(量能短/长均线相对位置)。有限窗,MIN_WINDOW=max(nl,ns)=nl。
    """
    nl = int(nl); ns = int(ns)
    vol = prices["volume"].astype(float)
    sig = pd.Series(0, index=prices.index, dtype=int)
    if len(vol) < nl:
        return sig
    smal = vol.rolling(nl).mean()   # 长
    smas = vol.rolling(ns).mean()   # 短
    sig = sig.mask(smas > smal, 1).mask(smas < smal, -1)
    sig.iloc[: nl - 1] = 0          # rolling(nl) 未满段强制 0(旧 warm-up)
    return sig.astype(int)


# ---------------------------------------------------------------------------
# 9) 区间突破 —— tradingRangeBreakout.py
# ---------------------------------------------------------------------------
def range_breakout_signal(prices: pd.DataFrame, *, n: int = 20) -> pd.Series:
    """n 日区间突破(今日收盘触及 n 日最高/最低)。

    旧文件:strategies/componentTradingRules/tradingRangeBreakout.py
    旧 run():
        highest = adjclose.rolling(n).max()      # ★ 含当日的 n 根窗口(见下与注释的出入)
        lowest  = adjclose.rolling(n).min()
    旧 score(row):
        if (highest==np.nan) or (lowest==np.nan): return 0   # 死代码,x==np.nan 恒 False(同 bollinger)
        if adjclose == highest: return +1        # 今日收盘 == 窗口最高 → 买(创新高)
        if adjclose == lowest:  return -1        # 今日收盘 == 窗口最低 → 卖(创新低)
        return 0
    旧参数:n(回看天数),defaultParam=range(10,255)。取 n=20 作默认(迷你 Donchian,
        网格无唯一默认,迁移取值选择;checkParams 要求 n>1)。

    ★旧代码 注释 vs 实现 的出入(如实标注,照**实现**迁移):
      文件头注释写 Ht,n = max(p_{t-1},...,p_{t-n}) = **前 n 天(不含今日)**的最高,买入判据 pt>Ht,n
      (严格大于、且不含今日)。但**实现**用 rolling(n).max()(**含当日**),再判 adjclose==highest
      (相等,非严格 >)。二者不同:实现是「今日收盘 = 含今日的 n 日窗口内最高」= 今日创 n 日新高。
      本迁移照实现(含今日 rolling + 相等判据),不按注释加 shift(1)/改严格 >。
      浮点相等安全性:rolling(n).max() 含今日,今日恰为窗口最大时,highest 就是今日那个元素本身
      (同一浮点值,无舍入)⇒ `adjclose==highest` 精确成立,不存在浮点比较陷阱。
      同 bollinger:score 首行 NaN 守卫是死代码;但 warm-up 段 highest/lowest 为 NaN,
      `adjclose==NaN` 恒 False → 自然落 0,行为无差异,再以 MIN_WINDOW 显式挡。

    信号语义:-1/0/1 事件(创新高/新低日);震荡段可能同一根既非最高也非最低 → 0。
    注:若某窗口内今日既是最高又是最低(全窗等值,极罕见),buy 先判 → 记 +1(照旧 score 顺序)。
    有限窗,MIN_WINDOW=n。
    """
    n = int(n)
    close = prices["close"].astype(float)
    sig = pd.Series(0, index=prices.index, dtype=int)
    if len(close) < n:
        return sig
    highest = close.rolling(n).max()   # 含当日
    lowest = close.rolling(n).min()
    is_high = close == highest         # 精确相等(highest 含今日,见 docstring)
    is_low = close == lowest
    # 旧 score 顺序:先判 highest(买),再判 lowest(卖);故 buy 优先(mask 顺序保证)
    sig = sig.mask(is_low, -1).mask(is_high, 1)
    sig.iloc[: n - 1] = 0              # rolling(n) 未满段强制 0(NaN==x 已为 False,再显式挡)
    return sig.astype(int)


# ---------------------------------------------------------------------------
# 10) 价格双 SMA 交叉 —— MovingAverage.py(与 sma_crossover.py 的 long/flat 等价)
# ---------------------------------------------------------------------------
def ma_cross_signal(prices: pd.DataFrame, *, nl: int = 50, ns: int = 20) -> pd.Series:
    """价格双 SMA 交叉:短 SMA 在长 SMA 上方 → +1、下方 → -1。

    旧文件:strategies/componentTradingRules/MovingAverage.py
    旧 calculate()/score()(逐行照搬):
        smal = adjclose.rolling(nl).mean()   # 长
        smas = adjclose.rolling(ns).mean()   # 短(ns<nl)
        buy  = smas > smal ; sell = smas < smal
        if isnan(smas) or isnan(smal): return 0
        if buy:  return +1
        if sell: return -1
        return 0
    旧参数:nl(长)、ns(短);defaultParam 网格 nl=range(15,255,5)、ns=range(1,10)+range(10,200,5)。
        取 nl=50,ns=20 作默认(对齐 sma_crossover.py 的 long=50/short=20 便于对照;
        网格无唯一默认,迁移取值选择;checkParams 要求 nl>ns)。

    与 zipline_lab/sma_crossover.py 的**等价关系**(参数映射 + 取舍):
      sma_crossover(短=short_window, 长=long_window)口径:sig = int(short_ma > long_ma) ∈ {0,1}
      (只 long/flat,无做空),前 long_window-1 天强制 0。
      本 ma_cross 与之**在 long/flat 下单口径下逐日等价**,映射:ns ↔ short_window、nl ↔ long_window。
        · 判据同为 short_ma>long_ma;相等(==)两者都落 0(sma_crossover 的 int(>) 与本 mask 都不置 1);
        · warm-up 同为「长窗未满 → 0」(sma_crossover 用 bar 门闩,本函数用 iloc 前置 0);
        · **唯一差异**:本 ma_cross 在 short<long 时输出 **-1**(sma_crossover 输出 0)。此差异
          仅当 allow_short=True 才显现;rule_factory 默认 long/flat 会把 -1→0,故与 sma_crossover 恒等。
      结论:两者非同一函数(-1 vs 0 的原始三态不同),但在旧论文/本框架默认的 long/flat 口径下
      完全等价,可互为回归对照。保留独立 ma_cross 是为忠实旧规则的三态语义(-1 可被 allow_short 激活)。
      注:sma_crossover 用 data.history 的 "price"(=adj_close),本函数用 close(bundle 已 close≡adj_close),口径一致。

    信号语义:-1/0/1 状态(短/长 SMA 相对位置)。有限窗,MIN_WINDOW=nl。
    """
    nl = int(nl); ns = int(ns)
    close = prices["close"].astype(float)
    sig = pd.Series(0, index=prices.index, dtype=int)
    if len(close) < nl:
        return sig
    smal = close.rolling(nl).mean()   # 长
    smas = close.rolling(ns).mean()   # 短
    sig = sig.mask(smas > smal, 1).mask(smas < smal, -1)
    sig.iloc[: nl - 1] = 0            # 长窗未满段强制 0(旧 warm-up)
    return sig.astype(int)


# ---------------------------------------------------------------------------
# 11) 多规则加权合成 —— WeightAdjRule.py(旧为未完成 stub,按其书面意图重写)
# ---------------------------------------------------------------------------
def _weighted_member_params(params: dict) -> dict:
    """weighted 的成员参数覆写表({rule_name: {param overrides}}),缺省 {}。"""
    return dict((params or {}).get("member_params") or {})


def _member_merged_params(member: str, member_params: dict) -> dict:
    """某成员规则的完整参数 = 其 DEFAULT_PARAMS 叠加 member_params 覆写。"""
    merged = dict(DEFAULT_PARAMS[member])
    merged.update((member_params or {}).get(member, {}))
    return merged


def weighted_signal(
    prices: pd.DataFrame,
    *,
    weights: dict | None = None,
    threshold: float = 0.0,
    member_params: dict | None = None,
) -> pd.Series:
    """多分量规则加权合成:Σ w_i·signal_i,按 Σ|w| 归一后过对称阈值 → -1/0/1。

    旧文件:strategies/componentTradingRules/WeightAdjRule.py
    ★旧代码状态(如实标注):**未完成的 stub**。它:
        · InitalWt(220) 生成 220 个等权 1/220;
        · 声称「按过去 ms 期表现动态调整各分量规则权重」(PRS = 分量规则组合的表现加权);
        · 但函数体只 import 了不存在的 bb/utils,循环里全是 `print(invest)`,**从未真正合成出信号**,
          也**从未实现**那套「按 ms 期表现调权」的动态逻辑。即:旧文件只有意图与骨架,无可运行合成。
    因此本迁移**不是照抄**(无可抄的合成实现),而是按其**书面意图**(header 的 Input=当日+规则权重,
      Output=更新后权重;body 想做的是「各分量规则打分 → 加权 → 出组合信号」)落一个干净的**静态加权**实现:

    新实现语义:
        weights = {rule_name: weight}(调 SIGNAL_FUNCS 已登记规则;成员参数走 member_params 覆写,缺省各自 DEFAULT_PARAMS)
        combined = Σ_i weight_i · signal_i(prices) ,  signal_i ∈ {-1,0,1}
        combined /= Σ_i |weight_i|            # 归一到 [-1,1](对齐旧 InitalWt 的等权归一精神)
        signal = +1 if combined >  threshold
               = -1 if combined < -threshold
               =  0 otherwise                 # 对称阈值,threshold∈[0,1) 造中性死区
    与旧实现的**取舍**(如实交代):
      (a) 旧「按过去 ms 期表现动态调权」未实现 ⇒ 本函数取**静态权重**(由调用方/walk-forward/PSO 外层
          依历史表现设定后传入),不在信号函数内做前视式的表现回看(那会引入 look-ahead,违本框架硬规则)。
          即把「调权」职责上移到研究外层,信号层只做纯 trailing 的加权合成。
      (b) 归一用 Σ|w|(旧等权隐含归一到 1);threshold 默认 0.0 = 取加权和符号(多数决)。
      (c) 成员各自 trailing-safe 且 parity 成立 ⇒ 逐点加权+定阈 = 逐点函数 ⇒ weighted 自身 parity 亦成立
          (per-bar 取数窗取所有成员 lookback 的 max,保证每个成员都被精确复现;见 lookback_bars 特判)。

    ★_STATEFUL 传染:任一成员 ∈ _STATEFUL(如 sma8)⇒ weighted 自身按 stateful 处理(取数用全段扩张窗,
      见 is_stateful / lookback_bars 的 weighted 分支)。默认成员(macd/bollinger/stochastic)皆有限窗 ⇒
      默认 weighted **非** stateful。

    默认组合(DEFAULT_PARAMS):{macd:1, bollinger:1, stochastic:1} 等权、threshold=0.0(3 成员做冒烟/parity)。

    信号语义:-1/0/1;稀疏度取决于成员与阈值。
    """
    weights = dict(weights or DEFAULT_PARAMS["weighted"]["weights"])
    member_params = dict(member_params or {})
    idx = prices.index
    combined = pd.Series(0.0, index=idx)
    total_w = sum(abs(float(w)) for w in weights.values())
    for member, w in weights.items():
        s = compute_signal(member, prices, member_params.get(member, {})).astype(float)
        combined = combined + float(w) * s
    if total_w > 0:
        combined = combined / total_w   # 归一到 [-1,1]
    thr = float(threshold)
    sig = pd.Series(0, index=idx, dtype=int)
    sig = sig.mask(combined > thr, 1).mask(combined < -thr, -1)
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
    "sma8": sma8_signal,
    "macd_hist": macd_hist_signal,
    "obv": obv_signal,
    "range_breakout": range_breakout_signal,
    "ma_cross": ma_cross_signal,
    "weighted": weighted_signal,
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
    "sma8": dict(t1=5, t2=120, t3=60, t4=200, t5=5, t6=120, t7=60, t8=200),
    "macd_hist": dict(nl=26, ns=12, t=9),
    "obv": dict(nl=50, ns=10),
    "range_breakout": dict(n=20),
    "ma_cross": dict(nl=50, ns=20),
    # weighted:默认 3 成员等权 + 阈值 0(多数决);成员各用自己的 DEFAULT_PARAMS
    "weighted": dict(
        weights={"macd": 1.0, "bollinger": 1.0, "stochastic": 1.0},
        threshold=0.0,
        member_params={},
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
    # 8 条 SMA 就绪(最长窗)后状态机才可能翻态;前 max(t..)-1 根强制 flat。
    "sma8": lambda p: max(
        int(p.get("t1", 5)), int(p.get("t2", 120)), int(p.get("t3", 60)),
        int(p.get("t4", 200)), int(p.get("t5", 5)), int(p.get("t6", 120)),
        int(p.get("t7", 60)), int(p.get("t8", 200)),
    ),
    # 纯 EMA(min_periods=0)自 bar1 出信号,bar0 因 prediverse=NaN 自然为 0 → 同 macd,门 1
    "macd_hist": lambda p: 1,
    # 成交量双 SMA:长窗就绪即可(有限窗)
    "obv": lambda p: max(int(p.get("nl", 50)), int(p.get("ns", 10))),
    "range_breakout": lambda p: int(p.get("n", 20)),
    "ma_cross": lambda p: max(int(p.get("nl", 50)), int(p.get("ns", 20))),
    # weighted:所有成员 MIN_WINDOW 的 max(成员各用其 DEFAULT_PARAMS 叠加 member_params)
    "weighted": lambda p: max(
        (
            MIN_WINDOW[m](_member_merged_params(m, _weighted_member_params(p)))
            for m in (p.get("weights") or DEFAULT_PARAMS["weighted"]["weights"])
        ),
        default=1,
    ),
}

# EMA 类规则的 last 值依赖全历史(递归),trailing 窗口须给足缓冲让 seed 衰减到不翻整数信号;
# 有限窗规则(rolling)last 值只依赖窗口内 MIN_WINDOW 根,缓冲无关正确性(给点余量即可)。
_EMA_BUFFER = 300   # macd / momentum_rule / macd_hist 的 EMA seed 衰减缓冲
_FINITE_BUFFER = 5  # bollinger / rsi / stochastic / obv / range_breakout / ma_cross
_EMA_RULES = ("macd", "momentum_rule", "macd_hist")  # last 值依赖全历史(递归 EMA)

# ★状态机规则(sma8):仓位状态 path-dependent(见 sma8_signal docstring),固定 trailing
#   窗口会截断更早的进/出场触发而错判状态 ⇒ 必须用「全段扩张窗口」。用一个大到吃满任何回测
#   长度的哨兵:rule_factory 的 n=min(bar_count, look) 恒取 bar_count(自起点至今),
#   test_parity 的 lo=max(0,t-look+1) 恒为 0 ⇒ 二者都退化为「自 bar0 起的扩张窗口」,
#   与全区间向量化逐日一致。哨兵取 10^9(> 任何实际交易日数)。
_STATEFUL = {"sma8"}
_FULL_SEGMENT = 1_000_000_000


def is_stateful(rule_name: str, params: dict | None = None) -> bool:
    """规则(给定 params)是否 path-dependent(需全段扩张窗口重放)。

    sma8 恒 stateful;weighted 当**任一成员** stateful 时传染为 stateful;其余否。
    供 test_parity 的取数/显示与 lookback_bars 共用同一判据,避免 `rule in _STATEFUL` 漏掉 weighted。
    """
    if rule_name in _STATEFUL:
        return True
    if rule_name == "weighted":
        p = params or {}
        weights = p.get("weights") or DEFAULT_PARAMS["weighted"]["weights"]
        mp = _weighted_member_params(p)
        return any(is_stateful(m, _member_merged_params(m, mp)) for m in weights)
    return False


def lookback_bars(rule_name: str, params: dict) -> int:
    """rule_factory / test_parity 每 bar 取数(以及逐 bar 模拟)用的 trailing 窗口长度。

    有限窗/EMA 规则 = MIN_WINDOW(params) + 缓冲(EMA 类给大缓冲);
    状态机规则(sma8,或含 stateful 成员的 weighted)= 全段哨兵(_FULL_SEGMENT),强制扩张窗口重放;
    weighted(全有限成员)= 所有成员 lookback 的 max(保证每个成员都被精确复现 → weighted parity 成立)。
    """
    if rule_name == "weighted":
        p = params or {}
        weights = p.get("weights") or DEFAULT_PARAMS["weighted"]["weights"]
        mp = _weighted_member_params(p)
        if any(is_stateful(m, _member_merged_params(m, mp)) for m in weights):
            return _FULL_SEGMENT
        return max(
            (lookback_bars(m, _member_merged_params(m, mp)) for m in weights),
            default=_FINITE_BUFFER,
        )
    if rule_name in _STATEFUL:
        return _FULL_SEGMENT
    mw = MIN_WINDOW[rule_name](params)
    buf = _EMA_BUFFER if rule_name in _EMA_RULES else _FINITE_BUFFER
    return int(mw + buf)


def compute_signal(rule_name: str, prices: pd.DataFrame, params: dict) -> pd.Series:
    """按 rule_name 调对应向量化函数(params 缺省用 DEFAULT_PARAMS 补全)。"""
    merged = dict(DEFAULT_PARAMS[rule_name])
    merged.update(params or {})
    return SIGNAL_FUNCS[rule_name](prices, **merged)
