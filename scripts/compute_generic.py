#!/usr/bin/env python3
"""
Generic compute script for any symbol.
- Reads ALL bars from frozen DB
- Computes regime state + escalation v3
- Writes to per-symbol compute.db (latest_state, state_history, escalation_history_v3)
"""

import argparse
import os
import sqlite3
import json
from datetime import datetime, timezone
from typing import Dict, Any

import pandas as pd
import numpy as np

# Adjust these imports to match your actual structure
from regime_engine.cli import compute_market_state_from_df
from regime_engine.escalation_v2 import compute_escalation_v2_series, rolling_percentile_transform
from regime_engine.escalation_buckets import compute_bucket_from_percentile   # if you have this

# Constants
TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]
MIN_BARS_FOR_COMPUTE = 200

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def get_frozen_path(symbol: str) -> str:
    # Look for latest frozen_*.db in symbol folder
    folder = f"data/assets/{symbol}"
    if not os.path.exists(folder):
        raise FileNotFoundError(f"Folder not found: {folder}")
    
    frozen_files = [f for f in os.listdir(folder) if f.startswith("frozen_") and f.endswith(".db")]
    if not frozen_files:
        raise FileNotFoundError(f"No frozen_*.db in {folder}")
    
    # Take the latest by name/date
    frozen_files.sort(reverse=True)
    return os.path.join(folder, frozen_files[0])

def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def ensure_tables(conn: sqlite3.Connection):
    """Create/ensure tables if missing (safe to run multiple times)"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS latest_state (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            asof TEXT NOT NULL,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (symbol, timeframe)
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS state_history (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            asof TEXT NOT NULL,
            state_json TEXT NOT NULL,
            PRIMARY KEY (symbol, timeframe, asof)
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS escalation_history_v3 (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            asof TEXT NOT NULL,
            esc_raw REAL,
            esc_pctl REAL,
            esc_bucket TEXT,
            PRIMARY KEY (symbol, timeframe, asof)
        );
    """)

def load_all_bars(conn: sqlite3.Connection, tf: str) -> pd.DataFrame:
    """Load ALL bars for a timeframe (no limit)"""
    rows = conn.execute(
        """
        SELECT ts, open, high, low, close, volume
        FROM bars
        WHERE timeframe = ?
        ORDER BY ts ASC
        """,
        (tf,),
    ).fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts")
    df["adj_close"] = df["close"]  # fallback

    for c in ["open", "high", "low", "close", "adj_close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close"])

    print(f"Loaded {len(df)} bars for {tf}")
    return df

def compute_and_write_one_tf(conn_in, conn_out, symbol: str, tf: str):
    df = load_all_bars(conn_in, tf)
    if df.empty or len(df) < MIN_BARS_FOR_COMPUTE:
        print(f"[{symbol} {tf}] insufficient bars ({len(df)}), skipping")
        return

    # Core computation (your engine hook)
    state = compute_market_state_from_df(
        df,
        symbol,
        diagnostics=False,
        include_escalation_v2=True,
    )
    asof = df.index.max().isoformat()
    state["timeframe"] = tf
    state["schema_version"] = 1   # add your standard
    state["engine_version"] = "1.0"  # or git hash

    # Optional: add escalation series to state if needed
    # But main output is tables below

    state_json = json.dumps(state, separators=(",", ":"), ensure_ascii=False)

    # Write latest_state
    updated_at = now_utc_iso()
    conn_out.execute(
        """
        INSERT OR REPLACE INTO latest_state (symbol, timeframe, asof, state_json, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (symbol, tf, asof, state_json, updated_at),
    )

    # Write state_history
    conn_out.execute(
        """
        INSERT OR IGNORE INTO state_history (symbol, timeframe, asof, state_json)
        VALUES (?, ?, ?, ?)
        """,
        (symbol, tf, asof, state_json),
    )

    # Optional: write escalation_history_v3 if your engine returns series
    # Example (adapt if needed):
    if "escalation_series" in state:
        esc_raw = state["escalation_series"]
        esc_pctl = rolling_percentile_transform(pd.Series(esc_raw), window=504).values
        buckets = [compute_bucket_from_percentile(p) if not np.isnan(p) else None for p in esc_pctl]

        rows = []
        for i, ts in enumerate(df.index):
            if i < len(esc_raw):
                rows.append((
                    symbol,
                    tf,
                    ts.isoformat(),
                    float(esc_raw[i]) if not np.isnan(esc_raw[i]) else None,
                    float(esc_pctl[i]) if not np.isnan(esc_pctl[i]) else None,
                    str(buckets[i]) if buckets[i] else None,
                ))

        conn_out.executemany(
            """
            INSERT OR IGNORE INTO escalation_history_v3
            (symbol, timeframe, asof, esc_raw, esc_pctl, esc_bucket)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    conn_out.commit()
    print(f"[{symbol} {tf}] wrote state & escalation at {asof} (bars: {len(df)})")

def main():
    parser = argparse.ArgumentParser(description="Compute regime state for any symbol (full history)")
    parser.add_argument("--symbol", required=True, help="Symbol to compute (e.g. QQQ)")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    frozen_path = get_frozen_path(symbol)
    output_db = f"data/assets/{symbol}/compute.db"

    print(f"Symbol: {symbol}")
    print(f"Input frozen DB: {frozen_path}")
    print(f"Output DB: {output_db}")

    ensure_tables(sqlite3.connect(output_db))  # ensure tables exist

    with connect(frozen_path) as conn_in, connect(output_db) as conn_out:
        for tf in TIMEFRAMES:
            compute_and_write_one_tf(conn_in, conn_out, symbol, tf)

    print("\nCompute complete.")

if __name__ == "__main__":
    main()