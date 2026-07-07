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

import functools
import os

import numpy as np
import pandas as pd
import sqlalchemy as sa
from exchange_calendars.errors import CalendarNameCollision
from zipline.data.bundles import register
from zipline.utils.calendar_utils import get_calendar, register_calendar_alias

BUNDLE_NAME = "stockdb"
EXCHANGE = "STOCKDB"  # 自造交易所名,canonical 指到 XNYS

# 港股增量(2026-07-05):独立 bundle `stockdb-hk`,自造交易所名 STOCKDB_HK → canonical XHKG,
# 只收 `%.HK`。与美股 bundle 完全隔离(不同 bundle 名/交易所名/日历),故 US 路径 ingest 不受影响。
BUNDLE_NAME_HK = "stockdb-hk"
EXCHANGE_HK = "STOCKDB_HK"

# ★钉死日历边界(2026-07-07 根治,见 register_* docstring):两个 bundle 的 register 都显式传
# 固定的 start_session / end_session,把 ingest 冻结进 bcolz 元数据的日历起点钉在一个恒定值上,
# 不再随 ingest 当日的滚动日历漂移。数据 2013 起,故 2012 起点安全(会与库内 MIN/MAX(traded_at)
# 取交集,见 _ingest_impl,实际 bar 区间不变)。
PIN_START_SESSION = pd.Timestamp("2012-01-01")
PIN_END_SESSION = pd.Timestamp("2027-12-31")


def _pinned_sessions(calendar_name: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """把 PIN_START/END 夹进当前日历可用区间并**贴到真实交易日**。

    BcolzDailyBarWriter 要求 start/end_session 必须是日历上的真实 session(见
    bcolz_daily_bars.py:__init__ 的 is_session 校验),而 2012-01-01/2027-12-31 多为周末/假日,
    直接传会 ValueError。这里取「≥PIN_START 的首个 session」「≤min(PIN_END, 日历末日) 的末个
    session」——XNYS 与 XHKG 交易日不同,故按各自日历分别贴。贴出的起点(如 2012-01-03)是**恒定**
    的真实 session,与 ingest 当日的滚动日历首日彻底解耦,这正是根治点。"""
    cal = get_calendar(calendar_name)
    start = max(PIN_START_SESSION, cal.first_session)
    end = min(PIN_END_SESSION, cal.last_session)
    sess = cal.sessions_in_range(start, end)
    return sess[0], sess[-1]


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


def _load_symbols(eng, symbol_like: str | None = None) -> pd.DataFrame:
    """symbol_like 给出则加 SQL `symbol LIKE :like` 过滤(如 '%.HK');None=全表(美股原行为)。"""
    sql = "SELECT id, symbol, full_name FROM symbols"
    params: dict = {}
    if symbol_like:
        sql += " WHERE symbol LIKE :like"
        params["like"] = symbol_like
    sql += " ORDER BY symbol"
    df = pd.read_sql(sa.text(sql), eng, params=params)
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
    *,
    exchange: str = EXCHANGE,
    canonical: str = "XNYS",
    country_code: str = "US",
    symbol_like: str | None = None,
):
    """通用 ingest 内核:美股(symbol_like=None/XNYS)与港股(symbol_like='%.HK'/XHKG)共用。

    exchange/canonical/country_code/symbol_like 皆为带默认值的仅关键字参数,默认即原美股行为
    (STOCKDB→XNYS→US,全表),故 register_stockdb_bundle 的产出与泛化前逐字节等价。
    """
    eng = _engine()
    symbols = _load_symbols(eng, symbol_like=symbol_like)
    if symbols.empty:
        raise ValueError(
            f"stockdb.symbols 为空(symbol_like={symbol_like!r},或 STOCKDB_BUNDLE_SYMBOLS 过滤后无匹配)"
        )

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
                    exchange=exchange,
                )
            )
            yield sid, df[["open", "high", "low", "close", "volume"]]

    daily_bar_writer.write(gen(), show_progress=show_progress)

    equities = pd.DataFrame(meta_rows).set_index("sid")
    exchanges = pd.DataFrame(
        {"exchange": [exchange], "canonical_name": [canonical], "country_code": [country_code]}
    )
    asset_db_writer.write(equities=equities, exchanges=exchanges)

    # 复权已烧进价格,adjustment 写空表即可(列名仿 csvdir bundle)
    adjustment_writer.write(
        splits=pd.DataFrame(columns=["sid", "ratio", "effective_date"]),
        dividends=pd.DataFrame(
            columns=["sid", "amount", "ex_date", "record_date", "declared_date", "pay_date"]
        ),
    )


# 美股 ingest 入口:内核默认参数即原行为(STOCKDB/XNYS/US/全表)→ 与泛化前等价。
stockdb_bundle = functools.partial(
    _ingest_impl, exchange=EXCHANGE, canonical="XNYS", country_code="US", symbol_like=None
)

# 港股 ingest 入口:STOCKDB_HK/XHKG/HK,只收 `%.HK`。
stockdb_hk_bundle = functools.partial(
    _ingest_impl, exchange=EXCHANGE_HK, canonical="XHKG", country_code="HK", symbol_like="%.HK"
)


def register_stockdb_bundle() -> None:
    """幂等:同进程重复调用不抛(alias 撞名吞掉;register 本身是 dict 覆盖,天然幂等)。

    ★为什么显式钉 start_session / end_session(2026-07-07 根治):
    zipline ingest 会把「日历 session 边界」冻结进 bcolz 每资产的 first_row/last_row 元数据;
    若 register 不传 start/end,zipline 用 ingest 当日的 `calendar.first_session / last_session`
    (见 zipline/data/bundles/core.py:402-406)。而 exchange_calendars 的默认日历窗口是
    **滚动的** [now−20y, now+1y]。于是 ingest 当日冻结的起点(如 2006-07-05)会随日子推移被
    滚动窗口的新起点(now−20y)越过——某天 `calendar.first_session` > 冻结起点,读 bundle 即抛
    DateOutOfBounds(stockdb-hk 已于 2026-07-06 触发)。钉一个恒定的 start_session=2012-01-01
    (远早于数据首日 2013、又远晚于任何合理的滚动起点),让冻结边界与滚动窗口彻底解耦:只要
    2012-01-01 仍落在滚动窗口内(约到 2032 年前恒成立),读 bundle 永不越界。end_session 若超出
    当日 `calendar.last_session` 会被 core.py 夹到当日值(上界只会随日历增长,不会反向越界,故安全)。
    真实 bar 区间由 _ingest_impl 与库内 MIN/MAX(traded_at) 取交集决定,钉边界不改任何价格数据。
    """
    try:
        register_calendar_alias(EXCHANGE, "XNYS")
    except CalendarNameCollision:
        pass
    start_session, end_session = _pinned_sessions("XNYS")
    register(
        BUNDLE_NAME,
        stockdb_bundle,
        calendar_name="XNYS",
        start_session=start_session,
        end_session=end_session,
    )


def register_stockdb_hk_bundle() -> None:
    """注册港股 bundle `stockdb-hk`(XHKG 日历,只收 %.HK)。幂等,同上。

    同样显式钉 start_session / end_session(见 register_stockdb_bundle docstring 的完整解释):
    stockdb-hk 是 7-06 事故的首个受害者(2026-07-05 ingest 冻结起点 2006-07-05,7-06 起滚动窗口
    起点越过它 → DateOutOfBounds)。钉 2012-01-01 后根治。
    """
    try:
        register_calendar_alias(EXCHANGE_HK, "XHKG")
    except CalendarNameCollision:
        pass
    start_session, end_session = _pinned_sessions("XHKG")
    register(
        BUNDLE_NAME_HK,
        stockdb_hk_bundle,
        calendar_name="XHKG",
        start_session=start_session,
        end_session=end_session,
    )
