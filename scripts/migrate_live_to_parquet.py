#!/usr/bin/env python3
"""
Migrate bars from per-asset live.db to Parquet storage.

Reads bars from data/assets/{SYMBOL}/live.db and writes to data/assets/{SYMBOL}/bars/{timeframe}/
as partitioned Parquet (by date).

Usage:
  python scripts/migrate_live_to_parquet.py [--symbol SPY]
  python scripts/migrate_live_to_parquet.py --all   # migrate all core + daily
"""

import argparse
import sqlite3
from pathlib import Path

import polars as pl

from core.assets_registry import core_assets, daily_assets
from core.providers.bars_provider import BarsProvider

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]


def migrate_symbol(symbol: str, quiet: bool = False) -> int:
    """Migrate one symbol's bars from live.db to Parquet. Returns total rows migrated."""
    db_path = PROJECT_ROOT / "data" / "assets" / symbol / "live.db"
    if not db_path.exists():
        if not quiet:
            print(f"SKIP {symbol}: live.db not found")
        return 0

    conn = sqlite3.connect(str(db_path))
    total = 0

    for tf in TIMEFRAMES:
        query = f"""
            SELECT ts, open, high, low, close, volume
            FROM bars
            WHERE symbol = '{symbol}' AND timeframe = '{tf}'
            ORDER BY ts
        """
        try:
            df = pl.read_database(query, conn, schema_overrides={"ts": pl.String})
        except Exception as e:
            print(f"  {symbol} {tf}: read error {e}")
            continue

        if df.is_empty():
            continue

        # Cast ts to Datetime, volume to Int64
        df = df.with_columns(
            pl.col("ts").str.to_datetime(),
            pl.col("volume").cast(pl.Int64),
        )

        BarsProvider.write_bars(symbol, tf, df)
        total += len(df)
        print(f"  {symbol} {tf}: {len(df)} rows")

    conn.close()
    return total


def main():
    ap = argparse.ArgumentParser(description="Migrate live.db bars to Parquet")
    ap.add_argument("--symbol", help="Single symbol to migrate (e.g. SPY)")
    ap.add_argument("--all", action="store_true", help="Migrate all core + daily symbols")
    ap.add_argument("-q", "--quiet", action="store_true", help="Skip symbols without live.db silently")
    args = ap.parse_args()

    if args.all:
        core = core_assets()
        daily = daily_assets()
        symbols = list({a["symbol"] for a in core + daily})
        have_db = [s for s in symbols if (PROJECT_ROOT / "data" / "assets" / s / "live.db").exists()]
        print(f"Migrating: {len(have_db)} symbols with live.db (of {len(symbols)} total)")
        if not have_db:
            print("Run backfill_asset_full (core) or backfill_asset_partial (daily) first.")
            return
        grand_total = 0
        for symbol in have_db:
            try:
                total = migrate_symbol(symbol, quiet=args.quiet)
                grand_total += total
            except Exception as e:
                print(f"Error migrating {symbol}: {e}")
        print(f"Migrated {grand_total} total rows")
    else:
        symbol = (args.symbol or "SPY").strip().upper()
        print(f"Migrating {symbol} bars to Parquet...")
        total = migrate_symbol(symbol)
        print(f"Migrated {symbol} bars to Parquet: {total} rows")


if __name__ == "__main__":
    main()
