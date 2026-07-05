"""给 stockdb.daily_prices 里零行的标的补日线数据(yfinance → 裸 SQL 插入)。

背景:stockdb.symbols 有 827 行,其中一批标的在 daily_prices 里零行(现有 516 只
覆盖 2013-01-02..2025-12-19)。本脚本把这些空标的用 yfinance 下载后灌进 daily_prices,
供 bundle_stockdb.py 重新 ingest。

—— 关键设计(每条防一种翻车)——

1. 写库凭据(eden)从 Webb-site 的 .env 内联读取,**绝不打印、绝不落盘**:
   该文件是 CRLF,取值必须剥 '\r'。用最小改动读 DB_USER/DB_PASSWORD/DB_HOST/DB_PORT。
   bundle 侧用只读 altas 账号;这里要写,所以用 eden。

2. 表结构与 common.db 的 ORM 不兼容(多一个 NOT NULL 冗余 symbol 列 + 时间戳列),
   故全程裸 SQL,不 import common.db。symbol 列必须填 symbols.symbol 原值。

3. auto_adjust=False:必须同时拿到原始 Close 和 Adj Close,分别存 close / adj_close 两
   列 —— bundle 的复权因子 = adj_close/close,缺一不可。

4. ticker 规范化:daily_prices 里的空标的多是带交易所后缀的国际股(.HK/.T/.DE/.PA/…),
   这些后缀 yfinance **原样需要**,绝不能替换。只有美股 share-class 的点(BRK.B)才替成
   '-'(BRK-B)。因此:识别已知交易所后缀 → 保留;否则整体 '.'→'-'。

5. 幂等:插入前对每个 symbol_id 复核 COUNT(*)==0,>0 直接跳过 —— 无唯一约束,防重复。

6. 不造数据:下载失败/退市/空数据的如实记录跳过,并按 无数据/无效格式 归类。

7. dry-run 默认(只打印将做什么),--execute 才真写。

用法:
    cd /home/eden/code/altas-quant/dissertation
    .venv-zipline/bin/python zipline_lab/backfill_stockdb.py            # dry-run
    .venv-zipline/bin/python zipline_lab/backfill_stockdb.py --execute  # 真灌
"""
from __future__ import annotations

import argparse
import sys
import time

import pandas as pd
import pymysql
import yfinance as yf

ENV_PATH = "/home/eden/code/opensource/webbsite/Webb-site_repository/python/.env"

START = "2013-01-02"
END_INCLUSIVE = "2025-12-19"
END_EXCLUSIVE = "2025-12-20"  # yfinance 的 end 是排他的

# yfinance 原样接受的交易所后缀(不替换点)。不在此列表的点视为 US share-class。
EXCHANGE_SUFFIXES = {
    "HK", "T", "DE", "PA", "AS", "MC", "MI", "BR", "HE", "L", "TO", "SW",
    "SS", "SZ", "KS", "KQ", "TW", "TWO", "AX", "NZ", "SA", "MX", "JO", "IL",
    "VI", "ST", "OL", "CO", "IR", "LS", "WA", "PR", "BD", "AT", "IS", "SI",
    "F", "BE", "HM", "MU", "SG", "DU", "MADRID", "NX",
}


def load_eden_creds() -> dict:
    """从 CRLF 的 .env 内联读 eden 写库凭据。绝不打印。"""
    env = {}
    with open(ENV_PATH, "rb") as f:
        for line in f.read().decode("utf-8").splitlines():
            line = line.strip().replace("\r", "")
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k] = v.strip()
    return {
        "host": env["DB_HOST"],
        "port": int(env.get("DB_PORT") or 3306),
        "user": env["DB_USER"],
        "password": env["DB_PASSWORD"],
        "database": "stockdb",
        "charset": "utf8mb4",
    }


def normalize_ticker(symbol: str) -> str:
    """把 stockdb 的 symbol 转成 yfinance 认的 ticker。

    - 带已知交易所后缀(0700.HK / SAP.DE / 1914.T):后缀保留,只处理根部的点。
    - 无后缀的美股 share-class(BRK.B):整体 '.'→'-' → BRK-B。
    """
    if "." in symbol:
        root, _, suffix = symbol.rpartition(".")
        if suffix.upper() in EXCHANGE_SUFFIXES:
            return root.replace(".", "-") + "." + suffix
    return symbol.replace(".", "-")


def fetch_empty_symbols(conn) -> list[dict]:
    """daily_prices 里零行的 symbol 清单(JOIN symbols)。"""
    cur = conn.cursor()
    cur.execute(
        "SELECT s.id, s.symbol FROM symbols s "
        "LEFT JOIN (SELECT DISTINCT symbol_id FROM daily_prices) d "
        "ON s.id = d.symbol_id WHERE d.symbol_id IS NULL ORDER BY s.symbol"
    )
    return [{"id": r[0], "symbol": r[1]} for r in cur.fetchall()]


def already_has_data(conn, symbol_id: int) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM daily_prices WHERE symbol_id = %s LIMIT 1", (symbol_id,))
    return cur.fetchone() is not None


def download_batch(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """批量下载一组 ticker,返回 {ticker: OHLCV DataFrame}(含 Adj Close)。

    yfinance auto_adjust=False → 同时含 Close 与 Adj Close。空/失败的 ticker 不出现在结果里。
    """
    out: dict[str, pd.DataFrame] = {}
    if not tickers:
        return out
    data = yf.download(
        tickers,
        start=START,
        end=END_EXCLUSIVE,
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    if data is None or data.empty:
        return out
    for t in tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if t not in data.columns.get_level_values(0):
                    continue
                sub = data[t].copy()
            else:
                sub = data.copy()  # 单 ticker 时列不分组
        except (KeyError, IndexError):
            continue
        sub = sub.dropna(how="all")
        if sub.empty or "Close" not in sub.columns:
            continue
        out[t] = sub
    return out


def to_rows(symbol: str, symbol_id: int, df: pd.DataFrame) -> list[tuple]:
    """把 yfinance DataFrame 转成 daily_prices 插入行。close NaN 的行丢弃,不造数据。"""
    rows = []
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    adj_col = "Adj Close" if "Adj Close" in df.columns else "Close"
    for ts, o, h, low, c, ac, v in zip(
        idx, df["Open"], df["High"], df["Low"], df["Close"], df[adj_col], df["Volume"]
    ):
        if pd.isna(c):
            continue

        def f(x):
            return None if pd.isna(x) else float(x)

        vol = 0 if pd.isna(v) else int(v)
        rows.append(
            (
                symbol,
                symbol_id,
                pd.Timestamp(ts).date(),
                f(o), f(h), f(low), f(c), f(ac), vol,
            )
        )
    return rows


INSERT_SQL = (
    "INSERT INTO daily_prices "
    "(symbol, symbol_id, traded_at, open, high, low, close, adj_close, volume) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="真写库(默认 dry-run)")
    ap.add_argument("--batch-size", type=int, default=25, help="每批下载多少 ticker")
    ap.add_argument("--sleep", type=float, default=2.0, help="批间隔秒")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个(调试用)")
    args = ap.parse_args()

    mode = "EXECUTE(真写)" if args.execute else "DRY-RUN(不写库)"
    print(f"=== stockdb backfill [{mode}] 区间 {START}..{END_INCLUSIVE} ===")

    conn = pymysql.connect(**load_eden_creds())
    targets = fetch_empty_symbols(conn)
    if args.limit:
        targets = targets[: args.limit]
    print(f"daily_prices 零行标的:{len(targets)} 个")

    # 幂等:剔除已有数据的(可能上一轮已灌)
    pending = [t for t in targets if not already_has_data(conn, t["id"])]
    skipped_idem = len(targets) - len(pending)
    if skipped_idem:
        print(f"其中 {skipped_idem} 个已有数据(幂等跳过),实际待补 {len(pending)} 个")

    # ticker 映射(yfinance ticker → symbol 记录),同一 yf ticker 可能对应多个 symbol,故用 list
    tmap: dict[str, list[dict]] = {}
    for t in pending:
        yft = normalize_ticker(t["symbol"])
        tmap.setdefault(yft, []).append(t)
    yf_tickers = sorted(tmap)
    renamed = [(t["symbol"], normalize_ticker(t["symbol"]))
               for t in pending if normalize_ticker(t["symbol"]) != t["symbol"]]
    print(f"ticker 规范化改写:{len(renamed)} 个 " +
          (f"(样例 {renamed[:3]})" if renamed else ""))

    # —— 下载(分批 + 间隔),失败的收集后重试一轮 ——
    def run_download(tickers: list[str]) -> dict[str, pd.DataFrame]:
        got: dict[str, pd.DataFrame] = {}
        for i in range(0, len(tickers), args.batch_size):
            batch = tickers[i : i + args.batch_size]
            print(f"  下载 batch {i // args.batch_size + 1} "
                  f"({i + 1}-{min(i + args.batch_size, len(tickers))}/{len(tickers)}) …",
                  flush=True)
            try:
                got.update(download_batch(batch))
            except Exception as e:  # noqa: BLE001
                print(f"    batch 异常:{type(e).__name__}: {e}", flush=True)
            time.sleep(args.sleep)
        return got

    print(f"\n第一轮下载 {len(yf_tickers)} 个 yfinance ticker …")
    fetched = run_download(yf_tickers)
    missing = [t for t in yf_tickers if t not in fetched]
    if missing:
        print(f"\n第一轮缺 {len(missing)} 个,重试一轮 …")
        time.sleep(5)
        fetched.update(run_download(missing))

    # —— 汇总 + 插入 ——
    success, failed = [], []
    total_rows = 0
    cur = conn.cursor()
    for yft in yf_tickers:
        recs = tmap[yft]
        df = fetched.get(yft)
        if df is None or df.empty:
            # 归类:无 '.' 且非纯字母数字常规 → 无效格式;否则无数据(退市/改名/不可用)
            for rec in recs:
                sym = rec["symbol"]
                if any(c.isdigit() for c in sym) and "." not in sym and len(sym) > 12:
                    reason = "无效格式(非合法 ticker)"
                elif sym.count(".") >= 2:
                    reason = "无效格式(多重后缀)"
                else:
                    reason = "无数据(退市/改名/yfinance 不可用)"
                failed.append({"symbol": sym, "yf": yft, "reason": reason})
            continue
        for rec in recs:
            rows = to_rows(rec["symbol"], rec["id"], df)
            if not rows:
                failed.append({"symbol": rec["symbol"], "yf": yft,
                               "reason": "无数据(下载为空)"})
                continue
            # 幂等复核:插入前再确认零行
            if already_has_data(conn, rec["id"]):
                print(f"  {rec['symbol']} 已有数据,跳过(并发/重入保护)")
                continue
            if args.execute:
                cur.executemany(INSERT_SQL, rows)
                conn.commit()
            total_rows += len(rows)
            success.append({"symbol": rec["symbol"], "yf": yft, "rows": len(rows)})
            print(f"  {'写入' if args.execute else '将写入'} {rec['symbol']} "
                  f"({yft}): {len(rows)} 行")

    conn.close()

    # —— 结束汇总 ——
    print("\n" + "=" * 60)
    print(f"成功 {len(success)} / 失败 {len(failed)}  | 插入总行数 {total_rows} "
          f"({'已提交' if args.execute else 'dry-run 未写'})")
    if failed:
        print("\n失败清单(按原因归类):")
        by_reason: dict[str, list[str]] = {}
        for f_ in failed:
            by_reason.setdefault(f_["reason"], []).append(f_["symbol"])
        for reason, syms in sorted(by_reason.items()):
            print(f"  [{reason}] {len(syms)} 个: {', '.join(syms)}")
    if not args.execute:
        print("\n※ 这是 dry-run。确认无误后加 --execute 真灌。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
