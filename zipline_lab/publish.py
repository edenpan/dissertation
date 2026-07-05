"""发布器:把回测结果写入 altas_media.bt_run / bt_equity / bt_signal(altas 账号)。

凭据来源(与 altas-web 同一来源):
  - 用户名:环境变量 ALTAS_DB_USER,缺省 'altas'。
  - 密码:环境变量 ALTAS_DB_PASSWORD 优先;缺省时退回 altas-web 侧同一来源
    ——altas_core.config.get_secret('altas_db_password')(读 private.keys)。
  - 读 private.keys 需管理员凭据,来自 ALTAS_ADMIN_ENV_FILE 指向的 .env(默认已在下方
    setdefault 为 webbsite 仓的 .env,内含 eden 账号);缺失则清晰报错。
两者都取不到密码时抛 RuntimeError(不静默连空密码)。

幂等:UNIQUE(strategy,symbol,bundle,segment,start,end,params) 冲突时走 REPLACE 语义
——先按自然键(params 用 JSON 语义比较,规避 key 顺序/空白差异)查 run_id,删旧行
(bt_equity/bt_signal 靠 FK ON DELETE CASCADE 连带清)再重插。
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

# --- 让 altas_core 可导入(venv 未装):优先 co-located altas-quant/altas-core -------------
for _cand in (
    "/home/eden/code/altas-quant/altas-core",
    "/home/eden/code/altas/altas-core",
):
    if (Path(_cand) / "altas_core").is_dir() and _cand not in sys.path:
        sys.path.insert(0, _cand)
# 读 private.keys 的管理员 .env(webbsite 仓那份含 eden);altas_core 默认指向的 llm .env 为空
os.environ.setdefault(
    "ALTAS_ADMIN_ENV_FILE",
    "/home/eden/code/opensource/webbsite/Webb-site_repository/python/.env",
)

_TRADING_DAYS = 252


# ---------------------------------------------------------------------------
# 连接
# ---------------------------------------------------------------------------
def _load_altas_config():
    """直接按文件加载 altas_core/config.py(不触发 package __init__ 的 llm/notify 重依赖)。

    这是 altas-web 侧读密钥用的同一份代码(config.get_secret 读 private.keys)。
    """
    import importlib.util
    for cand in ("/home/eden/code/altas-quant/altas-core",
                 "/home/eden/code/altas/altas-core"):
        p = Path(cand) / "altas_core" / "config.py"
        if p.exists():
            spec = importlib.util.spec_from_file_location("_altas_config", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise RuntimeError("找不到 altas_core/config.py(altas-core 未就位)")


def _resolve_password() -> str:
    pw = os.environ.get("ALTAS_DB_PASSWORD")
    if pw:
        return pw
    try:
        config = _load_altas_config()  # 同 altas-web 的密钥来源
        pw = config.get_secret("altas_db_password")
    except Exception as ex:  # noqa: BLE001
        raise RuntimeError(
            "无法解析 altas 账号密码:未设 ALTAS_DB_PASSWORD,且导入 altas_core.config "
            f"取 private.keys 失败:{ex}"
        ) from ex
    if not pw:
        raise RuntimeError(
            "无法解析 altas 账号密码:ALTAS_DB_PASSWORD 未设,且 "
            "altas_core.config.get_secret('altas_db_password') 返回空。"
            "请设 ALTAS_DB_PASSWORD,或确认 ALTAS_ADMIN_ENV_FILE 指向含 eden 账号的 .env。"
        )
    return pw


_ENGINE = None


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        host = os.environ.get("ALTAS_DB_HOST", "127.0.0.1")
        port = int(os.environ.get("ALTAS_DB_PORT", "3306"))
        user = os.environ.get("ALTAS_DB_USER", "altas")
        name = os.environ.get("ALTAS_DB_NAME", "altas_media")
        pw = _resolve_password()
        url = f"mysql+pymysql://{user}:{pw}@{host}:{port}/{name}?charset=utf8mb4"
        _ENGINE = create_engine(url, pool_pre_ping=True, future=True)
    return _ENGINE


# ---------------------------------------------------------------------------
# 指标
# ---------------------------------------------------------------------------
def _finite(x):
    """非有限(NaN/inf)→ None,便于进 JSON(MySQL 不吃 NaN)。"""
    if x is None:
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def compute_metrics(perf: pd.DataFrame | None, equity: pd.Series | None) -> dict:
    """统一口径算 total_return / sharpe(年化,rf=0)/ max_dd / n_days / n_txn。

    equity(资产净值序列)优先取显式传入,否则取 perf['portfolio_value']。
    """
    eq = equity if equity is not None else (
        perf["portfolio_value"] if perf is not None and "portfolio_value" in perf else None)
    m: dict = {}
    if eq is None:
        return m
    eq = pd.Series(eq).astype(float).dropna()
    if len(eq) == 0:
        return m
    # 总收益:有 zipline 的 algorithm_period_return 就用它(与引擎自报一致),否则净值比
    if perf is not None and "algorithm_period_return" in perf:
        m["total_return"] = _finite(perf["algorithm_period_return"].iloc[-1])
    else:
        m["total_return"] = _finite(eq.iloc[-1] / eq.iloc[0] - 1.0)
    # 年化 Sharpe:日收益均值/标准差 * sqrt(252),rf=0
    if perf is not None and "returns" in perf:
        daily = pd.Series(perf["returns"]).astype(float)
    else:
        daily = eq.pct_change()
    daily = daily.dropna()
    sd = daily.std(ddof=1) if len(daily) > 1 else 0.0
    m["sharpe"] = _finite(daily.mean() / sd * math.sqrt(_TRADING_DAYS)) if sd and sd > 0 else None
    # 最大回撤
    dd = eq / eq.cummax() - 1.0
    m["max_dd"] = _finite(dd.min())
    m["n_days"] = int(len(eq))
    # 成交笔数(仅 perf 有 transactions 时)
    if perf is not None and "transactions" in perf:
        m["n_txn"] = int(sum(len(t) for t in perf["transactions"]))
    return m


def _json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _to_date(idx):
    ts = pd.Timestamp(idx)
    return ts.date()


# ---------------------------------------------------------------------------
# 发布
# ---------------------------------------------------------------------------
def publish_run(
    *,
    strategy: str,
    symbol: str,
    segment: str,
    start,
    end,
    params: dict,
    perf: pd.DataFrame | None = None,
    equity: pd.Series | None = None,
    signal: pd.Series | None = None,
    metrics: dict | None = None,
    report_md: str | None = None,
    source: str | None = None,
    bundle: str = "stockdb",
) -> int:
    """写一条回测 run + 其净值/信号曲线,返回 run_id。幂等(自然键冲突则先删后插)。

    - metrics 缺省从 perf/equity 统一算。
    - equity 缺省从 perf['portfolio_value'] 取;signal 缺省从 perf['signal'] 取(无则跳过)。
    """
    # 解析净值/信号序列
    eq_series = equity
    if eq_series is None and perf is not None and "portfolio_value" in perf:
        eq_series = perf["portfolio_value"]
    sig_series = signal
    if sig_series is None and perf is not None and "signal" in perf:
        sig_series = perf["signal"]

    if metrics is None:
        metrics = compute_metrics(perf, eq_series)

    params_json = _json(params or {})
    metrics_json = _json(metrics or {})
    start_d = _to_date(start)
    end_d = _to_date(end)

    eng = get_engine()
    with eng.begin() as cx:
        # 幂等:params 用 JSON 语义比较(不依赖 params_hash 的 MySQL 序列化细节)
        existing = cx.execute(text(
            "SELECT run_id FROM bt_run WHERE strategy=:s AND symbol=:sym AND bundle=:b "
            "AND segment=:seg AND start_date=:sd AND end_date=:ed "
            "AND params = CAST(:p AS JSON)"
        ), {"s": strategy, "sym": symbol, "b": bundle, "seg": segment,
            "sd": start_d, "ed": end_d, "p": params_json}).scalar()
        if existing is not None:
            # CASCADE 连带清 bt_equity/bt_signal
            cx.execute(text("DELETE FROM bt_run WHERE run_id=:r"), {"r": existing})

        res = cx.execute(text(
            "INSERT INTO bt_run (strategy, symbol, bundle, segment, start_date, end_date, "
            "params, metrics, report_md, source) VALUES "
            "(:s, :sym, :b, :seg, :sd, :ed, CAST(:p AS JSON), CAST(:m AS JSON), :rmd, :src)"
        ), {"s": strategy, "sym": symbol, "b": bundle, "seg": segment,
            "sd": start_d, "ed": end_d, "p": params_json, "m": metrics_json,
            "rmd": report_md, "src": source})
        run_id = int(res.lastrowid)

        # 净值逐日
        if eq_series is not None:
            eq_series = pd.Series(eq_series).astype(float).dropna()
            rows = [{"r": run_id, "d": _to_date(i), "v": float(v)}
                    for i, v in eq_series.items() if math.isfinite(float(v))]
            if rows:
                cx.execute(text(
                    "INSERT INTO bt_equity (run_id, `date`, value) VALUES (:r, :d, :v)"), rows)

        # 信号逐日(没有就跳过)
        if sig_series is not None:
            sig_series = pd.Series(sig_series).dropna()
            rows = [{"r": run_id, "d": _to_date(i), "sig": int(round(float(v)))}
                    for i, v in sig_series.items()]
            if rows:
                cx.execute(text(
                    "INSERT INTO bt_signal (run_id, `date`, `signal`) VALUES (:r, :d, :sig)"), rows)

    return run_id


if __name__ == "__main__":
    # 连通性自检(不写数据)
    with get_engine().connect() as c:
        print("bt_run rows:", c.execute(text("SELECT COUNT(*) FROM bt_run")).scalar())
