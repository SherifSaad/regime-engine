#!/usr/bin/env python3
"""
Backfill SPY escalation signals into escalation_history (one-time, run on cloud).

Supports single TF or all TFs: 15min, 1h, 4h, 1day, 1week.

Writes:
(symbol, timeframe, asof, escalation_v2, escalation_bucket)

Usage:
  python scripts/backfill_spy_signals_1day.py              # 1day only (default)
  python scripts/backfill_spy_signals_1day.py --all        # all TFs
  python scripts/backfill_spy_signals_1day.py -t 1h        # specific TF
"""

import argparse
import os
import sqlite3

import numpy as np
import pandas as pd

DB_PATH = os.getenv(
    "REGIME_DB_PATH",
    "/Users/sherifsaad/Documents/regime-engine/data/regime_cache.db",
)

SYMBOL = "SPY"
ALL_TFS = ["15min", "1h", "4h", "1day", "1week"]

# Escalation percentile window (match your v2 design; Cursor suggested 504)
PCTL_WINDOW = 504
MIN_BARS = 400


def ensure_table(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS escalation_history (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            asof TEXT NOT NULL,
            escalation_v2 REAL,
            escalation_bucket TEXT,
            PRIMARY KEY (symbol, timeframe, asof)
        );
        """
    )


def load_bars(conn: sqlite3.Connection, tf: str) -> pd.DataFrame:
    rows = conn.execute(
        """
        SELECT ts, open, high, low, close, volume
        FROM bars
        WHERE symbol=? AND timeframe=?
        ORDER BY ts ASC
        """,
        (SYMBOL, tf),
    ).fetchall()

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts")
    df["adj_close"] = df["close"]

    for c in ["open", "high", "low", "close", "adj_close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close"])
    return df


def _backfill_one_tf(conn: sqlite3.Connection, tf: str) -> int:
    """Backfill one timeframe. Returns number of rows written."""
    df = load_bars(conn, tf)
    print(f"  Bars: {len(df)}")
    if len(df) < MIN_BARS:
        print(f"  Skipped: need >= {MIN_BARS}")
        return 0

    from regime_engine.escalation_buckets import compute_bucket_from_percentile
    from regime_engine.escalation_fast import compute_dsr_iix_ss_arrays_fast
    from regime_engine.escalation_v2 import (
        compute_escalation_v2_series,
        rolling_percentile_transform,
    )
    from regime_engine.features import compute_ema

    dsr_arr, iix_arr, ss_arr = compute_dsr_iix_ss_arrays_fast(df, SYMBOL)
    close_arr = df["close"].iloc[20:].astype(float).values
    ema_arr = compute_ema(df["close"], 100).iloc[20:].astype(float).values

    esc_full = compute_escalation_v2_series(
        dsr_arr, iix_arr, ss_arr, close_arr, ema_arr
    )

    w_max = 12
    n_esc = max(0, len(df) - 31)
    esc_vals = list(esc_full[w_max - 1 : w_max - 1 + n_esc]) if n_esc > 0 else []
    esc_raw = np.concatenate(
        [
            np.full(min(31, len(df)), np.nan, dtype=float),
            np.array(esc_vals, dtype=float),
        ]
    )

    if len(esc_raw) != len(df):
        if len(esc_raw) < len(df):
            esc_raw = np.concatenate([np.full(len(df) - len(esc_raw), np.nan), esc_raw])
        else:
            esc_raw = esc_raw[-len(df) :]

    esc_series = pd.Series(esc_raw, index=df.index)
    pctl = rolling_percentile_transform(esc_series, window=PCTL_WINDOW)

    buckets = []
    for x in pctl.values:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            buckets.append(None)
        else:
            buckets.append(compute_bucket_from_percentile(float(x))[0])

    rows = []
    for ts, ev, bk in zip(df.index, esc_raw, buckets):
        asof = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        rows.append(
            (
                SYMBOL,
                tf,
                asof,
                None if (ev is None or (isinstance(ev, float) and np.isnan(ev))) else float(ev),
                None if bk is None else str(bk),
            )
        )

    conn.executemany(
        """
        INSERT OR REPLACE INTO escalation_history(symbol,timeframe,asof,escalation_v2,escalation_bucket)
        VALUES(?,?,?,?,?);
        """,
        rows,
    )
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Backfill SPY escalation signals")
    parser.add_argument("-t", "--timeframe", default="1day", help="TF to backfill (default: 1day)")
    parser.add_argument("--all", action="store_true", help="Run for all TFs: 15min, 1h, 4h, 1day, 1week")
    args = parser.parse_args()

    tfs = ALL_TFS if args.all else [args.timeframe]

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    ensure_table(conn)

    print("DB:", DB_PATH)
    print("Timeframes:", ", ".join(tfs))

    total = 0
    for tf in tfs:
        print(f"\n--- {tf} ---")
        n = _backfill_one_tf(conn, tf)
        total += n
        if n > 0:
            print(f"  Wrote {n} rows")

    conn.commit()
    conn.close()

    print(f"\nDone. Total rows: {total}")


if __name__ == "__main__":
    main()
