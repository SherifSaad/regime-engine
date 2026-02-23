#!/usr/bin/env python3
"""
Full backfill for SPY from Twelve Data to SQLite using earliest_timestamp bounds.

- Uses canonical timeframe keys everywhere: 15min, 1h, 4h, 1day, 1week
- Pages time_series in 5000-bar chunks (order=ASC) starting from a start_date
- Idempotent inserts into bars (PRIMARY KEY symbol,timeframe,ts)
- Updates fetch_cursor progressively

Run:
  python scripts/backfill_spy_full.py
"""

import os
import sqlite3
import time
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

SYMBOL = "SPY"
TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]

TD_EARLIEST_URL = "https://api.twelvedata.com/earliest_timestamp"
TD_TS_URL = "https://api.twelvedata.com/time_series"

OUTPUTSIZE = 5000
OVERLAP_BARS = 5
SLEEP_BETWEEN_CALLS_SEC = 0.2  # gentle pacing

DEFAULT_DB_PATH = "/Users/sherifsaad/Documents/regime-engine/data/regime_cache.db"

def api_key() -> str:
    k = os.getenv("TWELVEDATA_API_KEY", "").strip()
    if not k:
        raise RuntimeError("Missing TWELVEDATA_API_KEY (check .env)")
    return k

def db_path() -> str:
    return os.getenv("REGIME_DB_PATH", DEFAULT_DB_PATH)

def connect(db: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def ensure_cursor_row(conn: sqlite3.Connection, symbol: str, tf: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO fetch_cursor(symbol, timeframe, last_ts) VALUES(?,?,NULL);",
        (symbol, tf),
    )

def get_cursor(conn: sqlite3.Connection, symbol: str, tf: str) -> Optional[str]:
    row = conn.execute(
        "SELECT last_ts FROM fetch_cursor WHERE symbol=? AND timeframe=?;",
        (symbol, tf),
    ).fetchone()
    return row[0] if row else None

def set_cursor(conn: sqlite3.Connection, symbol: str, tf: str, ts: str) -> None:
    conn.execute(
        "UPDATE fetch_cursor SET last_ts=? WHERE symbol=? AND timeframe=?;",
        (ts, symbol, tf),
    )

def get_nth_last_ts(conn: sqlite3.Connection, symbol: str, tf: str, n: int) -> Optional[str]:
    row = conn.execute(
        """
        SELECT ts FROM bars
        WHERE symbol=? AND timeframe=?
        ORDER BY ts DESC
        LIMIT 1 OFFSET ?;
        """,
        (symbol, tf, max(0, n - 1)),
    ).fetchone()
    return row[0] if row else None

def call_earliest(symbol: str, interval: str) -> str:
    params = {"apikey": api_key(), "symbol": symbol, "interval": interval, "format": "JSON"}
    r = requests.get(TD_EARLIEST_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"earliest_timestamp error ({interval}): {data.get('message')}")
    for k in ("datetime", "timestamp", "earliest_timestamp", "date", "value"):
        if isinstance(data, dict) and k in data:
            return str(data[k])
    return str(data)

def call_time_series(symbol: str, interval: str, start_date: Optional[str]) -> List[Dict]:
    params = {
        "apikey": api_key(),
        "symbol": symbol,
        "interval": interval,
        "outputsize": OUTPUTSIZE,
        "order": "ASC",
        "format": "JSON",
        # keep vendor timestamps stable; you can add timezone later if you want
    }
    if start_date:
        params["start_date"] = start_date

    r = requests.get(TD_TS_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"time_series error ({interval}): {data.get('message')} | start_date={start_date}")
    values = data.get("values") if isinstance(data, dict) else None
    return values or []

def to_float(x):
    try:
        return float(x) if x is not None and x != "" else None
    except Exception:
        return None

def insert_values(conn: sqlite3.Connection, symbol: str, tf: str, values: List[Dict]) -> Tuple[int, Optional[str]]:
    inserted = 0
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
            """
            INSERT OR IGNORE INTO bars(symbol, timeframe, ts, open, high, low, close, volume, source)
            VALUES(?,?,?,?,?,?,?,?, 'twelvedata');
            """,
            (symbol, tf, ts, o, h, l, c, vol),
        )
        if cur.rowcount > 0:
            inserted += 1

        if (max_ts is None) or (ts > max_ts):
            max_ts = ts

    return inserted, max_ts

def backfill_timeframe(conn: sqlite3.Connection, symbol: str, tf: str) -> None:
    ensure_cursor_row(conn, symbol, tf)

    earliest = call_earliest(symbol, tf)
    cursor = get_cursor(conn, symbol, tf)

    # If cursor is NULL, we start from earliest.
    # If cursor exists, we are in incremental mode; but for "full backfill"
    # we still ensure we have everything up to cursor by paging forward from earliest
    # ONLY if DB is missing early history.
    # We'll detect missing by checking min(ts) in DB.
    row = conn.execute(
        "SELECT MIN(ts), MAX(ts), COUNT(*) FROM bars WHERE symbol=? AND timeframe=?;",
        (symbol, tf),
    ).fetchone()
    min_ts, max_ts, count = row if row else (None, None, 0)

    print(f"\n[{symbol} {tf}] earliest_vendor={earliest} db_min={min_ts} db_max={max_ts} db_count={count}")

    start = earliest
    # If we already have data and our db_min equals earliest, no need to backfill from earliest;
    # we can just incremental from cursor overlap.
    if min_ts and str(min_ts) <= str(earliest):
        print(f"[{symbol} {tf}] DB already contains earliest vendor history. Skipping full backfill.")
        return

    # Page forward from earliest until the API stops giving full pages.
    page = 0
    prev_max = None
    while True:
        page += 1
        values = call_time_series(symbol, tf, start_date=start)

        if not values:
            print(f"[{symbol} {tf}] page={page} no values returned. STOP.")
            break

        inserted, page_max = insert_values(conn, symbol, tf, values)
        conn.commit()

        # Always advance cursor forward to the max we have
        if page_max:
            set_cursor(conn, symbol, tf, page_max)
            conn.commit()

        print(f"[{symbol} {tf}] page={page} fetched={len(values)} inserted={inserted} start={start} page_max={page_max}")

        # Stop conditions
        if len(values) < OUTPUTSIZE:
            print(f"[{symbol} {tf}] fetched < {OUTPUTSIZE}. Backfill complete.")
            break
        if (prev_max is not None) and (page_max == prev_max):
            print(f"[{symbol} {tf}] page_max did not advance. STOP (safety).")
            break

        prev_max = page_max

        # Advance start to page_max with a small overlap
        # We'll rely on idempotent inserts to avoid duplicates.
        # We overlap by reusing the Nth-last ts currently in DB if available.
        overlap_start = get_nth_last_ts(conn, symbol, tf, OVERLAP_BARS)
        start = overlap_start or page_max

        time.sleep(SLEEP_BETWEEN_CALLS_SEC)

def main():
    db = db_path()
    os.makedirs(os.path.dirname(db), exist_ok=True)
    print("DB:", db)

    with connect(db) as conn:
        for tf in TIMEFRAMES:
            backfill_timeframe(conn, SYMBOL, tf)

    print("\nDONE: SPY full backfill pass complete.")

if __name__ == "__main__":
    main()
