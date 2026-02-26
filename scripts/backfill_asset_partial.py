#!/usr/bin/env python3
"""Full backfill for daily symbols: 1day + 1week bars only, into Parquet or live.db.

- Reads assets from universe.json via core.assets_registry.daily_assets()
- Writes to: data/assets/{SYMBOL}/bars/{tf}/ (Parquet, default) or live.db (legacy)
- Timeframes: 1day, 1week only (no 15min, 1h, 4h)
- Full history via paging (5000 per request until earliest)
- 1day: backward paging. 1week: forward paging.

Run:
  python scripts/backfill_asset_partial.py
  python scripts/backfill_asset_partial.py --symbol GOOG
  python scripts/backfill_asset_partial.py --output parquet   # default
  python scripts/backfill_asset_partial.py --output live      # legacy
"""

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import polars as pl
import requests
from dotenv import load_dotenv

from core.assets_registry import daily_assets
from core.manifest import write_bar_manifest
from core.providers.bars_provider import BarsProvider

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TD_EARLIEST_URL = "https://api.twelvedata.com/earliest_timestamp"
TD_TS_URL = "https://api.twelvedata.com/time_series"

TIMEFRAMES = ["1day", "1week"]
# 1day: backward. 1week: forward
BACKWARD_TFS = {"1day"}
OUTPUTSIZE = 5000
OVERLAP_BARS = 5
SLEEP_BETWEEN_CALLS_SEC = 0.2


def api_key() -> str:
    k = os.getenv("TWELVEDATA_API_KEY", "").strip()
    if not k:
        raise RuntimeError("Missing TWELVEDATA_API_KEY (check .env)")
    return k


def td_get(url: str, params: dict, timeout: int = 30, max_retries: int = 10):
    for attempt in range(1, max_retries + 1):
        r = requests.get(url, params=params, timeout=timeout)
        try:
            data = r.json()
        except Exception:
            data = None
        if isinstance(data, dict) and data.get("status") == "error":
            msg = str(data.get("message", ""))
            if "out of API credits for the current minute" in msg:
                time.sleep(65)
                continue
        r.raise_for_status()
        return r
    raise RuntimeError("Twelve Data rate-limit persisted after retries.")


def asset_dir(symbol: str) -> Path:
    return PROJECT_ROOT / "data" / "assets" / symbol


def live_db_path(symbol: str) -> Path:
    return asset_dir(symbol) / "live.db"


def connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bars(
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            ts TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            source TEXT DEFAULT 'twelvedata',
            PRIMARY KEY(symbol, timeframe, ts)
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fetch_cursor(
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            last_ts TEXT,
            PRIMARY KEY(symbol, timeframe)
        );
        """
    )
    conn.commit()


def ensure_cursor_row(conn: sqlite3.Connection, symbol: str, tf: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO fetch_cursor(symbol, timeframe, last_ts) VALUES(?,?,NULL);",
        (symbol, tf),
    )
    conn.commit()


def set_cursor(conn: sqlite3.Connection, symbol: str, tf: str, ts: str) -> None:
    conn.execute(
        "UPDATE fetch_cursor SET last_ts=? WHERE symbol=? AND timeframe=?;",
        (ts, symbol, tf),
    )
    conn.commit()


def db_stats(conn: sqlite3.Connection, symbol: str, tf: str) -> Tuple[Optional[str], Optional[str], int]:
    row = conn.execute(
        "SELECT MIN(ts), MAX(ts), COUNT(*) FROM bars WHERE symbol=? AND timeframe=?;",
        (symbol, tf),
    ).fetchone()
    if not row:
        return None, None, 0
    return row[0], row[1], int(row[2])


def get_nth_last_ts(conn: sqlite3.Connection, symbol: str, tf: str, n: int) -> Optional[str]:
    row = conn.execute(
        "SELECT ts FROM bars WHERE symbol=? AND timeframe=? ORDER BY ts DESC LIMIT 1 OFFSET ?;",
        (symbol, tf, max(0, n - 1)),
    ).fetchone()
    return row[0] if row else None


def get_nth_first_ts(conn: sqlite3.Connection, symbol: str, tf: str, n: int) -> Optional[str]:
    row = conn.execute(
        "SELECT ts FROM bars WHERE symbol=? AND timeframe=? ORDER BY ts ASC LIMIT 1 OFFSET ?;",
        (symbol, tf, max(0, n - 1)),
    ).fetchone()
    return row[0] if row else None


def call_earliest(provider_symbol: str, interval: str) -> str:
    params = {"apikey": api_key(), "symbol": provider_symbol, "interval": interval, "format": "JSON"}
    r = td_get(TD_EARLIEST_URL, params=params, timeout=30)
    data = r.json()
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"earliest_timestamp error ({interval}): {data.get('message')}")
    for k in ("datetime", "timestamp", "earliest_timestamp", "date", "value"):
        if isinstance(data, dict) and k in data:
            return str(data[k])
    return str(data)


def call_time_series(
    provider_symbol: str,
    interval: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    order: str = "ASC",
) -> List[Dict]:
    params = {
        "apikey": api_key(),
        "symbol": provider_symbol,
        "interval": interval,
        "outputsize": OUTPUTSIZE,
        "order": order,
        "format": "JSON",
    }
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    r = td_get(TD_TS_URL, params=params, timeout=30)
    data = r.json()
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"time_series error ({interval}): {data.get('message')}")
    values = data.get("values") if isinstance(data, dict) else None
    return values or []


def to_float(x):
    try:
        return float(x) if x is not None and x != "" else None
    except Exception:
        return None


def insert_values(conn: sqlite3.Connection, symbol: str, tf: str, values: List[Dict]) -> Tuple[int, Optional[str], Optional[str]]:
    inserted = 0
    min_ts = None
    max_ts = None
    cur = conn.cursor()
    for v in values:
        ts = v.get("datetime")
        if not ts:
            continue
        o = to_float(v.get("open"))
        h = to_float(v.get("high"))
        l = to_float(v.get("low"))
        c = to_float(v.get("close"))
        vol = to_float(v.get("volume"))
        cur.execute(
            "INSERT OR IGNORE INTO bars(symbol, timeframe, ts, open, high, low, close, volume, source) VALUES(?,?,?,?,?,?,?,?, 'twelvedata');",
            (symbol, tf, ts, o, h, l, c, vol),
        )
        if cur.rowcount > 0:
            inserted += 1
        if (min_ts is None) or (ts < min_ts):
            min_ts = ts
        if (max_ts is None) or (ts > max_ts):
            max_ts = ts
    conn.commit()
    return inserted, min_ts, max_ts


# ───────────────────────────────────────────────────────────────
# Parquet output path (--output parquet, default)
# ───────────────────────────────────────────────────────────────


def _values_to_df(values: List[Dict]) -> pl.DataFrame:
    rows = []
    for v in values:
        ts = v.get("datetime")
        if not ts:
            continue
        o = to_float(v.get("open"))
        h = to_float(v.get("high"))
        l_ = to_float(v.get("low"))
        c = to_float(v.get("close"))
        vol = to_float(v.get("volume"))
        rows.append({"ts": ts, "open": o or 0, "high": h or 0, "low": l_ or 0, "close": c or 0, "volume": int(vol or 0)})
    if not rows:
        return pl.DataFrame(schema={"ts": pl.String, "open": pl.Float64, "high": pl.Float64, "low": pl.Float64, "close": pl.Float64, "volume": pl.Int64})
    df = pl.DataFrame(rows)
    df = df.with_columns(pl.col("ts").str.to_datetime())
    return df


def write_values_parquet(symbol: str, tf: str, values: List[Dict]) -> Tuple[int, Optional[str], Optional[str]]:
    df = _values_to_df(values)
    if df.is_empty():
        return 0, None, None
    BarsProvider.write_bars(symbol, tf, df)
    min_ts = df["ts"].min()
    max_ts = df["ts"].max()
    return len(df), str(min_ts) if min_ts else None, str(max_ts) if max_ts else None


def parquet_stats(symbol: str, tf: str) -> Tuple[Optional[str], Optional[str], int]:
    df = BarsProvider.get_bars(symbol, tf).collect()
    if df.is_empty():
        return None, None, 0
    return str(df["ts"].min()), str(df["ts"].max()), len(df)


def parquet_get_nth_last_ts(symbol: str, tf: str, n: int) -> Optional[str]:
    df = BarsProvider.get_bars(symbol, tf).collect()
    if df.is_empty() or len(df) < n:
        return None
    row = df.sort("ts", descending=True).row(n - 1, named=True)
    return str(row["ts"]) if row else None


def parquet_get_nth_first_ts(symbol: str, tf: str, n: int) -> Optional[str]:
    df = BarsProvider.get_bars(symbol, tf).collect()
    if df.is_empty() or len(df) < n:
        return None
    row = df.sort("ts").row(n - 1, named=True)
    return str(row["ts"]) if row else None


def backfill_forward_parquet(symbol: str, provider_symbol: str, tf: str, earliest: str) -> None:
    min_ts, max_ts, count = parquet_stats(symbol, tf)
    print(f"\n[{symbol} {tf}] (forward/parquet) earliest={earliest} parquet_min={min_ts} parquet_max={max_ts} count={count}")
    if min_ts and str(min_ts) <= str(earliest):
        print(f"[{symbol} {tf}] Already at earliest. Skip.")
        return
    start = earliest
    page = 0
    prev_max = None
    while True:
        page += 1
        values = call_time_series(provider_symbol, tf, start_date=start, order="ASC")
        if not values:
            break
        inserted, page_min, page_max = write_values_parquet(symbol, tf, values)
        if page_max:
            pass
        print(f"[{symbol} {tf}] page={page} fetched={len(values)} wrote={inserted} page_max={page_max}")
        if len(values) < OUTPUTSIZE:
            break
        if prev_max is not None and page_max == prev_max:
            break
        prev_max = page_max
        overlap_start = parquet_get_nth_last_ts(symbol, tf, OVERLAP_BARS)
        start = overlap_start or page_max
        time.sleep(SLEEP_BETWEEN_CALLS_SEC)


def backfill_backward_parquet(symbol: str, provider_symbol: str, tf: str, earliest: str) -> None:
    min_ts, max_ts, count = parquet_stats(symbol, tf)
    print(f"\n[{symbol} {tf}] (backward/parquet) earliest={earliest} parquet_min={min_ts} parquet_max={max_ts} count={count}")
    if not min_ts:
        values = call_time_series(provider_symbol, tf, order="DESC")
        if not values:
            return
        inserted, page_min, page_max = write_values_parquet(symbol, tf, values)
        min_ts, max_ts, count = parquet_stats(symbol, tf)
        print(f"[{symbol} {tf}] seed fetched={len(values)} wrote={inserted} parquet_min={min_ts} parquet_max={max_ts}")
    if min_ts and str(min_ts) <= str(earliest):
        print(f"[{symbol} {tf}] Already at earliest. Skip.")
        return
    end = min_ts
    page = 0
    prev_min = None
    while True:
        page += 1
        values = call_time_series(provider_symbol, tf, end_date=end, order="DESC")
        if not values:
            break
        inserted, page_min, page_max = write_values_parquet(symbol, tf, values)
        print(f"[{symbol} {tf}] page={page} fetched={len(values)} wrote={inserted} page_min={page_min}")
        if page_min and str(page_min) <= str(earliest):
            break
        if len(values) < OUTPUTSIZE:
            break
        if prev_min is not None and page_min == prev_min:
            break
        prev_min = page_min
        overlap_end = parquet_get_nth_first_ts(symbol, tf, OVERLAP_BARS)
        end = overlap_end or page_min
        min_ts, _, _ = parquet_stats(symbol, tf)
        if min_ts and str(min_ts) <= str(earliest):
            break
        time.sleep(SLEEP_BETWEEN_CALLS_SEC)


def backfill_forward(conn: sqlite3.Connection, symbol: str, provider_symbol: str, tf: str, earliest: str) -> None:
    min_ts, max_ts, count = db_stats(conn, symbol, tf)
    print(f"\n[{symbol} {tf}] (forward) earliest={earliest} db_min={min_ts} db_max={max_ts} count={count}")
    if min_ts and str(min_ts) <= str(earliest):
        print(f"[{symbol} {tf}] Already at earliest. Skip.")
        return
    start = earliest
    page = 0
    prev_max = None
    while True:
        page += 1
        values = call_time_series(provider_symbol, tf, start_date=start, order="ASC")
        if not values:
            break
        inserted, page_min, page_max = insert_values(conn, symbol, tf, values)
        if page_max:
            set_cursor(conn, symbol, tf, page_max)
        print(f"[{symbol} {tf}] page={page} fetched={len(values)} inserted={inserted} page_max={page_max}")
        if len(values) < OUTPUTSIZE:
            break
        if prev_max is not None and page_max == prev_max:
            break
        prev_max = page_max
        overlap_start = get_nth_last_ts(conn, symbol, tf, OVERLAP_BARS)
        start = overlap_start or page_max
        time.sleep(SLEEP_BETWEEN_CALLS_SEC)


def backfill_backward(conn: sqlite3.Connection, symbol: str, provider_symbol: str, tf: str, earliest: str) -> None:
    min_ts, max_ts, count = db_stats(conn, symbol, tf)
    print(f"\n[{symbol} {tf}] (backward) earliest={earliest} db_min={min_ts} db_max={max_ts} count={count}")
    if not min_ts:
        values = call_time_series(provider_symbol, tf, order="DESC")
        if not values:
            return
        insert_values(conn, symbol, tf, values)
        min_ts, max_ts, count = db_stats(conn, symbol, tf)
        print(f"[{symbol} {tf}] seed fetched={len(values)} db_min={min_ts} db_max={max_ts}")
    if min_ts and str(min_ts) <= str(earliest):
        print(f"[{symbol} {tf}] Already at earliest. Skip.")
        return
    end = min_ts
    page = 0
    prev_min = None
    while True:
        page += 1
        values = call_time_series(provider_symbol, tf, end_date=end, order="DESC")
        if not values:
            break
        inserted, page_min, page_max = insert_values(conn, symbol, tf, values)
        if page_max:
            set_cursor(conn, symbol, tf, page_max)
        print(f"[{symbol} {tf}] page={page} fetched={len(values)} inserted={inserted} page_min={page_min}")
        if page_min and str(page_min) <= str(earliest):
            break
        if len(values) < OUTPUTSIZE:
            break
        if prev_min is not None and page_min == prev_min:
            break
        prev_min = page_min
        overlap_end = get_nth_first_ts(conn, symbol, tf, OVERLAP_BARS)
        end = overlap_end or page_min
        min_ts, _, _ = db_stats(conn, symbol, tf)
        if min_ts and str(min_ts) <= str(earliest):
            break
        time.sleep(SLEEP_BETWEEN_CALLS_SEC)


def write_inventory(symbol: str, conn: sqlite3.Connection) -> None:
    inv = {"symbol": symbol, "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "timeframes": {}}
    for tf in TIMEFRAMES:
        mn, mx, ct = db_stats(conn, symbol, tf)
        inv["timeframes"][tf] = {"count": ct, "min_ts": mn, "max_ts": mx}
    out = asset_dir(symbol) / "inventory.json"
    out.write_text(json.dumps(inv, indent=2) + "\n")
    print(f"\nWROTE inventory: {out}")


def write_inventory_parquet(symbol: str) -> None:
    inv = {"symbol": symbol, "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "timeframes": {}}
    for tf in TIMEFRAMES:
        mn, mx, ct = parquet_stats(symbol, tf)
        inv["timeframes"][tf] = {"count": ct, "min_ts": mn, "max_ts": mx}
    out = asset_dir(symbol) / "inventory.json"
    out.write_text(json.dumps(inv, indent=2) + "\n")
    print(f"\nWROTE inventory: {out}")


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Backfill daily symbols (1day + 1week) -> Parquet or live.db")
    ap.add_argument("--symbol", help="Single symbol to backfill (e.g. GOOG). Default: all daily_assets()")
    ap.add_argument(
        "--output",
        choices=["parquet", "live"],
        default="parquet",
        help="Output: parquet (default) or live (legacy)",
    )
    args = ap.parse_args()

    use_parquet = args.output == "parquet"
    out_desc = "Parquet" if use_parquet else "live.db"

    assets = daily_assets()
    if args.symbol:
        sym = args.symbol.strip().upper()
        assets = [a for a in assets if a["symbol"] == sym]
        if not assets:
            assets = [{"symbol": sym, "provider_symbol": sym}]
        print(f"Backfilling 1 daily symbol: {assets[0]['symbol']} (1day + 1week) -> {out_desc}")
    else:
        symbols = [a["symbol"] for a in assets]
        print(f"Backfilling {len(symbols)} daily symbols (1day + 1week) -> {out_desc}")
        print(f"Symbols: {symbols[:15]}{'...' if len(symbols) > 15 else ''}")

    for asset in assets:
        symbol = asset["symbol"]
        provider_symbol = asset.get("provider_symbol") or symbol
        try:
            _ = call_earliest(provider_symbol, TIMEFRAMES[0])
        except (RuntimeError, requests.RequestException) as e:
            print(f"SKIP {symbol}: {str(e)[:80]}")
            continue

        try:
            if use_parquet:
                print("\nOutput: Parquet", asset_dir(symbol) / "bars")
                for tf in TIMEFRAMES:
                    earliest = call_earliest(provider_symbol, tf)
                    if tf in BACKWARD_TFS:
                        backfill_backward_parquet(symbol, provider_symbol, tf, earliest)
                    else:
                        backfill_forward_parquet(symbol, provider_symbol, tf, earliest)
                write_inventory_parquet(symbol)
                write_bar_manifest(symbol)
            else:
                db = live_db_path(symbol)
                print("\nDB:", db)
                conn = connect(db)
                ensure_schema(conn)
                for tf in TIMEFRAMES:
                    ensure_cursor_row(conn, symbol, tf)
                    earliest = call_earliest(provider_symbol, tf)
                    if tf in BACKWARD_TFS:
                        backfill_backward(conn, symbol, provider_symbol, tf, earliest)
                    else:
                        backfill_forward(conn, symbol, provider_symbol, tf, earliest)
                write_inventory(symbol, conn)
                conn.close()
            print(f"\nDONE: {symbol}")
        except (RuntimeError, requests.RequestException) as e:
            print(f"SKIP {symbol}: {str(e)[:80]}")
            if not use_parquet:
                conn.close()


if __name__ == "__main__":
    main()
