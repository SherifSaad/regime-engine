#!/usr/bin/env python3
"""
Builds a dynamic registry for the UI/API by scanning data/assets/*.

Outputs:
- data/index/registry.json  (asset list + types + available timeframes + freshness)
- data/index/stats.json     (landing-page stats computed from real DBs)

Design goals:
- NO hardcoded asset types, assets, timeframes, metric names, or "calculations".
- Everything derived from: meta.json, inventory.json, and DB introspection.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = REPO_ROOT / "data" / "assets"
INDEX_DIR = REPO_ROOT / "data" / "index"
INDEX_DIR.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def sqlite_table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,)
    )
    return cur.fetchone() is not None


def sqlite_get_tables(conn: sqlite3.Connection) -> List[str]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [r[0] for r in cur.fetchall()]


def sqlite_count_rows(conn: sqlite3.Connection, table: str) -> Optional[int]:
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(1) FROM {table}")
        return int(cur.fetchone()[0])
    except Exception:
        return None


def sqlite_get_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    # columns: cid, name, type, notnull, dflt_value, pk
    return [r[1] for r in cur.fetchall()]


def sqlite_latest_ts(conn: sqlite3.Connection, table: str) -> Optional[str]:
    """
    Tries to find a latest 'ts' value. Works if table has a 'ts' or 'asof_ts' column.
    Returns raw stored string (no formatting).
    """
    cols = set(sqlite_get_columns(conn, table))
    ts_col = None
    if "ts" in cols:
        ts_col = "ts"
    elif "asof_ts" in cols:
        ts_col = "asof_ts"
    if not ts_col:
        return None
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {ts_col} FROM {table} ORDER BY {ts_col} DESC LIMIT 1")
        row = cur.fetchone()
        return str(row[0]) if row and row[0] is not None else None
    except Exception:
        return None


def safe_symbol_dirname(p: Path) -> str:
    return p.name


def infer_available_timeframes(inv: Dict[str, Any]) -> List[str]:
    """
    inventory.json is expected to include timeframes with counts.
    We do NOT hardcode the timeframe list.
    """
    tfs = []
    tf_obj = inv.get("timeframes", {})
    if isinstance(tf_obj, dict):
        for tf, info in tf_obj.items():
            if isinstance(info, dict) and int(info.get("count", 0) or 0) > 0:
                tfs.append(tf)
    return sorted(tfs)


def pick_primary_series_table(tables: List[str]) -> Optional[str]:
    """
    Pick a compute table to represent 'series' for rowcounts/columns.
    We avoid hardcoding exact names by using heuristics.
    Preference order:
    - state_series
    - escalation
    - any table containing 'series'
    - else None
    """
    lower = [t.lower() for t in tables]
    # exact matches
    for name in ["state_series", "escalation", "states", "regime_states"]:
        if name in lower:
            return tables[lower.index(name)]
    # contains 'series'
    for i, t in enumerate(lower):
        if "series" in t:
            return tables[i]
    return None


def compute_dynamic_calculation_units(
    compute_conn: sqlite3.Connection, series_table: str
) -> Tuple[int, int]:
    """
    A transparent, dynamic proxy for "calculations performed":
    - We count total rows in a representative output table (series_table).
    - We count output columns dynamically via PRAGMA table_info.
    - We define "calc_units" = rows * (#output_columns)

    We do NOT hardcode which metrics exist. As you add/remove columns, this updates.
    """
    rows = sqlite_count_rows(compute_conn, series_table) or 0
    cols = sqlite_get_columns(compute_conn, series_table)

    # Exclude obvious identifier columns if present (still not hardcoding the full schema)
    id_like = {"id", "symbol", "timeframe", "tf", "ts", "asof_ts"}
    output_cols = [c for c in cols if c.lower() not in id_like]

    return rows, rows * len(output_cols)


@dataclass
class AssetRegistryItem:
    symbol: str
    asset_class: str
    name: str
    has_compute: bool
    timeframes: List[str]
    bars_total: int
    bars_by_tf: Dict[str, int]
    latest_bar_ts_by_tf: Dict[str, str]
    compute_latest_ts: Optional[str]
    compute_series_table: Optional[str]
    compute_rows: int
    compute_calc_units: int
    updated_utc: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "name": self.name,
            "has_compute": self.has_compute,
            "timeframes": self.timeframes,
            "bars_total": self.bars_total,
            "bars_by_tf": self.bars_by_tf,
            "latest_bar_ts_by_tf": self.latest_bar_ts_by_tf,
            "compute": {
                "latest_ts": self.compute_latest_ts,
                "series_table": self.compute_series_table,
                "rows": self.compute_rows,
                "calc_units": self.compute_calc_units,
            },
            "updated_utc": self.updated_utc,
        }


def main() -> None:
    if not ASSETS_DIR.exists():
        raise SystemExit(f"Assets directory not found: {ASSETS_DIR}")

    items: List[AssetRegistryItem] = []

    totals = {
        "assets_total": 0,
        "assets_with_compute": 0,
        "bars_total": 0,
        "compute_rows_total": 0,
        "calc_units_total": 0,
        "timeframes_seen": set(),
        "asset_classes_seen": set(),
    }

    for asset_dir in sorted(ASSETS_DIR.iterdir()):
        if not asset_dir.is_dir():
            continue

        symbol = safe_symbol_dirname(asset_dir)
        meta = read_json(asset_dir / "meta.json") or {}
        inv = read_json(asset_dir / "inventory.json") or {}

        asset_class = str(meta.get("asset_class") or meta.get("type") or "UNKNOWN")
        name = str(meta.get("name") or symbol)

        # inventory.json timeframes are the truth; no hardcoded TF list.
        tfs = infer_available_timeframes(inv)

        bars_by_tf: Dict[str, int] = {}
        latest_bar_ts_by_tf: Dict[str, str] = {}

        tf_obj = inv.get("timeframes", {})
        if isinstance(tf_obj, dict):
            for tf, info in tf_obj.items():
                if not isinstance(info, dict):
                    continue
                c = int(info.get("count", 0) or 0)
                if c <= 0:
                    continue
                bars_by_tf[tf] = c
                totals["timeframes_seen"].add(tf)
                # attempt to keep min/max if available
                max_ts = info.get("max_ts")
                if max_ts is not None:
                    latest_bar_ts_by_tf[tf] = str(max_ts)

        bars_total = sum(bars_by_tf.values())

        compute_db = asset_dir / "compute.db"
        has_compute = compute_db.exists() and compute_db.stat().st_size > 0

        compute_latest_ts = None
        compute_series_table = None
        compute_rows = 0
        compute_calc_units = 0

        if has_compute:
            try:
                conn = sqlite3.connect(str(compute_db))
                tables = sqlite_get_tables(conn)
                compute_series_table = pick_primary_series_table(tables)
                if compute_series_table:
                    compute_latest_ts = sqlite_latest_ts(conn, compute_series_table)
                    compute_rows, compute_calc_units = compute_dynamic_calculation_units(
                        conn, compute_series_table
                    )
                conn.close()
            except Exception:
                # if compute exists but introspection fails, keep zeros; registry still builds
                pass

        item = AssetRegistryItem(
            symbol=symbol,
            asset_class=asset_class,
            name=name,
            has_compute=has_compute,
            timeframes=tfs,
            bars_total=bars_total,
            bars_by_tf=bars_by_tf,
            latest_bar_ts_by_tf=latest_bar_ts_by_tf,
            compute_latest_ts=compute_latest_ts,
            compute_series_table=compute_series_table,
            compute_rows=compute_rows,
            compute_calc_units=compute_calc_units,
            updated_utc=str(inv.get("updated_utc") or meta.get("updated_utc") or utc_now_iso()),
        )
        items.append(item)

        totals["assets_total"] += 1
        totals["asset_classes_seen"].add(asset_class)
        totals["bars_total"] += bars_total
        totals["compute_rows_total"] += compute_rows
        totals["calc_units_total"] += compute_calc_units
        if has_compute:
            totals["assets_with_compute"] += 1

    asset_classes = sorted(c for c in totals["asset_classes_seen"] if c != "UNKNOWN")

    assets = [it.to_dict() for it in items]

    # 1) Earnings universe comes from universe_plan.json (default membership)
    universe_plan_path = REPO_ROOT / "data" / "index" / "universe_plan.json"
    earnings_set = set()
    if universe_plan_path.exists():
        plan = json.loads(universe_plan_path.read_text(encoding="utf-8"))
        for row in plan.get("symbols", []):
            s = (row.get("symbol") or "").strip().upper()
            if s:
                earnings_set.add(s)

    # 2) Core universe comes from repo_root/core_symbols.txt (explicit override)
    core_path = REPO_ROOT / "core_symbols.txt"
    core_set = set()
    if core_path.exists():
        for raw in core_path.read_text(encoding="utf-8").splitlines():
            s = raw.strip().upper()
            if s and not s.startswith("#"):
                core_set.add(s)

    # 3) Attach capabilities per asset (no hardcoding of symbols in code)
    for a in assets:
        sym = (a.get("symbol") or "").strip().upper()

        earnings = sym in earnings_set
        core = sym in core_set

        # Enforce hierarchy: core => earnings
        if core and not earnings:
            earnings = True

        a["capabilities"] = {
            "earnings_module": bool(earnings),
            "core_engine": bool(core),
        }

    registry = {
        "generated_utc": utc_now_iso(),
        "assets": assets,
        "asset_classes": asset_classes,
        "timeframes": sorted(totals["timeframes_seen"]),
    }

    core_count = sum(1 for a in assets if a.get("capabilities", {}).get("core_engine"))
    earnings_count = sum(1 for a in assets if a.get("capabilities", {}).get("earnings_module"))

    stats = {
        "generated_utc": utc_now_iso(),
        "assets_total": totals["assets_total"],
        "assets_with_compute": totals["assets_with_compute"],
        "bars_total": totals["bars_total"],
        "compute_rows_total": totals["compute_rows_total"],
        # "calc_units_total" is a transparent, reproducible proxy for "calculations"
        # computed dynamically from your compute tables' rowcounts * output columns.
        "calc_units_total": totals["calc_units_total"],
        "asset_classes": asset_classes,
        "timeframes": sorted(totals["timeframes_seen"]),
        "core_count": core_count,
        "earnings_count": earnings_count,
    }

    (INDEX_DIR / "registry.json").write_text(
        json.dumps(registry, indent=2, sort_keys=True), encoding="utf-8"
    )
    (INDEX_DIR / "stats.json").write_text(
        json.dumps(stats, indent=2, sort_keys=True), encoding="utf-8"
    )

    print("WROTE:", INDEX_DIR / "registry.json")
    print("WROTE:", INDEX_DIR / "stats.json")
    print("STATS:", json.dumps(stats, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
