#!/usr/bin/env python3
"""
Earnings scheduler – daily/weekly bars for earnings tier symbols.

Single run: fetch daily + weekly bars for all daily_assets(), write to per-asset live.db.
No RTH check – runs once per day (cron) or on demand.

Notes:
- TWELVEDATA_API_KEY required in .env
"""

import os
import sys
import time
import sqlite3
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

from core.assets_registry import daily_assets

# ----------------------------
# Env / Config
# ----------------------------

load_dotenv()

TD_TS_URL = "https://api.twelvedata.com/time_series"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EARNINGS_TIMEFRAMES = ["1day", "1week"]
OVERLAP_BARS = 5
RATE_LIMIT_SLEEP = 65

# ----------------------------
# Helpers
# ----------------------------

def api_key() -> str:
    k = os.getenv("TWELVEDATA_API_KEY", "").strip()
    if not k:
        raise RuntimeError("Missing TWELVEDATA_API_KEY (check .env)")
    return k

def live_db_path(symbol: str) -> Path:
    return PROJECT_ROOT / "data" / "assets" / symbol / "live.db"

def ensure_cursor_row(conn: sqlite3.Connection, symbol: str, tf: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO fetch_cursor(symbol, timeframe, last_ts) VALUES(?,?,NULL);",
        (symbol, tf),
    )

def get_nth_last_ts(conn: sqlite3.Connection, symbol: str, tf: str, n: int) -> Optional[str]:
    row = conn.execute(
        """
        SELECT ts
        FROM bars
        WHERE symbol=? AND timeframe=?
        ORDER BY ts DESC
        LIMIT 1 OFFSET ?;
        """,
        (symbol, tf, max(0, n - 1)),
    ).fetchone()
    return row[0] if row else None

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

def ensure_live_db_schema(conn: sqlite3.Connection) -> None:
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

def td_time_series(symbol: str, interval: str, start_date: Optional[str]) -> List[Dict]:
    params = {
        "apikey": api_key(),
        "symbol": symbol,
        "interval": interval,
        "outputsize": 5000,
        "order": "ASC",
        "format": "JSON",
    }
    if start_date:
        params["start_date"] = start_date

    r = requests.get(TD_TS_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    if isinstance(data, dict) and data.get("status") == "error":
        msg = data.get("message", "")
        if "run out of API credits for the current minute" in msg:
            raise RuntimeError("RATE_LIMIT")
        raise RuntimeError(f"Twelve Data error: {msg}")

    values = data.get("values") if isinstance(data, dict) else None
    return values or []

def to_float(x):
    try:
        return float(x) if x is not None and x != "" else None
    except Exception:
        return None

def insert_bars(conn: sqlite3.Connection, symbol: str, tf: str, values: List[Dict], source: str) -> Tuple[int, Optional[str]]:
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
            VALUES(?,?,?,?,?,?,?,?, ?);
            """,
            (symbol, tf, ts, o, h, l, c, vol, source),
        )
        if cur.rowcount > 0:
            inserted += 1

        if (max_ts is None) or (ts > max_ts):
            max_ts = ts

    return inserted, max_ts

def fetch_earnings_daily_weekly(symbol: str, provider_symbol: str) -> Tuple[int, Optional[str]]:
    """
    Fetch daily + weekly bars for earnings tier. Writes to per-asset live.db.
    Returns (inserted_total, error_msg). error_msg is None on success.
    """
    path = live_db_path(symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    ensure_live_db_schema(conn)

    total = 0
    try:
        for tf in EARNINGS_TIMEFRAMES:
            ensure_cursor_row(conn, symbol, tf)
            start_date = get_nth_last_ts(conn, symbol, tf, OVERLAP_BARS)

            try:
                values = td_time_series(provider_symbol, tf, start_date=start_date)
            except RuntimeError as e:
                if str(e) == "RATE_LIMIT":
                    time.sleep(RATE_LIMIT_SLEEP)
                    values = td_time_series(provider_symbol, tf, start_date=start_date)
                else:
                    raise

            if not values:
                continue

            inserted, _ = insert_bars(conn, symbol, tf, values, source="twelvedata")
            conn.commit()
            set_cursor_max(conn, symbol, tf)
            conn.commit()
            total += inserted
    except Exception as e:
        conn.close()
        return total, str(e)
    conn.close()
    return total, None

# ----------------------------
# Main
# ----------------------------

def main():
    daily_list = daily_assets()
    print(f"Earnings daily run – processing {len(daily_list)} symbols")

    if not daily_list:
        print("No daily/earnings symbols enabled")
        return

    for asset in daily_list:
        symbol = asset["symbol"]
        provider_symbol = asset.get("provider_symbol") or symbol
        try:
            print(f"  Fetching daily/weekly bars for {symbol}")
            inserted, err = fetch_earnings_daily_weekly(symbol, provider_symbol)
            if err:
                print(f"  Error updating {symbol}: {err}")
            else:
                print(f"  Success: updated {symbol} (inserted={inserted})")
        except Exception as e:
            print(f"  Error updating {symbol}: {e}")

    print("Earnings daily run complete")

if __name__ == "__main__":
    main()
