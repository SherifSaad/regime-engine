#!/usr/bin/env python3
"""
Verify Parquet bars match original live.db after migration.

Checks per symbol/timeframe:
- Row counts match
- Min/max ts match
- No duplicates in either source

Run after migrate_live_to_parquet.py to confirm migration integrity.

Usage:
  python scripts/verify_migration_equivalence.py [--symbol SPY]
  python scripts/verify_migration_equivalence.py --all
"""

import argparse
import sqlite3
import sys
from pathlib import Path

import polars as pl

from core.assets_registry import core_assets, daily_assets
from core.providers.bars_provider import get_bars_path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]


def get_live_stats(symbol: str, tf: str, conn: sqlite3.Connection) -> dict | None:
    """Get count, min_ts, max_ts, duplicates in live.db for symbol/tf."""
    try:
        rows = conn.execute(
            "SELECT ts FROM bars WHERE symbol=? AND timeframe=?",
            (symbol, tf),
        ).fetchall()
    except Exception:
        return None
    if not rows:
        return None
    df = pl.DataFrame({"ts": [r[0] for r in rows]}).with_columns(pl.col("ts").str.to_datetime())
    count = len(df)
    min_ts = df["ts"].min()
    max_ts = df["ts"].max()
    dup_count = count - df["ts"].n_unique()
    return {"count": count, "min_ts": min_ts, "max_ts": max_ts, "duplicates": dup_count}


def get_parquet_stats(symbol: str, tf: str) -> dict | None:
    """Get count, min_ts, max_ts, duplicates in Parquet for symbol/tf."""
    path = get_bars_path(symbol, tf)
    if not path.exists():
        return None
    try:
        lf = pl.scan_parquet(path / "**/*.parquet")
        df = lf.select("ts").collect()
    except Exception:
        return None
    if df.is_empty():
        return None
    count = len(df)
    min_ts = df["ts"].min()
    max_ts = df["ts"].max()
    dup_count = count - df["ts"].n_unique()
    return {"count": count, "min_ts": min_ts, "max_ts": max_ts, "duplicates": dup_count}


def verify_symbol(symbol: str, verbose: bool = False) -> tuple[bool, list[str]]:
    """Verify one symbol. Returns (all_pass, messages)."""
    db_path = PROJECT_ROOT / "data" / "assets" / symbol / "live.db"
    if not db_path.exists():
        return True, [f"SKIP {symbol}: live.db not found (nothing to verify)"]

    conn = sqlite3.connect(str(db_path))
    all_pass = True
    msgs = []

    for tf in TIMEFRAMES:
        live = get_live_stats(symbol, tf, conn)
        parquet = get_parquet_stats(symbol, tf)

        if live is None and parquet is None:
            continue
        if live is None:
            msgs.append(f"  {symbol} {tf}: live.db MISSING, Parquet has {parquet['count']} rows")
            all_pass = False
            continue
        if parquet is None:
            msgs.append(f"  {symbol} {tf}: Parquet MISSING, live.db has {live['count']} rows")
            all_pass = False
            continue

        count_ok = live["count"] == parquet["count"]
        min_ok = live["min_ts"] == parquet["min_ts"]
        max_ok = live["max_ts"] == parquet["max_ts"]
        no_dup_live = live["duplicates"] == 0
        no_dup_parquet = parquet["duplicates"] == 0

        if count_ok and min_ok and max_ok and no_dup_live and no_dup_parquet:
            if verbose:
                msgs.append(f"  {symbol} {tf}: OK (count={live['count']}, ts={live['min_ts']}..{live['max_ts']})")
        else:
            all_pass = False
            parts = []
            if not count_ok:
                parts.append(f"count={live['count']} vs {parquet['count']}")
            if not min_ok:
                parts.append(f"min_ts={live['min_ts']} vs {parquet['min_ts']}")
            if not max_ok:
                parts.append(f"max_ts={live['max_ts']} vs {parquet['max_ts']}")
            if not no_dup_live:
                parts.append(f"live duplicates={live['duplicates']}")
            if not no_dup_parquet:
                parts.append(f"parquet duplicates={parquet['duplicates']}")
            msgs.append(f"  {symbol} {tf}: FAIL ({'; '.join(parts)})")

    conn.close()
    return all_pass, msgs


def main():
    ap = argparse.ArgumentParser(description="Verify Parquet matches live.db after migration")
    ap.add_argument("--symbol", help="Single symbol (e.g. SPY)")
    ap.add_argument("--all", action="store_true", help="Verify all symbols with live.db")
    ap.add_argument("-v", "--verbose", action="store_true", help="Print OK for each tf")
    args = ap.parse_args()

    if args.all:
        core = core_assets()
        daily = daily_assets()
        symbols = list({a["symbol"] for a in core + daily})
        have_db = [s for s in symbols if (PROJECT_ROOT / "data" / "assets" / s / "live.db").exists()]
        print(f"Verifying {len(have_db)} symbols with live.db (of {len(symbols)} total)")
        if not have_db:
            print("No symbols with live.db found.")
            return 0
        any_fail = False
        for symbol in have_db:
            ok, msgs = verify_symbol(symbol, verbose=args.verbose)
            for m in msgs:
                print(m)
            if not ok:
                any_fail = True
        if any_fail:
            print("\nFAIL: Some symbols/timeframes did not match.")
            sys.exit(1)
        print("\nPASS: All Parquet data matches live.db.")
        return 0

    symbol = (args.symbol or "SPY").strip().upper()
    ok, msgs = verify_symbol(symbol, verbose=True)
    for m in msgs:
        print(m)
    if not ok:
        sys.exit(1)
    print("\nPASS: Parquet matches live.db.")


if __name__ == "__main__":
    main()
