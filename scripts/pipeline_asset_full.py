#!/usr/bin/env python3
"""
Run full pipeline for one asset: backfill(→Parquet) → validate(parquet) → compute(parquet).

Parquet-only. No migrate step. Backfill writes directly to Parquet.

Modes:
- core (default): backfill_asset_full (5 TFs) for core symbols
- daily: backfill_asset_partial (1day, 1week) for daily symbols

Usage:
  python scripts/pipeline_asset_full.py --symbol QQQ
  python scripts/pipeline_asset_full.py --symbol QQQ -t 1day   # 1day only (faster test)
  python scripts/pipeline_asset_full.py --symbol GOOG --mode daily
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Full pipeline: backfill(→Parquet) → validate(parquet) → compute(parquet)"
    )
    ap.add_argument("--symbol", required=True)
    ap.add_argument(
        "--mode",
        choices=["core", "daily"],
        default="core",
        help="core: 5 TFs (backfill_full). daily: 1day+1week (backfill_partial)",
    )
    ap.add_argument("-t", "--timeframe", help="Single TF for compute (e.g. 1day). Default: all")
    ap.add_argument("--skip-ingest", action="store_true", help="Skip bar ingestion (bars already in live.db)")
    args = ap.parse_args()
    symbol = args.symbol.strip().upper()
    tf_arg = ["-t", args.timeframe] if args.timeframe else []
    is_daily = args.mode == "daily"

    if not args.skip_ingest:
        if is_daily:
            print(f"\n>>> python3 scripts/backfill_asset_partial.py --symbol {symbol} --output parquet")
            r = subprocess.run(
                ["python3", "scripts/backfill_asset_partial.py", "--symbol", symbol, "--output", "parquet"],
                cwd=PROJECT_ROOT,
            )
        else:
            print(f"\n>>> python3 scripts/backfill_asset_full.py --symbol {symbol} --output parquet")
            r = subprocess.run(
                ["python3", "scripts/backfill_asset_full.py", "--symbol", symbol, "--output", "parquet"],
                cwd=PROJECT_ROOT,
            )
        if r.returncode != 0:
            sys.exit(r.returncode)
        # Parquet: no live.db check. Backfill writes directly to Parquet.
        bars_dir = PROJECT_ROOT / "data" / "assets" / symbol / "bars"
        if not bars_dir.exists() or not any(bars_dir.iterdir()):
            print(f"[pipeline] No bars written for {symbol}. Skipping validate/compute.")
            return

    steps = [
        ["python3", "scripts/validate_asset_bars.py", "--symbol", symbol, "--input", "parquet"],
        ["python3", "scripts/compute_asset_full.py", "--symbol", symbol, "--input", "parquet"] + tf_arg,
    ]

    for cmd in steps:
        print(f"\n>>> {' '.join(cmd)}")
        r = subprocess.run(cmd, cwd=PROJECT_ROOT)
        if r.returncode != 0:
            sys.exit(r.returncode)

    print("\nPipeline complete. Verify: python scripts/validation_leadtime_spy.py (for SPY)")


if __name__ == "__main__":
    main()
