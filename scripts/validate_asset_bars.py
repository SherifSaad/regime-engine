#!/usr/bin/env python3
"""
Validate bars in live.db or Parquet before freeze/compute.

Checks:
- bars exist, sufficient count per timeframe
- OHLC sanity (high >= max(open,close), low <= min(open,close), prices > 0)
- No nulls in required fields
- Date ranges (min/max ts per TF)
- Duplicate ts per (symbol, timeframe)
- Gap detection (optional): flag large gaps in ts sequence

Exits 0 if OK, 1 if validation fails.

Usage:
  python scripts/validate_asset_bars.py --symbol QQQ
  python scripts/validate_asset_bars.py --symbol QQQ --input parquet   # default
  python scripts/validate_asset_bars.py --symbol QQQ --input live       # legacy
  python scripts/validate_asset_bars.py --symbol QQQ --check-gaps      # optional gap detection
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import polars as pl

from core.providers.bars_provider import BarsProvider

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]
MIN_BARS_PER_TF = 100

# Expected bar interval in minutes for gap detection (gap > multiplier * expected = flag)
TF_EXPECTED_MINUTES = {"15min": 15, "1h": 60, "4h": 240, "1day": 1440, "1week": 10080}
GAP_MULTIPLIER = 10  # flag if gap > 10x expected interval


def asset_dir(symbol: str) -> Path:
    return PROJECT_ROOT / "data" / "assets" / symbol


def live_db_path(symbol: str) -> Path:
    return asset_dir(symbol) / "live.db"


def _check_gaps_parquet(symbol: str, check_gaps: bool) -> int:
    """Optional gap detection. Flags (warns) large gaps; does not fail validation. Returns 0."""
    if not check_gaps:
        return 0
    flagged = 0
    for tf in TIMEFRAMES:
        lf = BarsProvider.get_bars(symbol, tf)
        df = lf.collect()
        if df.is_empty() or len(df) < 2:
            continue
        df = df.sort("ts").with_columns(
            pl.col("ts").diff().dt.total_minutes().alias("gap_min")
        )
        expected = TF_EXPECTED_MINUTES.get(tf, 60)
        threshold = expected * GAP_MULTIPLIER
        large = df.filter(pl.col("gap_min").is_not_null() & (pl.col("gap_min") > threshold))
        if not large.is_empty():
            n = len(large)
            print(f"[validate] WARN: {tf} has {n} large gap(s) > {threshold} min")
            flagged += 1
    if not flagged and check_gaps:
        print("[validate] OK: no large gaps")
    return 0  # gaps are informational only, do not fail


def validate_parquet(symbol: str, check_gaps: bool = False) -> int:
    """Validate bars from Parquet via BarsProvider. Returns 0 if OK, 1 if errors."""
    errors = 0
    total = 0

    for tf in TIMEFRAMES:
        lf = BarsProvider.get_bars(symbol, tf)
        df = lf.collect()
        n = len(df)
        total += n

        if n == 0:
            print(f"[validate] WARN: {tf} has 0 bars")
            continue

        min_ts = df["ts"].min()
        max_ts = df["ts"].max()
        status = "OK" if n >= MIN_BARS_PER_TF else "WARN"
        print(f"[validate] {tf}: {n} bars, {min_ts} → {max_ts} [{status}]")
        if n < MIN_BARS_PER_TF:
            errors += 1

    # Duplicates per TF
    dup_count = 0
    for tf in TIMEFRAMES:
        lf = BarsProvider.get_bars(symbol, tf)
        df = lf.collect()
        if df.is_empty():
            continue
        dup = df.filter(pl.col("ts").is_duplicated())
        if not dup.is_empty():
            dup_count += len(dup)
    if dup_count:
        print(f"[validate] ERROR: {dup_count} duplicate ts within timeframes")
        errors += 1
    else:
        print("[validate] OK: no duplicate ts")

    # Nulls in OHLC
    null_count = 0
    for tf in TIMEFRAMES:
        lf = BarsProvider.get_bars(symbol, tf)
        df = lf.collect()
        if df.is_empty():
            continue
        nulls = df.filter(
            pl.col("open").is_null()
            | pl.col("high").is_null()
            | pl.col("low").is_null()
            | pl.col("close").is_null()
        )
        if not nulls.is_empty():
            null_count += len(nulls)
            print(f"[validate] ERROR: {tf} has {len(nulls)} rows with null OHLC")
    if null_count:
        errors += 1
    else:
        print("[validate] OK: no null OHLC")

    # OHLC sanity
    bad_count = 0
    for tf in TIMEFRAMES:
        lf = BarsProvider.get_bars(symbol, tf)
        df = lf.collect()
        if df.is_empty():
            continue
        bad = df.filter(
            (pl.col("open") <= 0)
            | (pl.col("high") <= 0)
            | (pl.col("low") <= 0)
            | (pl.col("close") <= 0)
            | (pl.col("high") < pl.col("open"))
            | (pl.col("high") < pl.col("close"))
            | (pl.col("low") > pl.col("open"))
            | (pl.col("low") > pl.col("close"))
            | (pl.col("low") > pl.col("high"))
        )
        if not bad.is_empty():
            bad_count += len(bad)
            print(f"[validate] ERROR: {tf} has {len(bad)} rows with invalid OHLC")
    if bad_count:
        errors += 1
    else:
        print("[validate] OK: OHLC sanity passed")

    # Optional gap detection (informational only, does not fail)
    if check_gaps:
        _check_gaps_parquet(symbol, check_gaps=True)

    print(f"[validate] total bars: {total}")
    if errors:
        print("[validate] FAIL")
    else:
        print("[validate] PASS")
    return 1 if errors else 0


def validate_live(symbol: str, check_gaps: bool = False) -> int:
    """Validate bars from live.db. Returns 0 if OK, 1 if errors. check_gaps ignored for live."""
    """Validate bars from live.db. Returns 0 if OK, 1 if errors."""
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
        if errors:
            print("[validate] FAIL")
        else:
            print("[validate] PASS")

        return 1 if errors else 0
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate bars in live.db or Parquet")
    ap.add_argument("--symbol", required=True, help="e.g. QQQ, SPY")
    ap.add_argument(
        "--input",
        choices=["parquet", "live"],
        default="parquet",
        help="Input source: parquet (default) or live (legacy)",
    )
    ap.add_argument(
        "--check-gaps",
        action="store_true",
        help="Optional: flag large gaps in ts sequence",
    )
    args = ap.parse_args()
    symbol = args.symbol.strip().upper()

    if args.input == "parquet":
        return validate_parquet(symbol, check_gaps=args.check_gaps)
    return validate_live(symbol, check_gaps=args.check_gaps)


if __name__ == "__main__":
    raise SystemExit(main())
