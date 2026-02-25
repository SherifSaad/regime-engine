#!/usr/bin/env python3
"""
Freeze bars-only snapshot: live.db bars → frozen_YYYY-MM-DD.db.

Frozen DB = raw input only (bars table). No derived tables.
Compute must read frozen, never live. This ensures reproducibility.

Checkpoints WAL before copy for consistent snapshot.

Usage:
  python scripts/freeze_asset_db.py --symbol QQQ
  python scripts/freeze_asset_db.py --symbol QQQ --date 2026-02-22
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def asset_dir(symbol: str) -> Path:
    return PROJECT_ROOT / "data" / "assets" / symbol


def live_db_path(symbol: str) -> Path:
    return asset_dir(symbol) / "live.db"


def frozen_db_path(symbol: str, d: date) -> Path:
    return asset_dir(symbol) / f"frozen_{d.isoformat()}.db"


BARS_SCHEMA = """
CREATE TABLE IF NOT EXISTS bars(
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    ts TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    source TEXT DEFAULT 'twelvedata',
    PRIMARY KEY(symbol, timeframe, ts)
);
"""


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Freeze bars-only snapshot to frozen_YYYY-MM-DD.db"
    )
    ap.add_argument("--symbol", required=True, help="e.g. QQQ, SPY")
    ap.add_argument("--date", help="Date for frozen file (default: today)")
    args = ap.parse_args()
    symbol = args.symbol.strip().upper()
    d = date.fromisoformat(args.date) if args.date else date.today()

    live = live_db_path(symbol)
    frozen = frozen_db_path(symbol, d)
    if not live.exists():
        raise SystemExit(f"live.db not found: {live}")

    frozen.parent.mkdir(parents=True, exist_ok=True)

    conn_live = sqlite3.connect(str(live))
    conn_live.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    conn_frozen = sqlite3.connect(str(frozen))
    conn_frozen.execute(BARS_SCHEMA)

    # Copy bars: read from live, write to frozen (no ATTACH to avoid lock)
    rows = conn_live.execute(
        "SELECT symbol, timeframe, ts, open, high, low, close, volume, COALESCE(source,'twelvedata') FROM bars"
    ).fetchall()
    conn_live.close()

    conn_frozen.executemany(
        "INSERT OR REPLACE INTO bars(symbol,timeframe,ts,open,high,low,close,volume,source) VALUES(?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn_frozen.commit()

    n = conn_frozen.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
    conn_frozen.close()

    print(f"[freeze] bars only ({n} rows): {live} → {frozen}")


if __name__ == "__main__":
    main()
