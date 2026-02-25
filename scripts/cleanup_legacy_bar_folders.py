#!/usr/bin/env python3
"""
Remove legacy bar folders that use non-canonical timeframe names.

Canonical: 15min, 1h, 4h, 1day, 1week
Legacy (to remove if empty): 1d, 1w, 1min, etc.

Usage:
  python scripts/cleanup_legacy_bar_folders.py --dry-run   # list only
  python scripts/cleanup_legacy_bar_folders.py             # remove empty legacy folders
"""

import argparse
from pathlib import Path

from core.timeframes import TIMEFRAMES, normalize_timeframe

ASSETS_ROOT = Path(__file__).resolve().parent.parent / "data" / "assets"
LEGACY_NAMES = {"1d", "1w", "1min"}  # known empty cruft; add others as needed


def is_legacy_folder(name: str) -> bool:
    """True if folder uses non-canonical timeframe name."""
    canonical = normalize_timeframe(name)
    return name != canonical or name in LEGACY_NAMES


def folder_is_empty(path: Path) -> bool:
    """True if folder has no parquet files (or only .DS_Store)."""
    parquets = list(path.glob("**/*.parquet"))
    return len(parquets) == 0


def main():
    ap = argparse.ArgumentParser(description="Remove empty legacy bar folders")
    ap.add_argument("--dry-run", action="store_true", help="List only, do not delete")
    args = ap.parse_args()

    if not ASSETS_ROOT.exists():
        print(f"Assets root not found: {ASSETS_ROOT}")
        return

    removed = 0
    skipped_nonempty = 0

    for symbol_dir in sorted(ASSETS_ROOT.iterdir()):
        if not symbol_dir.is_dir() or symbol_dir.name.startswith("."):
            continue

        bars_dir = symbol_dir / "bars"
        if not bars_dir.exists():
            continue

        for tf_dir in sorted(bars_dir.iterdir()):
            if not tf_dir.is_dir():
                continue

            name = tf_dir.name
            if name in TIMEFRAMES:
                continue  # canonical, keep

            if not is_legacy_folder(name) and name not in LEGACY_NAMES:
                continue  # unknown, leave alone

            if not folder_is_empty(tf_dir):
                print(f"SKIP (has data): {symbol_dir.name}/bars/{name}")
                skipped_nonempty += 1
                continue

            if args.dry_run:
                print(f"Would remove: {symbol_dir.name}/bars/{name}")
            else:
                try:
                    tf_dir.rmdir()
                    print(f"Removed: {symbol_dir.name}/bars/{name}")
                except OSError as e:
                    print(f"Error removing {symbol_dir.name}/bars/{name}: {e}")
                else:
                    removed += 1

    if args.dry_run:
        print(f"\nDry run: would remove empty legacy folders. Run without --dry-run to apply.")
    else:
        print(f"\nRemoved {removed} empty legacy folders. Skipped {skipped_nonempty} with data.")


if __name__ == "__main__":
    main()
