"""
Manifest writers for audit trail and reproducibility.

See docs/SCHEMA_VERSIONS.md and docs/REPRODUCIBILITY.md.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.providers.bars_provider import BarsProvider
from core.schema_versions import COMPUTE_DB_SCHEMA_VERSION

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_bar_manifest(symbol: str) -> Path:
    """
    Write data/assets/{SYMBOL}/manifest.json.
    Include: symbol, timeframes (counts, min/max ts), timestamp.
    """
    asset_dir = PROJECT_ROOT / "data" / "assets" / symbol
    manifest_path = asset_dir / "manifest.json"

    timeframes: dict[str, dict[str, Any]] = {}
    for tf in TIMEFRAMES:
        df = BarsProvider.get_bars(symbol, tf).collect()
        if df.is_empty():
            continue
        n = len(df)
        min_ts = df["ts"].min()
        max_ts = df["ts"].max()
        timeframes[tf] = {
            "count": n,
            "min_ts": str(min_ts) if min_ts else None,
            "max_ts": str(max_ts) if max_ts else None,
        }

    manifest = {
        "symbol": symbol,
        "timeframes": timeframes,
        "timestamp": _now_utc_iso(),
    }
    asset_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest_path


def write_compute_manifest(
    symbol: str,
    bar_count_used: int,
    asof: str | None = None,
    compute_db_path: Path | None = None,
) -> Path:
    """
    Write data/assets/{SYMBOL}/compute_manifest.json.
    Include: symbol, asof, bar_count_used, schema_version, timestamp.
    """
    asset_dir = PROJECT_ROOT / "data" / "assets" / symbol
    manifest_path = asset_dir / "compute_manifest.json"

    if asof is None and compute_db_path:
        conn = sqlite3.connect(str(compute_db_path))
        row = conn.execute(
            "SELECT MAX(asof) FROM escalation_history_v3 WHERE symbol=?",
            (symbol,),
        ).fetchone()
        conn.close()
        asof = row[0] if row and row[0] else None

    manifest = {
        "symbol": symbol,
        "asof": asof,
        "bar_count_used": bar_count_used,
        "schema_version": COMPUTE_DB_SCHEMA_VERSION,
        "timestamp": _now_utc_iso(),
    }
    asset_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest_path
