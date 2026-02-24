#!/usr/bin/env python3
"""
Phase 7 Step 1: Archive old live.db files to data/archive.
Run once to backup SQLite files before Parquet-only migration.
"""
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = PROJECT_ROOT / "data" / "assets"
ARCHIVE_ROOT = PROJECT_ROOT / "data" / "archive"


def main():
    stamp = datetime.now().strftime("%Y%m%d")
    archive_dir = ARCHIVE_ROOT / f"sqlite_backup_{stamp}"
    archive_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    for asset_dir in sorted(ASSETS_ROOT.iterdir()):
        if not asset_dir.is_dir():
            continue
        live_db = asset_dir / "live.db"
        if not live_db.exists():
            continue
        dest_dir = archive_dir / asset_dir.name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "live.db"
        live_db.rename(dest)
        moved += 1
        print(f"Archived {live_db} -> {dest}")

    print(f"Archived {moved} live.db files to {archive_dir}")


if __name__ == "__main__":
    main()
