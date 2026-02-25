#!/usr/bin/env python3
"""
Validate bars in live.db before freeze.

Checks:
- bars exist, sufficient count per timeframe
- OHLC sanity (high >= max(open,close), low <= min(open,close), prices > 0)
- No nulls in required fields
- Date ranges (min/max ts per TF)
- Duplicate ts per (symbol, timeframe)

Exits 0 if OK, 1 if validation fails.

Usage:
  python scripts/validate_asset_bars.py --symbol QQQ
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]
MIN_BARS_PER_TF = 100


def asset_dir(symbol: str) -> Path:
    return PROJECT_ROOT / "data" / "assets" / symbol


def live_db_path(symbol: str) -> Path:
    return asset_dir(symbol) / "live.db"


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate bars in live.db")
    ap.add_argument("--symbol", required=True, help="e.g. QQQ, SPY")
    args = ap.parse_args()
    symbol = args.symbol.strip().upper()
    db = live_db_path(symbol)

    if not db.exists():
        print(f"[validate] ERROR: live.db not found: {db}")
        return 1

    conn = sqlite3.connect(str(db))
    errors = 0
    try:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='bars'"
        ).fetchone():
            print("[validate] ERROR: bars table not found")
            return 1

        # 1. Counts and date ranges per TF
        for tf in TIMEFRAMES:
            row = conn.execute(
                """
                SELECT COUNT(*), MIN(ts), MAX(ts)
                FROM bars WHERE symbol=? AND timeframe=?
                """,
                (symbol, tf),
            ).fetchone()
            n, min_ts, max_ts = row[0], row[1], row[2]
            if n == 0:
                print(f"[validate] WARN: {tf} has 0 bars")
                continue
            status = "OK" if n >= MIN_BARS_PER_TF else "WARN"
            print(f"[validate] {tf}: {n} bars, {min_ts} → {max_ts} [{status}]")
            if n < MIN_BARS_PER_TF:
                errors += 1

        # 2. Duplicates
        dup = conn.execute(
            """
            SELECT timeframe, ts, COUNT(*) FROM bars
            WHERE symbol=? GROUP BY timeframe, ts HAVING COUNT(*) > 1
            """,
            (symbol,),
        ).fetchall()
        if dup:
            print(f"[validate] ERROR: {len(dup)} duplicate (timeframe, ts) pairs")
            errors += 1
        else:
            print("[validate] OK: no duplicate (timeframe, ts)")

        # 3. Nulls in OHLC
        nulls = conn.execute(
            """
            SELECT timeframe, COUNT(*) FROM bars
            WHERE symbol=? AND (open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL)
            GROUP BY timeframe
            """,
            (symbol,),
        ).fetchall()
        if nulls:
            for tf, c in nulls:
                print(f"[validate] ERROR: {tf} has {c} rows with null OHLC")
            errors += 1
        else:
            print("[validate] OK: no null OHLC")

        # 4. OHLC sanity (high >= max(o,c), low <= min(o,c), prices > 0)
        bad = conn.execute(
            """
            SELECT timeframe, COUNT(*) FROM bars
            WHERE symbol=? AND (
                open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                OR high < open OR high < close
                OR low > open OR low > close
                OR low > high
            )
            GROUP BY timeframe
            """,
            (symbol,),
        ).fetchall()
        if bad:
            for tf, c in bad:
                print(f"[validate] ERROR: {tf} has {c} rows with invalid OHLC")
            errors += 1
        else:
            print("[validate] OK: OHLC sanity passed")

        total = conn.execute(
            "SELECT COUNT(*) FROM bars WHERE symbol=?", (symbol,)
        ).fetchone()[0]
        print(f"[validate] total bars: {total}")

        return 1 if errors else 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
