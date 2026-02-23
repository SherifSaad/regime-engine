#!/usr/bin/env python3
"""
SPY centralized scheduler (single-process):

Loop:
  1) Fetch incremental bars for SPY across all TFs (15min, 1h, 4h, 1day, 1week)
  2) If any new bars inserted -> compute ALL 5 TF states and write:
       latest_state + state_history
  3) Sleep and repeat

Notes:
- Uses TWELVEDATA_API_KEY from .env
- Uses REGIME_DB_PATH override if set; otherwise default DB path
- Uses REGIME_LOOKBACK (default 2000) for compute speed
"""

import os
import sys
import time
import sqlite3
import requests
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd

NY_TZ = ZoneInfo("America/New_York")


def should_poll_timeframe(tf: str) -> bool:
    """
    Return True only when a new bar is realistically possible.
    Extremely cheap API optimization.
    """
    now = datetime.now(NY_TZ)

    minute = now.minute
    hour = now.hour
    weekday = now.weekday()  # Monday=0 ... Sunday=6

    # Market closed weekends (skip everything)
    if weekday >= 5:
        return False

    # 15min bars → only on 0,15,30,45
    if tf == "15min":
        return minute % 15 == 0

    # 1h bars → top of hour
    if tf == "1h":
        return minute == 0

    # 4h bars → every 4 hours (approx)
    if tf == "4h":
        return minute == 0 and (hour % 4 == 0)

    # 1day → once after market close (~17:00 NY)
    if tf == "1day":
        return hour == 17 and minute == 0

    # 1week → Friday after close
    if tf == "1week":
        return weekday == 4 and hour == 17 and minute == 0

    return False

from dotenv import load_dotenv

from regime_engine.cli import compute_market_state_from_df  # your real engine entrypoint

# ----------------------------
# Env / Config
# ----------------------------

load_dotenv()

SYMBOL = "SPY"
TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]

TD_TS_URL = "https://api.twelvedata.com/time_series"

DEFAULT_DB_PATH = "/Users/sherifsaad/Documents/regime-engine/data/regime_cache.db"

# Fetch overlap for robustness (vendor corrections / partial last bar)
OVERLAP_BARS = 5

# Compute window (fast mode)
DEFAULT_LOOKBACK = int(os.getenv("REGIME_LOOKBACK", "2000"))

# Scheduler cadence (seconds)
SLEEP_WHEN_NO_NEW = 60
SLEEP_AFTER_SUCCESS = 20

# Backoff if rate limited
RATE_LIMIT_SLEEP = 65

# ----------------------------
# Helpers
# ----------------------------

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

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
        # Rate limit handling
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

def insert_bars(conn: sqlite3.Connection, symbol: str, tf: str, values: List[Dict]) -> Tuple[int, Optional[str]]:
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

def fetch_incremental_all_tfs(conn: sqlite3.Connection, symbol: str) -> int:
    """
    Incremental fetch for all TFs using overlap start.
    Returns total inserted bars across all TFs.
    """
    total_inserted = 0

    for tf in TIMEFRAMES:
        if not should_poll_timeframe(tf):
            continue

        ensure_cursor_row(conn, symbol, tf)

        # overlap start_date: re-fetch a few bars back to be safe
        start_date = get_nth_last_ts(conn, symbol, tf, OVERLAP_BARS)

        try:
            values = td_time_series(symbol, tf, start_date=start_date)
        except RuntimeError as e:
            if str(e) == "RATE_LIMIT":
                print(f"[FETCH] Rate limit hit. Sleeping {RATE_LIMIT_SLEEP}s then retry...")
                time.sleep(RATE_LIMIT_SLEEP)
                values = td_time_series(symbol, tf, start_date=start_date)
            else:
                print(f"[FETCH] {symbol} {tf} error: {e}", file=sys.stderr)
                continue

        if not values:
            print(f"[FETCH] {symbol} {tf}: no new data")
            continue

        inserted, _ = insert_bars(conn, symbol, tf, values)
        conn.commit()

        # cursor should always match DB max
        set_cursor_max(conn, symbol, tf)
        conn.commit()

        total_inserted += inserted
        print(f"[FETCH] {symbol} {tf}: fetched={len(values)} inserted={inserted}")

    return total_inserted

# ----------------------------
# Compute (ALL TFs when any new data arrives)
# ----------------------------

def load_bars_df(conn: sqlite3.Connection, symbol: str, tf: str, limit: int) -> pd.DataFrame:
    rows = conn.execute(
        """
        SELECT ts, open, high, low, close, volume
        FROM bars
        WHERE symbol=? AND timeframe=?
        ORDER BY ts DESC
        LIMIT ?;
        """,
        (symbol, tf, limit),
    ).fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").reset_index(drop=True)
    return df

def get_latest_bar_ts(conn: sqlite3.Connection, symbol: str, tf: str) -> Optional[str]:
    row = conn.execute(
        "SELECT MAX(ts) FROM bars WHERE symbol=? AND timeframe=?;",
        (symbol, tf),
    ).fetchone()
    return row[0] if row and row[0] else None

def upsert_latest_state(conn: sqlite3.Connection, symbol: str, tf: str, asof: str, state: Dict) -> None:
    state_json = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
    updated_at = now_utc_iso()
    conn.execute(
        """
        INSERT INTO latest_state(symbol,timeframe,asof,state_json,updated_at)
        VALUES(?,?,?,?,?)
        ON CONFLICT(symbol,timeframe) DO UPDATE SET
            asof=excluded.asof,
            state_json=excluded.state_json,
            updated_at=excluded.updated_at;
        """,
        (symbol, tf, asof, state_json, updated_at),
    )

def insert_state_history(conn: sqlite3.Connection, symbol: str, tf: str, asof: str, state: Dict) -> None:
    state_json = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
    conn.execute(
        """
        INSERT OR IGNORE INTO state_history(symbol,timeframe,asof,state_json)
        VALUES(?,?,?,?);
        """,
        (symbol, tf, asof, state_json),
    )

def compute_and_persist_all_tfs(conn: sqlite3.Connection, symbol: str, lookback: int) -> None:
    for tf in TIMEFRAMES:
        latest_ts = get_latest_bar_ts(conn, symbol, tf)
        if not latest_ts:
            print(f"[COMPUTE] {symbol} {tf}: no bars, skipping")
            continue

        df = load_bars_df(conn, symbol, tf, lookback)
        if df.empty or len(df) < 200:
            print(f"[COMPUTE] {symbol} {tf}: insufficient bars (n={len(df)}), skipping")
            continue

        # Engine expects datetime index
        df = df.set_index("ts")
        df.index = pd.to_datetime(df.index)

        # Provide adj_close if missing
        if "adj_close" not in df.columns:
            df["adj_close"] = df["close"]

        # Clean numeric
        for c in ["open", "high", "low", "close", "adj_close", "volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["close"])

        state = compute_market_state_from_df(
            df,
            symbol,
            diagnostics=False,
            include_escalation_v2=True,
        )
        state["timeframe"] = tf

        # Prefer engine asof if present (daily/weekly format consistency)
        asof = state.get("asof", latest_ts)

        upsert_latest_state(conn, symbol, tf, asof, state)
        insert_state_history(conn, symbol, tf, asof, state)
        conn.commit()

        print(f"[COMPUTE] {symbol} {tf}: wrote latest_state + history asof={asof}")

# ----------------------------
# Main loop
# ----------------------------

def main():
    db = db_path()
    os.makedirs(os.path.dirname(db), exist_ok=True)

    print("DB:", db)
    print("SYMBOL:", SYMBOL)
    print("LOOKBACK:", DEFAULT_LOOKBACK)
    print("TFs:", ", ".join(TIMEFRAMES))
    print("Scheduler starting...\n")

    # Optional: init DB if available
    try:
        from core.storage import init_db  # type: ignore
        init_db()
    except Exception:
        pass

    while True:
        try:
            with connect(db) as conn:
                inserted = fetch_incremental_all_tfs(conn, SYMBOL)

                if inserted > 0:
                    print(f"\n[PIPELINE] New bars inserted={inserted}. Computing ALL TFs...")
                    compute_and_persist_all_tfs(conn, SYMBOL, DEFAULT_LOOKBACK)
                    print(f"[PIPELINE] Done compute. Sleeping {SLEEP_AFTER_SUCCESS}s.\n")
                    time.sleep(SLEEP_AFTER_SUCCESS)
                else:
                    print(f"[PIPELINE] No new bars. Sleeping {SLEEP_WHEN_NO_NEW}s.\n")
                    time.sleep(SLEEP_WHEN_NO_NEW)

        except KeyboardInterrupt:
            print("\nStopping scheduler (Ctrl+C).")
            return
        except Exception as e:
            print(f"[PIPELINE] ERROR: {e}", file=sys.stderr)
            # avoid crash loops
            time.sleep(15)

if __name__ == "__main__":
    main()
