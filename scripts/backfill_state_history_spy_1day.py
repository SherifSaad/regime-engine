#!/usr/bin/env python3
"""
Backfill state_history for SPY 1day across full vendor history (fast enough, resumable).

Strategy:
- Load all SPY 1day bars from DB (already backfilled).
- Compute state only every day using a rolling window of LOOKBACK bars.
- Write to state_history (symbol, timeframe, asof) + keep latest_state updated.
- Resume: skip days already present in state_history.

This is a one-time offline job for validation + research.
"""

import os, json, sqlite3
import pandas as pd
from datetime import datetime, timezone

from regime_engine.cli import compute_market_state_from_df

DB_PATH = os.getenv("REGIME_DB_PATH", "/Users/sherifsaad/Documents/regime-engine/data/regime_cache.db")

SYMBOL = "SPY"
TIMEFRAME = "1day"

LOOKBACK = int(os.getenv("REGIME_LOOKBACK", "2000"))  # reuse your fast setting
MIN_BARS = 400
COMMIT_EVERY = 25  # commit in batches

def now_utc_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def load_bars(conn):
    rows = conn.execute(
        """
        SELECT ts, open, high, low, close, volume
        FROM bars
        WHERE symbol=? AND timeframe=?
        ORDER BY ts ASC
        """,
        (SYMBOL, TIMEFRAME),
    ).fetchall()
    df = pd.DataFrame(rows, columns=["ts","open","high","low","close","volume"])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts")
    df["adj_close"] = df["close"]
    return df

def existing_asofs(conn):
    rows = conn.execute(
        """
        SELECT asof
        FROM state_history
        WHERE symbol=? AND timeframe=?
        """,
        (SYMBOL, TIMEFRAME),
    ).fetchall()
    return set(r[0] for r in rows)

def insert_state_history(conn, asof, state):
    state_json = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
    conn.execute(
        """
        INSERT OR IGNORE INTO state_history(symbol,timeframe,asof,state_json)
        VALUES(?,?,?,?)
        """,
        (SYMBOL, TIMEFRAME, asof, state_json),
    )

def upsert_latest_state(conn, asof, state):
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
        (SYMBOL, TIMEFRAME, asof, state_json, updated_at),
    )

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    bars = load_bars(conn)
    asofs_done = existing_asofs(conn)

    total_days = len(bars)
    wrote = 0
    skipped = 0

    print("DB:", DB_PATH)
    print("Bars:", total_days)
    print("Already in state_history:", len(asofs_done))
    print("LOOKBACK:", LOOKBACK)

    idx = bars.index

    for i in range(total_days):
        asof = idx[i].date().isoformat()

        if asof in asofs_done:
            skipped += 1
            continue

        df_i = bars.iloc[max(0, i - LOOKBACK + 1): i + 1].copy()
        if len(df_i) < MIN_BARS:
            continue

        state = compute_market_state_from_df(
            df_i,
            SYMBOL,
            diagnostics=False,
            include_escalation_v2=True,
        )
        state["timeframe"] = TIMEFRAME

        insert_state_history(conn, asof, state)
        upsert_latest_state(conn, asof, state)

        wrote += 1

        if wrote % COMMIT_EVERY == 0:
            conn.commit()
            print(f"progress: i={i}/{total_days} wrote={wrote} skipped={skipped} asof={asof}")

    conn.commit()
    conn.close()

    print("DONE")
    print("Wrote:", wrote)
    print("Skipped:", skipped)

if __name__ == "__main__":
    main()
