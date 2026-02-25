#!/usr/bin/env python3
"""
Run full pipeline for one asset: ingest → validate → freeze (bars only) → compute → verify.

Correct order ensures:
- Frozen DB = raw input only (bars)
- Compute reads frozen, never live
- Compute writes to compute.db (reproducible)

Usage:
  python scripts/pipeline_asset_full.py --symbol QQQ
  python scripts/pipeline_asset_full.py --symbol QQQ -t 1day   # 1day only (faster test)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Full pipeline: ingest → validate → freeze (bars only) → compute → verify"
    )
    ap.add_argument("--symbol", required=True)
    ap.add_argument("-t", "--timeframe", help="Single TF for compute (e.g. 1day). Default: all")
    ap.add_argument("--skip-ingest", action="store_true", help="Skip bar ingestion (bars already in live.db)")
    args = ap.parse_args()
    symbol = args.symbol.strip().upper()
    tf_arg = ["-t", args.timeframe] if args.timeframe else []

    live_db = PROJECT_ROOT / "data" / "assets" / symbol / "live.db"

    if not args.skip_ingest:
        print(f"\n>>> python3 scripts/backfill_asset_full.py --symbol {symbol}")
        r = subprocess.run(
            ["python3", "scripts/backfill_asset_full.py", "--symbol", symbol],
            cwd=PROJECT_ROOT,
        )
        if r.returncode != 0:
            sys.exit(r.returncode)
        if not live_db.exists():
            return

    steps = [
        ["python3", "scripts/validate_asset_bars.py", "--symbol", symbol],
        ["python3", "scripts/freeze_asset_db.py", "--symbol", symbol],
        ["python3", "scripts/compute_asset_full.py", "--symbol", symbol, "--input", "frozen"] + tf_arg,
    ]

    for cmd in steps:
        print(f"\n>>> {' '.join(cmd)}")
        r = subprocess.run(cmd, cwd=PROJECT_ROOT)
        if r.returncode != 0:
            sys.exit(r.returncode)

    print("\nPipeline complete. Verify: python scripts/validation_leadtime_spy.py (for SPY)")


if __name__ == "__main__":
    main()
