#!/usr/bin/env python3
"""
Remove symbols that have no Parquet bars: from universe.json and data/assets/.

Usage:
  python scripts/remove_symbols_without_bars.py --dry-run
  python scripts/remove_symbols_without_bars.py
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_PATH = PROJECT_ROOT / "universe.json"
ASSETS_ROOT = PROJECT_ROOT / "data" / "assets"


def get_symbols_without_bars() -> list[str]:
    """Symbols in data/assets/ that have no Parquet bars."""
    out = []
    if not ASSETS_ROOT.exists():
        return out
    for d in ASSETS_ROOT.iterdir():
        if not d.is_dir():
            continue
        bars = d / "bars"
        if not bars.exists():
            out.append(d.name)
            continue
        if not any(bars.iterdir()):
            out.append(d.name)
    return sorted(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    to_remove = get_symbols_without_bars()
    if not to_remove:
        print("No symbols without bars found.")
        return

    print(f"Symbols without Parquet bars: {to_remove}")

    # 1. Remove from universe.json
    with open(UNIVERSE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    remove_set = set(to_remove)
    before = len(data["assets"])
    data["assets"] = [a for a in data["assets"] if a["symbol"] not in remove_set]
    after = len(data["assets"])
    removed_from_universe = before - after
    print(f"Universe: remove {removed_from_universe} (had {before}, now {after})")

    if args.dry_run:
        print("[DRY RUN] Would update universe.json and delete asset dirs.")
        return

    with open(UNIVERSE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("Updated universe.json")

    # 2. Delete data/assets/{symbol} for each
    for sym in to_remove:
        d = ASSETS_ROOT / sym
        if d.exists():
            shutil.rmtree(d)
            print(f"  Deleted: data/assets/{sym}")
    print("Done.")


if __name__ == "__main__":
    main()
