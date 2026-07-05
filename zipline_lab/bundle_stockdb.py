"""zipline custom bundle:主实例 MySQL `stockdb` 的美股日线 → bundle `stockdb`。

数据源:stockdb.daily_prices / stockdb.symbols(旧 quant_system 纸交易工程灌的,
827 只美股,2013-01-02 起,含 adj_close)。**只读**——该表比 common.db 的 ORM 模型
多一个 NOT NULL 冗余 symbol 列和时间戳列,ORM 写不兼容,故这里用裸 SQL,也不
import common.db。

连接:环境变量 DATA_DB_HOST/PORT/USER/PASSWORD/NAME(样板 zipline_lab/env.example,
约定用最小权只读账号 altas)。zipline CLI 是独立进程,跑 ingest 前必须先在 shell
`set -a; source .env; set +a`。

设计决策:
- sid 直接用 stockdb.symbols.id:可追溯回库、重灌稳定。
- 复权:OHLC 整体乘 factor = adj_close/close,不写 splits/dividends(库里只有
  adj_close 快照,反推逐事件调整既易错又无必要)。缩放后 bundle 的 close ≡
  adj_close,与旧 strategies/backtester.py 的 price 口径(adj_close 优先)同源,
  这是信号级对齐的基石。volume 不缩放。
- 缺日:daily_bar_writer 对 session 缺失零容忍(bcolz_daily_bars 硬校验行数 ==
  sessions_in_range 长度),因此 reindex 到日历 session 后 close 前向填充、
  OHL=close、volume=0;非 session 行(数据脏日)由 reindex 自然丢弃。
- 日期范围:ingest 时查库取 MIN/MAX(traded_at) 与传入 start/end session 取交集,
  数据刷新后无需改注册代码。

zipline-reloaded 3.1.1 已知坑(勿踩):
- 全程 tz-naive(3.x 起),Timestamp 不要带 tz。
- 价格按 uint32 毫元(×1000)存储 → bundle 内价格精度 0.001,对齐比较容差取 5e-4。
- run_algorithm 默认联网拉 benchmark,策略侧必须外传零收益序列(见 strategy_base)。
- run_algorithm / CLI 都会自动加载 ~/.zipline/extension.py,策略脚本无需手动注册。

调试:环境变量 STOCKDB_BUNDLE_SYMBOLS="AAPL,MSFT" 可限定标的做单标的调通。

用法:
    set -a; source .env; set +a
    .venv-zipline/bin/zipline ingest -b stockdb
    .venv-zipline/bin/zipline bundles
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import sqlalchemy as sa
from exchange_calendars.errors import CalendarNameCollision
from zipline.data.bundles import register
from zipline.utils.calendar_utils import register_calendar_alias

BUNDLE_NAME = "stockdb"
EXCHANGE = "STOCKDB"  # 自造交易所名,canonical 指到 XNYS


def _engine() -> sa.Engine:
    url = sa.URL.create(
        "mysql+pymysql",
        username=os.environ.get("DATA_DB_USER", "altas"),
        password=os.environ.get("DATA_DB_PASSWORD", ""),
        host=os.environ.get("DATA_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DATA_DB_PORT", "3306")),
        database=os.environ.get("DATA_DB_NAME", "stockdb"),
        query={"charset": "utf8mb4"},
    )
    return sa.create_engine(url)


def _load_symbols(eng) -> pd.DataFrame:
    df = pd.read_sql(
        sa.text("SELECT id, symbol, full_name FROM symbols ORDER BY symbol"), eng
    )
    only = os.environ.get("STOCKDB_BUNDLE_SYMBOLS")
    if only:
        wanted = {s.strip().upper() for s in only.split(",") if s.strip()}
        df = df[df["symbol"].str.upper().isin(wanted)]
    return df


def _load_prices(eng, symbol_id: int) -> pd.DataFrame:
    df = pd.read_sql(
        sa.text(
            "SELECT traded_at, open, high, low, close, adj_close, volume "
            "FROM daily_prices WHERE symbol_id = :sid ORDER BY traded_at"
        ),
        eng,
        params={"sid": symbol_id},
        parse_dates=["traded_at"],
    ).set_index("traded_at")
    # 该表无唯一约束保证,防重复行(保留最后一条,与增量覆盖语义一致)
    return df[~df.index.duplicated(keep="last")]


def stockdb_bundle(
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
    eng = _engine()
    symbols = _load_symbols(eng)
    if symbols.empty:
        raise ValueError("stockdb.symbols 为空(或 STOCKDB_BUNDLE_SYMBOLS 过滤后无匹配)")

    lo, hi = pd.read_sql(
        sa.text("SELECT MIN(traded_at), MAX(traded_at) FROM daily_prices"), eng
    ).iloc[0]
    start = max(pd.Timestamp(start_session), pd.Timestamp(lo))
    end = min(pd.Timestamp(end_session), pd.Timestamp(hi))
    sessions = calendar.sessions_in_range(start, end)

    meta_rows = []

    def gen():
        for _, row in symbols.iterrows():
            sid = int(row["id"])
            df = _load_prices(eng, sid)
            if df.empty:
                continue
            # 预复权:close ≡ adj_close 口径(缺 adj_close 的行 factor=1 → 用原 close)
            factor = (df["adj_close"] / df["close"]).replace([np.inf, -np.inf], np.nan).fillna(1.0)
            for col in ("open", "high", "low", "close"):
                df[col] = df[col] * factor

            asset_sessions = sessions[(sessions >= df.index[0]) & (sessions <= df.index[-1])]
            if len(asset_sessions) == 0:
                continue
            df = df.reindex(asset_sessions)
            # 开头就缺数的裁掉(首日必须有 close,否则 ffill 也救不回)
            df = df[df["close"].notna().cummax()]
            if df.empty:
                continue
            df["close"] = df["close"].ffill()
            for col in ("open", "high", "low"):
                df[col] = df[col].fillna(df["close"])
            df["volume"] = df["volume"].fillna(0).astype(np.int64)

            meta_rows.append(
                dict(
                    sid=sid,
                    symbol=str(row["symbol"]),
                    asset_name=str(row["full_name"] or row["symbol"]),
                    start_date=df.index[0],
                    end_date=df.index[-1],
                    first_traded=df.index[0],
                    auto_close_date=df.index[-1] + pd.Timedelta(days=1),
                    exchange=EXCHANGE,
                )
            )
            yield sid, df[["open", "high", "low", "close", "volume"]]

    daily_bar_writer.write(gen(), show_progress=show_progress)

    equities = pd.DataFrame(meta_rows).set_index("sid")
    exchanges = pd.DataFrame(
        {"exchange": [EXCHANGE], "canonical_name": ["XNYS"], "country_code": ["US"]}
    )
    asset_db_writer.write(equities=equities, exchanges=exchanges)

    # 复权已烧进价格,adjustment 写空表即可(列名仿 csvdir bundle)
    adjustment_writer.write(
        splits=pd.DataFrame(columns=["sid", "ratio", "effective_date"]),
        dividends=pd.DataFrame(
            columns=["sid", "amount", "ex_date", "record_date", "declared_date", "pay_date"]
        ),
    )


def register_stockdb_bundle() -> None:
    """幂等:同进程重复调用不抛(alias 撞名吞掉;register 本身是 dict 覆盖,天然幂等)。"""
    try:
        register_calendar_alias(EXCHANGE, "XNYS")
    except CalendarNameCollision:
        pass
    register(BUNDLE_NAME, stockdb_bundle, calendar_name="XNYS")
