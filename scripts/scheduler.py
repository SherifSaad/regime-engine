#!/usr/bin/env python3
"""
Central Scheduler (Multi-Asset)

DEPRECATED: Use scheduler_core.py (core assets) and scheduler_daily.py
(daily/earnings assets) instead. Those use Parquet + canonical compute → compute.db.
This script uses regime_cache.db (deprecated).

Loop:
  1) For each asset in core.assets_registry.real_time_assets():
       - for each timeframe: if should_poll(symbol, timeframe) is True:
           fetch incremental bars (overlap) -> insert into bars
  2) If ANY new bars inserted for a given symbol -> compute ALL 5 TF states for that symbol
  3) Sleep and repeat

Notes:
- TWELVEDATA_API_KEY required in .env
- REGIME_DB_PATH optional
- REGIME_LOOKBACK optional (default 2000)
"""

import os
import sys
import time
import sqlite3
import requests
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv

from regime_engine.cli import compute_market_state_from_df

from core.assets_registry import real_time_assets, daily_assets, LegacyAsset
from core.asset_class_rules import should_poll

# ----------------------------
# Env / Config
# ----------------------------

load_dotenv()

TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]
TD_TS_URL = "https://api.twelvedata.com/time_series"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = str(PROJECT_ROOT / "data" / "regime_cache.db")

# Earnings tier: daily + weekly only
EARNINGS_TIMEFRAMES = ["1day", "1week"]

# Overlap refetch (idempotent inserts make this safe)
OVERLAP_BARS = 5

# Compute window (fast mode)
DEFAULT_LOOKBACK = int(os.getenv("REGIME_LOOKBACK", "2000"))

# Loop sleep (seconds)
SLEEP_SEC = 30

# Backoff on rate limit
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


def live_db_path(symbol: str) -> Path:
    """Per-asset live.db path (pipeline storage)."""
    return PROJECT_ROOT / "data" / "assets" / symbol / "live.db"


def ensure_live_db_schema(conn: sqlite3.Connection) -> None:
    """Ensure per-asset live.db has bars and fetch_cursor tables."""
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
# Fetch
# ----------------------------

def fetch_incremental_symbol(conn: sqlite3.Connection, symbol: str, vendor_symbol: str) -> Tuple[int, int]:
    """
    Fetch incrementally across TFs for one symbol, but only for TFs where should_poll() is True.
    Returns (inserted_total, polled_count).
    """
    total = 0
    polled = 0
    for tf in TIMEFRAMES:
        if not should_poll(symbol, tf):
            continue

        ensure_cursor_row(conn, symbol, tf)
        start_date = get_nth_last_ts(conn, symbol, tf, OVERLAP_BARS)

        try:
            polled += 1
            values = td_time_series(vendor_symbol, tf, start_date=start_date)
        except RuntimeError as e:
            if str(e) == "RATE_LIMIT":
                print(f"[FETCH] Rate limit hit. Sleeping {RATE_LIMIT_SLEEP}s then retry...")
                time.sleep(RATE_LIMIT_SLEEP)
                polled += 1
                values = td_time_series(vendor_symbol, tf, start_date=start_date)
            else:
                print(f"[FETCH] {symbol} {tf} error: {e}", file=sys.stderr)
                continue

        if not values:
            continue

        inserted, _ = insert_bars(conn, symbol, tf, values, source="twelvedata")
        conn.commit()
        set_cursor_max(conn, symbol, tf)
        conn.commit()

        if inserted > 0:
            print(f"[FETCH] {symbol} {tf}: fetched={len(values)} inserted={inserted}")
        total += inserted

    return total, polled

# ----------------------------
# Compute
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

def compute_and_persist_symbol(conn: sqlite3.Connection, symbol: str, lookback: int) -> None:
    for tf in TIMEFRAMES:
        latest_ts = get_latest_bar_ts(conn, symbol, tf)
        if not latest_ts:
            continue

        df = load_bars_df(conn, symbol, tf, lookback)
        if df.empty or len(df) < 200:
            continue

        df = df.set_index("ts")
        df.index = pd.to_datetime(df.index)

        if "adj_close" not in df.columns:
            df["adj_close"] = df["close"]

        for c in ["open", "high", "low", "close", "adj_close", "volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["close"])

        state = compute_market_state_from_df(
            df,
            symbol,
            diagnostics=False,
            include_escalation_v2=True,
            tf=tf,
        )
        state["timeframe"] = tf

        asof = state.get("asof", latest_ts)

        upsert_latest_state(conn, symbol, tf, asof, state)
        insert_state_history(conn, symbol, tf, asof, state)
        conn.commit()

        print(f"[COMPUTE] {symbol} {tf}: wrote asof={asof}")

# ----------------------------
# Main loop
# ----------------------------

def main():
    db = db_path()
    os.makedirs(os.path.dirname(db), exist_ok=True)

    real_time_list = real_time_assets()
    assets = [LegacyAsset.from_dict(a) for a in real_time_list]
    real_time_symbols = [a["symbol"] for a in real_time_list]
    print("DB:", db)
    print("LOOKBACK:", DEFAULT_LOOKBACK)
    print(f"Scheduler (real-time only): processing {len(real_time_symbols)} symbols: {real_time_symbols}")
    print("TFs:", ", ".join(TIMEFRAMES))
    print("Scheduler starting...\n")

    # Optional init DB
    try:
        from core.storage import init_db  # type: ignore
        init_db()
    except Exception:
        pass

    while True:
        try:
            with connect(db) as conn:
                # Track which symbols got new bars
                changed_symbols: List[str] = []
                total_polled = 0
                total_inserted = 0

                for a in assets:
                    sym = a.symbol.upper()
                    vend = (a.vendor_symbol or a.symbol).upper()

                    inserted, polled = fetch_incremental_symbol(conn, sym, vend)
                    total_polled += polled
                    total_inserted += inserted
                    if inserted > 0:
                        changed_symbols.append(sym)

                # Compute for any symbols that changed
                for sym in changed_symbols:
                    print(f"\n[PIPELINE] {sym} new bars detected -> computing ALL TFs...")
                    compute_and_persist_symbol(conn, sym, DEFAULT_LOOKBACK)

                if not changed_symbols:
                    if total_polled == 0:
                        print(f"[PIPELINE] Session-gated: no TFs polled. Sleeping {SLEEP_SEC}s.\n")
                    else:
                        print(f"[PIPELINE] Polled={total_polled} calls, inserted={total_inserted}. No new bars. Sleeping {SLEEP_SEC}s.\n")
                else:
                    print(f"\n[PIPELINE] Updated symbols: {', '.join(changed_symbols)} | polled={total_polled} inserted={total_inserted}. Sleeping {SLEEP_SEC}s.\n")

            # Isolated earnings/daily tier — failures here never affect real-time
            try:
                daily_list = daily_assets()
                if daily_list:
                    print(f"Starting earnings/daily update for {len(daily_list)} symbols")
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
                    print("Earnings/daily update complete")
                else:
                    print("Skipping earnings/daily – no symbols enabled")
            except Exception as e:
                print(f"ERROR in earnings/daily block: {e}")
                # Do NOT re-raise — real-time path must continue unaffected

            time.sleep(SLEEP_SEC)

        except KeyboardInterrupt:
            print("\nStopping scheduler (Ctrl+C).")
            return
        except Exception as e:
            print(f"[PIPELINE] ERROR: {e}", file=sys.stderr)
            time.sleep(15)

if __name__ == "__main__":
    main()
