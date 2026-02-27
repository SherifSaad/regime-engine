#!/usr/bin/env python3
"""
Remove all compute outputs so we can run fresh calculations.
Deletes: compute.db, compute.db-shm, compute.db-wal, compute_manifest.json
Keeps: bars/, inventory.json, meta.json

Usage:
  python scripts/clean_compute_for_fresh_run.py --dry-run
  python scripts/clean_compute_for_fresh_run.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS = PROJECT_ROOT / "data" / "assets"

TO_DELETE = ["compute.db", "compute.db-shm", "compute.db-wal", "compute_manifest.json"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    deleted = 0
    for asset_dir in sorted(ASSETS.iterdir()):
        if not asset_dir.is_dir():
            continue
        for name in TO_DELETE:
            f = asset_dir / name
            if f.exists():
                if args.dry_run:
                    print(f"Would delete: {f.relative_to(PROJECT_ROOT)}")
                else:
                    f.unlink()
                    print(f"Deleted: {f.relative_to(PROJECT_ROOT)}")
                deleted += 1

    if args.dry_run:
        print(f"\n[DRY RUN] Would delete {deleted} file(s)")
    else:
        print(f"\nDeleted {deleted} file(s). Ready for fresh compute.")


if __name__ == "__main__":
    main()
