"""zipline custom bundle `techdiff`:接法三证伪回测专用美股日线。

数据源 = screener 侧本地 Parquet(`papers/tech-diffusion/data/prices/<TICKER>.parquet`,
由 fetch_prices.py 用 yfinance auto_adjust=False 下的),**不碰 stockdb 任何表**——实验隔离,
整体可删,不污染 B 线共享票池。路径走环境变量 TECHDIFF_PRICES_DIR(默认指向 screener 绝对路径)。

仿 bundle_stockdb.py 的设计(逐条对应,口径一致):
- sid = Compustat gvkey(整数,来自 _manifest.csv):可追溯回 Compustat/信号表、重灌稳定。
  (bundle_stockdb 用 symbols.id;这里没有 symbols 表,gvkey 是天然稳定主键。)
- 复权:OHLC 整体乘 factor = adj_close/close,close ≡ adj_close 口径;缺 adj_close 的行
  factor=1;不写 splits/dividends(复权已烧进价格,adjustment 写空表)。volume 不缩放。
- 缺日:reindex 到 XNYS session 后 close 前向填充、OHL=close、volume=0(daily_bar_writer
  对 session 缺失零容忍)。开头缺数的行裁掉(首日必须有 close)。
- 日期范围:PIN_START=2010-12-01 钉死起点(数据首日,fetch 区间起点),与各票实际首末日取交集。

zipline-reloaded 3.1.1 坑(同 bundle_stockdb,勿踩):
- 全程 tz-naive;价格 uint32 毫元(×1000),对齐容差 5e-4;run_algorithm 外传零收益 benchmark;
- ~/.zipline/extension.py 自动加载(本 bundle 追加注册,保留原 stockdb 两行)。
- 显式钉 start_session/end_session,解耦 exchange_calendars 滚动窗口(见 bundle_stockdb
  register docstring 的完整解释),防未来某日读 bundle DateOutOfBounds。

调试:环境变量 TECHDIFF_BUNDLE_SYMBOLS="QCOM,AAPL" 限定标的做单标的调通。

用法:
    export TECHDIFF_PRICES_DIR=/home/eden/code/altas/screener/papers/tech-diffusion/data/prices
    .venv-zipline/bin/zipline ingest -b techdiff
    .venv-zipline/bin/zipline bundles
"""
from __future__ import annotations

import csv
import os

import numpy as np
import pandas as pd
from exchange_calendars.errors import CalendarNameCollision
from zipline.data.bundles import register
from zipline.utils.calendar_utils import get_calendar, register_calendar_alias

BUNDLE_NAME = "techdiff"
EXCHANGE = "TECHDIFF"  # 自造交易所名,canonical 指到 XNYS

DEFAULT_PRICES_DIR = (
    "/home/eden/code/altas/screener/papers/tech-diffusion/data/prices"
)

# 钉死日历边界(同 bundle_stockdb 根治):数据 2010-12-01 起,钉 2010-12-01 起点。
PIN_START_SESSION = pd.Timestamp("2010-12-01")
PIN_END_SESSION = pd.Timestamp("2027-12-31")


def _prices_dir() -> str:
    return os.environ.get("TECHDIFF_PRICES_DIR", DEFAULT_PRICES_DIR)


def _pinned_sessions(calendar_name: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    cal = get_calendar(calendar_name)
    start = max(PIN_START_SESSION, cal.first_session)
    end = min(PIN_END_SESSION, cal.last_session)
    sess = cal.sessions_in_range(start, end)
    return sess[0], sess[-1]


def _load_manifest(prices_dir: str) -> list[dict]:
    """读 _manifest.csv 拿 ticker->gvkey(sid)。status=ok 且 parquet 存在的才收。

    manifest 缺失时回退:扫描目录 <TICKER>.parquet,sid 用 ticker 的稳定哈希(避免撞号取
    正整数域)。正常路径永远有 manifest(fetch_prices 产出),回退仅防手工放文件。"""
    manifest = os.path.join(prices_dir, "_manifest.csv")
    only = os.environ.get("TECHDIFF_BUNDLE_SYMBOLS")
    wanted = {s.strip().upper() for s in only.split(",")} if only else None

    rows: list[dict] = []
    seen_sid: set[int] = set()
    if os.path.exists(manifest):
        with open(manifest) as f:
            for r in csv.DictReader(f):
                if r["status"] != "ok":
                    continue
                ticker = r["ticker"].strip().upper()
                if wanted and ticker not in wanted:
                    continue
                p = os.path.join(prices_dir, f"{ticker}.parquet")
                if not os.path.exists(p):
                    continue
                try:
                    sid = int(r["gvkey"])
                except (ValueError, KeyError):
                    sid = abs(hash(ticker)) % (10**9)
                # 防 sid 撞号(gvkey 理论唯一,保险起见)
                while sid in seen_sid:
                    sid += 10**9
                seen_sid.add(sid)
                rows.append({"sid": sid, "ticker": ticker, "path": p})
    else:
        for fn in sorted(os.listdir(prices_dir)):
            if not fn.endswith(".parquet") or fn.startswith("_"):
                continue
            ticker = fn[:-8].upper()
            if wanted and ticker not in wanted:
                continue
            sid = abs(hash(ticker)) % (10**9)
            while sid in seen_sid:
                sid += 10**9
            seen_sid.add(sid)
            rows.append({"sid": sid, "ticker": ticker,
                         "path": os.path.join(prices_dir, fn)})
    return rows


def _ingest_impl(
    environ,
    asset_db_writer,
    minute_bar_writer,
    daily_bar_writer,
    adjustment_writer,
    calendar,
    start_session,
    end_session,
    cache,
    show_progress,
    output_dir,
):
    prices_dir = _prices_dir()
    assets = _load_manifest(prices_dir)
    if not assets:
        raise ValueError(
            f"techdiff: no price parquet found under {prices_dir!r} "
            f"(TECHDIFF_BUNDLE_SYMBOLS filter may be too strict)"
        )

    sessions = calendar.sessions_in_range(
        pd.Timestamp(start_session), pd.Timestamp(end_session)
    )
    meta_rows = []

    def gen():
        for a in assets:
            df = pd.read_parquet(a["path"])
            if df.empty:
                continue
            df = df.copy()
            df["date"] = pd.to_datetime(df["date"])
            if getattr(df["date"].dt, "tz", None) is not None:
                df["date"] = df["date"].dt.tz_localize(None)
            df = df.set_index("date").sort_index()
            df = df[~df.index.duplicated(keep="last")]

            # 预复权:close ≡ adj_close(缺 adj_close 行 factor=1)
            factor = (df["adj_close"] / df["close"]).replace(
                [np.inf, -np.inf], np.nan).fillna(1.0)
            for col in ("open", "high", "low", "close"):
                df[col] = df[col] * factor

            asset_sessions = sessions[(sessions >= df.index[0]) & (sessions <= df.index[-1])]
            if len(asset_sessions) == 0:
                continue
            df = df.reindex(asset_sessions)
            df = df[df["close"].notna().cummax()]  # 裁掉开头缺数
            if df.empty:
                continue
            df["close"] = df["close"].ffill()
            for col in ("open", "high", "low"):
                df[col] = df[col].fillna(df["close"])
            df["volume"] = df["volume"].fillna(0).astype(np.int64)

            meta_rows.append(dict(
                sid=a["sid"],
                symbol=a["ticker"],
                asset_name=a["ticker"],
                start_date=df.index[0],
                end_date=df.index[-1],
                first_traded=df.index[0],
                auto_close_date=df.index[-1] + pd.Timedelta(days=1),
                exchange=EXCHANGE,
            ))
            yield a["sid"], df[["open", "high", "low", "close", "volume"]]

    daily_bar_writer.write(gen(), show_progress=show_progress)

    equities = pd.DataFrame(meta_rows).set_index("sid")
    exchanges = pd.DataFrame(
        {"exchange": [EXCHANGE], "canonical_name": ["XNYS"], "country_code": ["US"]}
    )
    asset_db_writer.write(equities=equities, exchanges=exchanges)
    adjustment_writer.write(
        splits=pd.DataFrame(columns=["sid", "ratio", "effective_date"]),
        dividends=pd.DataFrame(
            columns=["sid", "amount", "ex_date", "record_date", "declared_date", "pay_date"]
        ),
    )


def register_techdiff_bundle() -> None:
    """幂等注册 bundle `techdiff`(XNYS 日历,钉 start=2010-12-01)。"""
    try:
        register_calendar_alias(EXCHANGE, "XNYS")
    except CalendarNameCollision:
        pass
    start_session, end_session = _pinned_sessions("XNYS")
    register(
        BUNDLE_NAME,
        _ingest_impl,
        calendar_name="XNYS",
        start_session=start_session,
        end_session=end_session,
    )
