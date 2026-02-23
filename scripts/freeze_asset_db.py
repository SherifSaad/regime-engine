#!/usr/bin/env python3
"""
Freeze live.db → frozen_YYYY-MM-DD.db for an asset.

Immutable snapshot for validation. Idempotent: skips if frozen already exists for today.
Checkpoints WAL before copy for consistent snapshot.

Usage:
  python scripts/freeze_asset_db.py --symbol QQQ
  python scripts/freeze_asset_db.py --symbol QQQ --date 2026-02-22
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import date
from pathlib import Path


def asset_dir(symbol: str) -> Path:
    return Path("data/assets") / symbol


def live_db_path(symbol: str) -> Path:
    return asset_dir(symbol) / "live.db"


def frozen_db_path(symbol: str, d: date) -> Path:
    return asset_dir(symbol) / f"frozen_{d.isoformat()}.db"


def main() -> None:
    ap = argparse.ArgumentParser(description="Freeze live.db to frozen_YYYY-MM-DD.db")
    ap.add_argument("--symbol", required=True, help="e.g. QQQ, SPY")
    ap.add_argument("--date", help="Date for frozen file (default: today)")
    args = ap.parse_args()
    symbol = args.symbol.strip().upper()
    d = date.fromisoformat(args.date) if args.date else date.today()

    live = live_db_path(symbol)
    frozen = frozen_db_path(symbol, d)
    if not live.exists():
        raise SystemExit(f"live.db not found: {live}")
    if frozen.exists():
        print(f"[freeze] Already exists: {frozen} (skipping)")
        return
    frozen.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(live))
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    shutil.copy2(live, frozen)
    print(f"[freeze] {live} → {frozen}")


if __name__ == "__main__":
    main()
