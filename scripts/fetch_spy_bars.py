#!/usr/bin/env python3
"""
Incremental OHLCV ingestion for SPY from Twelve Data into SQLite.

Writes:
- bars(symbol, timeframe, ts, open, high, low, close, volume, source)
- fetch_cursor(symbol, timeframe, last_ts)

Idempotent: bars has PRIMARY KEY (symbol, timeframe, ts).
"""

import os
import sys
import sqlite3
import requests

from dotenv import load_dotenv

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env_path = os.path.join(_project_root, ".env")
if not load_dotenv(_env_path):
    load_dotenv()  # fallback: cwd

from typing import Dict, List, Optional, Tuple

# Add project root for core imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.timeframes import TIMEFRAME_OPTIONS

# ----------------------------
# Config
# ----------------------------

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "regime_cache.db")

# Canonical timeframes = Twelve Data format (15min, 1h, 4h, 1day, 1week)
# Same strings used in DB, UI, and API - no mapping needed.
TIMEFRAMES = TIMEFRAME_OPTIONS

TD_TIME_SERIES_URL = "https://api.twelvedata.com/time_series"

# Recommended for US equities; adjust later if you decide to store exchange-native timestamps differently.
DEFAULT_TZ = "America/New_York"

# When cursor exists, we re-fetch from (cursor - overlap) to be robust to late bars / vendor corrections.
OVERLAP_BARS = 5

# ----------------------------
# Helpers
# ----------------------------

def get_db_path() -> str:
    return os.getenv("REGIME_DB_PATH", DEFAULT_DB_PATH)

def get_api_key() -> str:
    key = os.getenv("TWELVEDATA_API_KEY", "").strip()
    if not key:
        env_path = os.path.join(_project_root, ".env")
        hint = f"Check {env_path} has: TWELVEDATA_API_KEY=your_key"
        raise RuntimeError(f"Missing TWELVEDATA_API_KEY. {hint}")
    return key

def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def ensure_cursor_row(conn: sqlite3.Connection, symbol: str, timeframe: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO fetch_cursor(symbol, timeframe, last_ts) VALUES(?,?,NULL);",
        (symbol, timeframe),
    )

def get_last_ts(conn: sqlite3.Connection, symbol: str, timeframe: str) -> Optional[str]:
    row = conn.execute(
        "SELECT last_ts FROM fetch_cursor WHERE symbol=? AND timeframe=?;",
        (symbol, timeframe),
    ).fetchone()
    if not row:
        return None
    return row[0]

def get_nth_last_ts(conn: sqlite3.Connection, symbol: str, timeframe: str, n: int) -> Optional[str]:
    """
    Return the timestamp of the n-th last bar (n>=1) for overlap refetching.
    If not enough bars exist, returns None.
    """
    row = conn.execute(
        """
        SELECT ts
        FROM bars
        WHERE symbol=? AND timeframe=?
        ORDER BY ts DESC
        LIMIT 1 OFFSET ?;
        """,
        (symbol, timeframe, max(0, n - 1)),
    ).fetchone()
    return row[0] if row else None

def td_time_series(
    api_key: str,
    symbol: str,
    td_interval: str,
    start_ts: Optional[str],
    outputsize: int = 5000,
    timezone: str = DEFAULT_TZ,
) -> List[Dict]:
    """
    Fetch up to outputsize bars from Twelve Data time_series endpoint.
    We request order=ASC so the returned values are oldest->newest.
    """
    params = {
        "apikey": api_key,
        "symbol": symbol,
        "interval": td_interval,
        "outputsize": outputsize,
        "order": "ASC",
        "timezone": timezone,
        "format": "JSON",
    }
    # start_date can be 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS'
    if start_ts:
        params["start_date"] = start_ts

    r = requests.get(TD_TIME_SERIES_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    # Twelve Data errors often come as JSON with "status":"error"
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Twelve Data error: {data.get('message')} | params={params}")

    values = data.get("values") if isinstance(data, dict) else None
    if not values:
        return []
    return values  # list of dicts, each has datetime/open/high/low/close/volume

def insert_bars(
    conn: sqlite3.Connection,
    symbol: str,
    timeframe: str,
    values: List[Dict],
    source: str = "twelvedata",
) -> Tuple[int, Optional[str]]:
    """
    Inserts values into bars table. Returns (inserted_count, max_ts_seen).
    """
    inserted = 0
    max_ts = None

    # Use a transaction for speed
    cur = conn.cursor()
    for v in values:
        ts = v.get("datetime")  # Twelve Data uses "datetime"
        if not ts:
            continue

        # Convert strings safely
        def to_float(x):
            try:
                return float(x) if x is not None and x != "" else None
            except Exception:
                return None

        o = to_float(v.get("open"))
        h = to_float(v.get("high"))
        l = to_float(v.get("low"))
        c = to_float(v.get("close"))
        vol = to_float(v.get("volume"))

        cur.execute(
            """
            INSERT OR IGNORE INTO bars(symbol, timeframe, ts, open, high, low, close, volume, source)
            VALUES(?,?,?,?,?,?,?,?,?);
            """,
            (symbol, timeframe, ts, o, h, l, c, vol, source),
        )

        if cur.rowcount > 0:
            inserted += 1

        if (max_ts is None) or (ts > max_ts):
            max_ts = ts

    return inserted, max_ts

def update_cursor(conn: sqlite3.Connection, symbol: str, timeframe: str, last_ts: str) -> None:
    conn.execute(
        "UPDATE fetch_cursor SET last_ts=? WHERE symbol=? AND timeframe=?;",
        (last_ts, symbol, timeframe),
    )

# ----------------------------
# Main ingestion loop
# ----------------------------

def ingest_symbol_all_timeframes(symbol: str = "SPY") -> int:
    api_key = get_api_key()
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    total_inserted = 0

    with connect(db_path) as conn:
        for tf in TIMEFRAMES:
            ensure_cursor_row(conn, symbol, tf)

            # overlap refetch start
            overlap_start = get_nth_last_ts(conn, symbol, tf, OVERLAP_BARS)
            start_ts = overlap_start or get_last_ts(conn, symbol, tf)

            # Fetch one chunk (max 5000). For SPY-first, this is sufficient.
            # Later (when you want deeper backfills), we can add a loop to walk backwards.
            try:
                values = td_time_series(api_key, symbol, tf, start_ts=start_ts)
            except Exception as e:
                print(f"[{symbol} {tf}] ERROR fetching: {e}", file=sys.stderr)
                continue

            if not values:
                print(f"[{symbol} {tf}] no new data (start_ts={start_ts})")
                continue

            inserted, max_ts = insert_bars(conn, symbol, tf, values)
            conn.commit()

            if max_ts:
                update_cursor(conn, symbol, tf, max_ts)
                conn.commit()

            total_inserted += inserted
            print(f"[{symbol} {tf}] fetched={len(values)} inserted={inserted} cursor={max_ts}")

    return total_inserted

if __name__ == "__main__":
    symbol = "SPY"
    if len(sys.argv) > 1:
        symbol = sys.argv[1].strip().upper()

    n = ingest_symbol_all_timeframes(symbol)
    print(f"\nDONE. Total inserted bars: {n}")
