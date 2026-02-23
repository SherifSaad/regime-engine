#!/usr/bin/env python3
"""
Run full pipeline for one asset: compute states → backfill escalation v3 → freeze.

Assumes bars already exist in live.db (from backfill_asset_full.py).

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
    ap = argparse.ArgumentParser(description="Full pipeline: compute → escalation v3 → freeze")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("-t", "--timeframe", help="Single TF for compute (e.g. 1day). Default: all")
    args = ap.parse_args()
    symbol = args.symbol.strip().upper()
    tf_arg = ["-t", args.timeframe] if args.timeframe else []

    steps = [
        (["python3", "scripts/compute_asset_states_full.py", "--symbol", symbol] + tf_arg),
        (["python3", "scripts/backfill_escalation_v3.py", "--symbol", symbol]),
        (["python3", "scripts/freeze_asset_db.py", "--symbol", symbol]),
    ]
    for cmd in steps:
        print(f"\n>>> {' '.join(cmd)}")
        r = subprocess.run(cmd, cwd=PROJECT_ROOT)
        if r.returncode != 0:
            sys.exit(r.returncode)
    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
