#!/usr/bin/env python3
"""
Compute latest regime state for SPY from SQLite bars, then write:
- latest_state(symbol,timeframe) upsert
- state_history(symbol,timeframe,asof) insert-or-ignore

Assumptions:
- SQLite schema exists (bars, latest_state, state_history)
- Canonical timeframe keys: 15min, 1h, 4h, 1day, 1week
"""

import os
import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv

from regime_engine.cli import compute_market_state_from_df

load_dotenv()

SYMBOL = "SPY"
TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]

DEFAULT_DB_PATH = "/Users/sherifsaad/Documents/regime-engine/data/regime_cache.db"

# How many bars to load for compute (safe default; adjust later per metric requirements)
DEFAULT_LOOKBACK = {
    "15min": 4000,
    "1h": 8000,
    "4h": 4000,
    "1day": 8000,
    "1week": 3000,
}

ENV_LOOKBACK = os.getenv("REGIME_LOOKBACK")
if ENV_LOOKBACK:
    try:
        v = int(ENV_LOOKBACK)
        for k in DEFAULT_LOOKBACK:
            DEFAULT_LOOKBACK[k] = v
    except ValueError:
        pass

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def db_path() -> str:
    return os.getenv("REGIME_DB_PATH", DEFAULT_DB_PATH)

def connect(db: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def load_bars(conn: sqlite3.Connection, symbol: str, tf: str, limit: int) -> pd.DataFrame:
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
    # Convert ts to datetime but keep original string for DB writes
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").reset_index(drop=True)
    return df

def get_latest_asof(conn: sqlite3.Connection, symbol: str, tf: str) -> Optional[str]:
    row = conn.execute(
        "SELECT MAX(ts) FROM bars WHERE symbol=? AND timeframe=?;",
        (symbol, tf),
    ).fetchone()
    return row[0] if row and row[0] else None

# ----------------------------
# Engine hook (ONE PLACE TO ADAPT)
# ----------------------------

def compute_state_from_df(symbol: str, tf: str, df: pd.DataFrame) -> Dict[str, Any]:
    """
    Adapter: SQLite bars -> engine df -> output dict.
    Engine expects a datetime index and uses close/adj_close if present.
    """
    # Ensure datetime index
    df = df.copy()
    if "ts" in df.columns:
        df = df.set_index("ts")
    df.index = pd.to_datetime(df.index)

    # Provide adj_close if missing (engine will prefer it)
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]

    # Ensure required numeric columns
    for c in ["open", "high", "low", "close", "adj_close", "volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=["close"])

    output = compute_market_state_from_df(
        df,
        symbol,
        diagnostics=False,
        include_escalation_v2=True,
    )

    # Add timeframe into payload for convenience (UI + debugging)
    output["timeframe"] = tf

    return output

# ----------------------------
# DB Writers
# ----------------------------

def upsert_latest_state(conn: sqlite3.Connection, symbol: str, tf: str, asof: str, state: Dict[str, Any]) -> None:
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

def insert_state_history(conn: sqlite3.Connection, symbol: str, tf: str, asof: str, state: Dict[str, Any]) -> None:
    state_json = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
    conn.execute(
        """
        INSERT OR IGNORE INTO state_history(symbol,timeframe,asof,state_json)
        VALUES(?,?,?,?);
        """,
        (symbol, tf, asof, state_json),
    )

def main():
    db = db_path()
    print("DB:", db)

    with connect(db) as conn:
        for tf in TIMEFRAMES:
            asof = get_latest_asof(conn, SYMBOL, tf)
            if not asof:
                print(f"[{SYMBOL} {tf}] no bars in DB, skipping")
                continue

            lookback = DEFAULT_LOOKBACK.get(tf, 5000)
            df = load_bars(conn, SYMBOL, tf, lookback)
            if df.empty or len(df) < 200:
                print(f"[{SYMBOL} {tf}] insufficient bars loaded (n={len(df)}), skipping")
                continue

            # Compute
            print(f"[{SYMBOL} {tf}] computing using n={len(df)} bars, asof={asof}")
            state = compute_state_from_df(SYMBOL, tf, df)
            asof = state.get("asof", asof)

            # Persist
            upsert_latest_state(conn, SYMBOL, tf, asof, state)
            insert_state_history(conn, SYMBOL, tf, asof, state)
            conn.commit()

            print(f"[{SYMBOL} {tf}] wrote latest_state + state_history at asof={asof}")

    print("\nDONE. SPY compute pass complete.")

if __name__ == "__main__":
    main()
