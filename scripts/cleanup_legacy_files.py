#!/usr/bin/env python3
"""
Remove legacy files no longer used in the Parquet-only pipeline.

Deletes:
- data/regime_cache.db (deprecated; scheduler uses per-asset compute.db)
- data/regime_cache_SPY_escalation_frozen_*.db (legacy validation DBs)
- data/assets/*/live.db (Parquet is canonical)
- data/assets/*/live.db.pre_vultr_merge (old backup)
- data/assets/*/frozen_*.db (+ -shm, -wal)

Keeps: bars/, compute.db, compute_manifest.json, inventory.json, era_metadata

Usage:
  python scripts/cleanup_legacy_files.py --dry-run   # list only
  python scripts/cleanup_legacy_files.py             # delete
"""

from __future__ import annotations

import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = PROJECT_ROOT / "data"
ASSETS = DATA / "assets"


def main() -> None:
    ap = argparse.ArgumentParser(description="Remove legacy frozen/live/regime_cache files")
    ap.add_argument("--dry-run", action="store_true", help="List only, do not delete")
    args = ap.parse_args()

    to_delete: list[Path] = []

    # Root data/
    for name in ["regime_cache.db", "regime_cache_SPY_escalation_frozen_2026-02-19.db"]:
        p = DATA / name
        if p.exists():
            to_delete.append(p)

    # Also any regime_cache_*_frozen*.db
    if DATA.exists():
        for f in DATA.glob("regime_cache_*frozen*.db"):
            to_delete.append(f)

    # Per-asset: live.db, live.db.pre_*, frozen_*.db, frozen_*.db-shm, frozen_*.db-wal
    if ASSETS.exists():
        for asset_dir in ASSETS.iterdir():
            if not asset_dir.is_dir():
                continue
            for f in asset_dir.iterdir():
                if not f.is_file():
                    continue
                name = f.name
                if name == "live.db" or name.startswith("live.db."):
                    to_delete.append(f)
                elif name.startswith("frozen_") and (
                    name.endswith(".db") or name.endswith(".db-shm") or name.endswith(".db-wal")
                ):
                    to_delete.append(f)

    to_delete = list(dict.fromkeys(to_delete))  # dedupe, preserve order

    if not to_delete:
        print("No legacy files found.")
        return

    total_size = sum(f.stat().st_size for f in to_delete if f.exists())
    size_mb = total_size / (1024 * 1024)
    print(f"Found {len(to_delete)} legacy file(s), ~{size_mb:.1f} MB")
    for p in sorted(to_delete):
        try:
            sz = p.stat().st_size / (1024 * 1024)
            print(f"  {p.relative_to(PROJECT_ROOT)} ({sz:.2f} MB)")
        except OSError:
            print(f"  {p.relative_to(PROJECT_ROOT)}")

    if args.dry_run:
        print("\n[DRY RUN] No files deleted. Run without --dry-run to delete.")
        return

    print("\nDeleting...")
    for p in to_delete:
        try:
            p.unlink()
            print(f"  Deleted: {p.relative_to(PROJECT_ROOT)}")
        except OSError as e:
            print(f"  FAILED: {p.relative_to(PROJECT_ROOT)}: {e}")
    print("Done.")


if __name__ == "__main__":
    main()
