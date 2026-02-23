#!/usr/bin/env python3
"""
Backward gap-fill backfill for SPY using Twelve Data time_series + end_date.

Goal:
Fill missing history between vendor earliest_timestamp and current DB min(ts),
for TFs where vendor returns "most recent N bars" even with start_date.

Canonical TF keys: 15min, 1h, 4h, 1day, 1week
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
SLEEP_SEC = 8.0

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

def set_cursor_max(conn: sqlite3.Connection, symbol: str, tf: str) -> None:
    row = conn.execute(
        "SELECT MAX(ts) FROM bars WHERE symbol=? AND timeframe=?;",
        (symbol, tf),
    ).fetchone()
    max_ts = row[0] if row else None
    if max_ts:
        conn.execute(
            "UPDATE fetch_cursor SET last_ts=? WHERE symbol=? AND timeframe=?;",
            (max_ts, symbol, tf),
        )

def get_db_min_max_count(conn: sqlite3.Connection, symbol: str, tf: str) -> Tuple[Optional[str], Optional[str], int]:
    row = conn.execute(
        "SELECT MIN(ts), MAX(ts), COUNT(*) FROM bars WHERE symbol=? AND timeframe=?;",
        (symbol, tf),
    ).fetchone()
    if not row:
        return None, None, 0
    return row[0], row[1], int(row[2])

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

def call_time_series_backward(symbol: str, interval: str, end_date: str) -> List[Dict]:
    """
    Fetch the most recent OUTPUTSIZE bars ending at end_date.
    We request order=DESC to get newest->oldest; insertion is idempotent anyway.
    """
    params = {
        "apikey": api_key(),
        "symbol": symbol,
        "interval": interval,
        "outputsize": OUTPUTSIZE,
        "order": "DESC",
        "end_date": end_date,
        "format": "JSON",
    }
    r = requests.get(TD_TS_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("status") == "error":
        msg = data.get("message", "")
        if "run out of API credits for the current minute" in msg:
            print(f"[RATE LIMIT] {interval} end_date={end_date} -> sleeping 65s then retry")
            time.sleep(65)
            return call_time_series_backward(symbol, interval, end_date)
        raise RuntimeError(f"time_series error ({interval}): {msg} | end_date={end_date}")
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
            """
            INSERT OR IGNORE INTO bars(symbol, timeframe, ts, open, high, low, close, volume, source)
            VALUES(?,?,?,?,?,?,?,?, 'twelvedata');
            """,
            (symbol, tf, ts, o, h, l, c, vol),
        )
        if cur.rowcount > 0:
            inserted += 1

        if (min_ts is None) or (ts < min_ts):
            min_ts = ts
        if (max_ts is None) or (ts > max_ts):
            max_ts = ts

    return inserted, min_ts, max_ts

def backfill_backward(conn: sqlite3.Connection, symbol: str, tf: str) -> None:
    ensure_cursor_row(conn, symbol, tf)

    vendor_earliest = call_earliest(symbol, tf)
    db_min, db_max, db_count = get_db_min_max_count(conn, symbol, tf)

    print(f"\n[{symbol} {tf}] vendor_earliest={vendor_earliest} db_min={db_min} db_max={db_max} db_count={db_count}")

    if not db_min:
        # If empty, simplest is forward fill later; but for SPY you already have data.
        print(f"[{symbol} {tf}] DB has no data; skip (not expected here).")
        return

    # If we already have full vendor history, stop.
    if str(db_min) <= str(vendor_earliest):
        print(f"[{symbol} {tf}] DB already reaches vendor earliest. Nothing to do.")
        return

    loops = 0
    while str(db_min) > str(vendor_earliest):
        loops += 1

        # Use end_date=db_min so we request bars strictly at/earlier than current earliest we have.
        values = call_time_series_backward(symbol, tf, end_date=db_min)
        if not values:
            print(f"[{symbol} {tf}] No values returned when end_date={db_min}. STOP.")
            break

        inserted, page_min, page_max = insert_values(conn, symbol, tf, values)
        conn.commit()

        new_db_min, new_db_max, new_count = get_db_min_max_count(conn, symbol, tf)
        print(
            f"[{symbol} {tf}] loop={loops} fetched={len(values)} inserted={inserted} "
            f"page_min={page_min} page_max={page_max} -> db_min={new_db_min} count={new_count}"
        )

        # Safety: if we made no progress, stop.
        if new_db_min == db_min:
            print(f"[{symbol} {tf}] db_min did not move. STOP (safety).")
            break

        db_min = new_db_min

        # Gentle pacing to be nice to rate limits
        time.sleep(SLEEP_SEC)

    # Keep cursor aligned to DB max
    set_cursor_max(conn, symbol, tf)
    conn.commit()

def main():
    db = db_path()
    print("DB:", db)
    with connect(db) as conn:
        for tf in TIMEFRAMES:
            backfill_backward(conn, SYMBOL, tf)
    print("\nDONE: backward backfill pass complete.")

if __name__ == "__main__":
    main()
