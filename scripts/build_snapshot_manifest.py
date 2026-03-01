#!/usr/bin/env python3
"""
Build global snapshot manifest for auditability and reproducibility.

Creates: data/snapshots/manifest_YYYY-MM-DD.json

Enables the claim: "Backtests and displayed metrics refer to snapshot YYYY-MM-DD."

Usage:
  python scripts/build_snapshot_manifest.py
  python scripts/build_snapshot_manifest.py --date 2026-02-27

Run after pipeline completes (e.g. after pipeline_batch_full, or nightly).
Safe to run on Vultr or Mac – reads existing manifests and compute.db only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data"
ASSETS_ROOT = DATA_ROOT / "assets"
SNAPSHOTS_ROOT = DATA_ROOT / "snapshots"


def _get_git_commit() -> str | None:
    """Return current git commit hash, or None if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()[:12]  # Short hash
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _sha256_file(path: Path) -> str | None:
    """Return SHA256 hex digest of file, or None if unreadable."""
    if not path.exists() or not path.is_file():
        return None
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _load_json(path: Path) -> dict | None:
    """Load JSON file, return None if missing or invalid."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def build_snapshot_manifest(snapshot_date: date, include_db_hash: bool = True) -> Path:
    """
    Build data/snapshots/manifest_YYYY-MM-DD.json.

    Includes symbols that have compute.db (i.e. have been computed).
    """
    snapshot_id = snapshot_date.isoformat()
    built_utc = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    code_version = _get_git_commit()

    symbols_data: dict[str, dict] = {}

    if not ASSETS_ROOT.exists():
        SNAPSHOTS_ROOT.mkdir(parents=True, exist_ok=True)
        manifest = {
            "snapshot_id": snapshot_id,
            "built_utc": built_utc,
            "code_version": code_version,
            "symbols": [],
            "symbols_data": {},
        }
        out_path = SNAPSHOTS_ROOT / f"manifest_{snapshot_id}.json"
        out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"[build_snapshot_manifest] No assets found. Wrote empty manifest to {out_path}")
        return out_path

    for symbol_dir in sorted(ASSETS_ROOT.iterdir()):
        if not symbol_dir.is_dir():
            continue
        symbol = symbol_dir.name

        compute_db = symbol_dir / "compute.db"
        if not compute_db.exists():
            continue

        bar_manifest = _load_json(symbol_dir / "manifest.json")
        compute_manifest = _load_json(symbol_dir / "compute_manifest.json")

        timeframes: dict[str, dict] = {}
        if bar_manifest and "timeframes" in bar_manifest:
            for tf, tf_data in bar_manifest["timeframes"].items():
                timeframes[tf] = {
                    "min_ts": tf_data.get("min_ts"),
                    "max_ts": tf_data.get("max_ts"),
                    "bar_count": tf_data.get("count"),
                }

        compute_asof_utc = None
        if compute_manifest:
            compute_asof_utc = compute_manifest.get("asof") or compute_manifest.get("timestamp")

        if compute_asof_utc is None:
            import sqlite3
            try:
                conn = sqlite3.connect(str(compute_db), timeout=5)
                row = conn.execute(
                    "SELECT MAX(asof) FROM escalation_history_v3 WHERE symbol=?",
                    (symbol,),
                ).fetchone()
                conn.close()
                compute_asof_utc = row[0] if row and row[0] else None
            except Exception:
                pass

        symbol_entry: dict = {
            "timeframes": timeframes,
            "compute_asof_utc": compute_asof_utc,
        }
        if include_db_hash:
            h = _sha256_file(compute_db)
            if h:
                symbol_entry["compute_db_sha256"] = h

        symbols_data[symbol] = symbol_entry

    symbols_list = sorted(symbols_data.keys())

    manifest = {
        "snapshot_id": snapshot_id,
        "built_utc": built_utc,
        "code_version": code_version,
        "symbols": symbols_list,
        "symbols_data": symbols_data,
    }

    SNAPSHOTS_ROOT.mkdir(parents=True, exist_ok=True)
    out_path = SNAPSHOTS_ROOT / f"manifest_{snapshot_id}.json"
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"[build_snapshot_manifest] Wrote {out_path} ({len(symbols_list)} symbols)")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build global snapshot manifest for auditability"
    )
    ap.add_argument(
        "--date",
        help="Snapshot date (YYYY-MM-DD). Default: today.",
    )
    ap.add_argument(
        "--no-db-hash",
        action="store_true",
        help="Skip compute_db_sha256 (faster for large datasets)",
    )
    args = ap.parse_args()

    if args.date:
        try:
            snapshot_date = date.fromisoformat(args.date)
        except ValueError:
            print(f"Invalid date: {args.date}", file=sys.stderr)
            sys.exit(1)
    else:
        snapshot_date = date.today()

    build_snapshot_manifest(snapshot_date, include_db_hash=not args.no_db_hash)


if __name__ == "__main__":
    main()
