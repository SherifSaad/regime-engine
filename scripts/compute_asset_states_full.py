#!/usr/bin/env python3
"""
Compute latest_state + state_history for an asset using FULL data (no bar cap).

Uses expanding window df[:i+1] per bar - no lookback limit.
Reads from data/assets/<SYMBOL>/live.db, writes to same DB.

Resumable: skips asofs already in state_history.

Usage:
  python scripts/compute_asset_states_full.py --symbol QQQ
  python scripts/compute_asset_states_full.py --symbol QQQ -t 1day   # 1day only (faster test)
  python scripts/compute_asset_states_full.py --symbol QQQ --all     # all TFs (default)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from regime_engine.cli import compute_market_state_from_df

TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]
MIN_BARS = 200
COMMIT_EVERY = 50


def asset_dir(symbol: str) -> Path:
    return Path("data/assets") / symbol


def live_db_path(symbol: str) -> Path:
    return asset_dir(symbol) / "live.db"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_state_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS latest_state (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            asof TEXT NOT NULL,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (symbol, timeframe)
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS state_history (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            asof TEXT NOT NULL,
            state_json TEXT NOT NULL,
            PRIMARY KEY (symbol, timeframe, asof)
        );
        """
    )
    conn.commit()


def load_bars(conn: sqlite3.Connection, symbol: str, tf: str) -> pd.DataFrame:
    rows = conn.execute(
        """
        SELECT ts, open, high, low, close, volume
        FROM bars
        WHERE symbol=? AND timeframe=?
        ORDER BY ts ASC
        """,
        (symbol, tf),
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts")
    df["adj_close"] = df["close"]
    for c in ["open", "high", "low", "close", "adj_close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close"])
    return df


def existing_asofs(conn: sqlite3.Connection, symbol: str, tf: str) -> set:
    rows = conn.execute(
        "SELECT asof FROM state_history WHERE symbol=? AND timeframe=?",
        (symbol, tf),
    ).fetchall()
    return {r[0] for r in rows}


def insert_state_history(conn: sqlite3.Connection, symbol: str, tf: str, asof: str, state: dict) -> None:
    state_json = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
    conn.execute(
        "INSERT OR IGNORE INTO state_history(symbol,timeframe,asof,state_json) VALUES(?,?,?,?)",
        (symbol, tf, asof, state_json),
    )


def upsert_latest_state(conn: sqlite3.Connection, symbol: str, tf: str, asof: str, state: dict) -> None:
    state_json = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
    updated_at = now_utc_iso()
    conn.execute(
        """
        INSERT INTO latest_state(symbol,timeframe,asof,state_json,updated_at)
        VALUES(?,?,?,?,?)
        ON CONFLICT(symbol,timeframe) DO UPDATE SET
            asof=excluded.asof,
            state_json=excluded.state_json,
            updated_at=excluded.updated_at
        """,
        (symbol, tf, asof, state_json, updated_at),
    )


def compute_one_tf(conn: sqlite3.Connection, symbol: str, tf: str) -> tuple[int, int]:
    df = load_bars(conn, symbol, tf)
    if len(df) < MIN_BARS:
        return 0, 0
    asofs_done = existing_asofs(conn, symbol, tf)
    idx = df.index
    wrote = 0
    skipped = 0
    for i in range(len(df)):
        sub = df.iloc[: i + 1].copy()
        ts = idx[i]
        asof = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        if asof in asofs_done:
            skipped += 1
            continue
        try:
            state = compute_market_state_from_df(
                sub,
                symbol,
                diagnostics=False,
                include_escalation_v2=True,
            )
        except Exception as e:
            print(f"  [WARN] bar {i} asof={asof}: {e}")
            continue
        state["timeframe"] = tf
        insert_state_history(conn, symbol, tf, asof, state)
        upsert_latest_state(conn, symbol, tf, asof, state)
        wrote += 1
        if wrote % COMMIT_EVERY == 0:
            conn.commit()
            print(f"  progress: i={i}/{len(df)} wrote={wrote} skipped={skipped}")
    return wrote, skipped


def main() -> None:
    ap = argparse.ArgumentParser(description="Compute state_history + latest_state (full data, no cap)")
    ap.add_argument("--symbol", required=True, help="e.g. QQQ, SPY")
    ap.add_argument("-t", "--timeframe", help="Single TF (1day, 4h, etc.). Default: all")
    ap.add_argument("--all", action="store_true", help="All TFs (default)")
    args = ap.parse_args()
    symbol = args.symbol.strip().upper()
    tfs = [args.timeframe] if args.timeframe else TIMEFRAMES

    db = live_db_path(symbol)
    if not db.exists():
        raise SystemExit(f"DB not found: {db}. Run backfill_asset_full.py --symbol {symbol} first.")

    conn = sqlite3.connect(str(db), timeout=60)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    ensure_state_tables(conn)

    print(f"[compute_asset_states_full] symbol={symbol} DB={db}")
    total_wrote = 0
    total_skipped = 0
    for tf in tfs:
        print(f"\n--- {tf} ---")
        w, s = compute_one_tf(conn, symbol, tf)
        total_wrote += w
        total_skipped += s
        print(f"  wrote={w} skipped={s}")
    conn.commit()
    conn.close()
    print(f"\nDONE. total wrote={total_wrote} skipped={total_skipped}")


if __name__ == "__main__":
    main()
