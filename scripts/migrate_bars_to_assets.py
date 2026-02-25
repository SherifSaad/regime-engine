#!/usr/bin/env python3
"""
One-time migration: move data/bars/{symbol}/{tf}/ → data/assets/{symbol}/bars/{tf}/

Consolidates to one folder per asset: data/assets/{SYMBOL}/ contains live.db, compute.db,
frozen_*.db, and bars/{timeframe}/*.parquet.

Usage:
  python scripts/migrate_bars_to_assets.py --dry-run   # list moves only
  python scripts/migrate_bars_to_assets.py             # perform migration
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OLD_BARS_ROOT = PROJECT_ROOT / "data" / "bars"
ASSETS_ROOT = PROJECT_ROOT / "data" / "assets"


def main() -> None:
    ap = argparse.ArgumentParser(description="Move data/bars/* to data/assets/*/bars/")
    ap.add_argument("--dry-run", action="store_true", help="List moves only, do not execute")
    args = ap.parse_args()

    if not OLD_BARS_ROOT.exists():
        print(f"No data/bars found at {OLD_BARS_ROOT}. Nothing to migrate.")
        return

    moved = 0
    for symbol_dir in sorted(OLD_BARS_ROOT.iterdir()):
        if not symbol_dir.is_dir() or symbol_dir.name.startswith("."):
            continue

        symbol = symbol_dir.name
        dest_base = ASSETS_ROOT / symbol / "bars"

        for tf_dir in sorted(symbol_dir.iterdir()):
            if not tf_dir.is_dir():
                continue

            tf = tf_dir.name
            dest = dest_base / tf

            parquets = list(tf_dir.glob("**/*.parquet"))
            if not parquets:
                if args.dry_run:
                    print(f"Would skip (empty): {symbol}/{tf}")
                continue

            if args.dry_run:
                print(f"Would move: {symbol_dir}/{tf} → {dest} ({len(parquets)} parquet files)")
                moved += 1
                continue

            dest.mkdir(parents=True, exist_ok=True)

            # Move parquet files (and date partitions)
            for p in tf_dir.rglob("*"):
                if p.is_file() and p.suffix == ".parquet":
                    rel = p.relative_to(tf_dir)
                    dest_file = dest / rel
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(p), str(dest_file))

            # Remove empty dirs in source (bottom-up)
            for d in sorted(tf_dir.rglob("*"), key=lambda x: -len(x.parts)):
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
            if tf_dir.exists() and not any(tf_dir.iterdir()):
                tf_dir.rmdir()

            print(f"Moved: {symbol}/{tf} → {dest}")
            moved += 1

    # Remove empty symbol dirs in old location
    if not args.dry_run:
        for symbol_dir in sorted(OLD_BARS_ROOT.iterdir()):
            if symbol_dir.is_dir() and not any(symbol_dir.iterdir()):
                symbol_dir.rmdir()
                print(f"Removed empty: {symbol_dir}")

    if args.dry_run:
        print(f"\nDry run: would migrate {moved} timeframe folders. Run without --dry-run to apply.")
    else:
        print(f"\nMigrated {moved} timeframe folders to data/assets/*/bars/")

    # Optionally remove data/bars if empty
    if not args.dry_run and OLD_BARS_ROOT.exists() and not any(OLD_BARS_ROOT.iterdir()):
        OLD_BARS_ROOT.rmdir()
        print(f"Removed empty {OLD_BARS_ROOT}")


if __name__ == "__main__":
    main()
