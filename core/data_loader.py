import os
import glob
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def compute_db_path(symbol: str) -> Optional[Path]:
    """
    Path to compute.db for symbol (scheduler output).
    Returns None if file does not exist.
    """
    p = PROJECT_ROOT / "data" / "assets" / _norm_symbol(symbol) / "compute.db"
    return p if p.exists() else None


@dataclass(frozen=True)
class AssetBundlePaths:
    symbol: str
    latest_state_json: Optional[str]
    full_history_csv: Optional[str]


def _norm_symbol(symbol: str) -> str:
    return str(symbol).upper().strip()


def find_latest_state_json(symbol: str, root: str = "validation_outputs") -> Optional[str]:
    """
    Your project currently writes latest_state.json under:
      validation_outputs/audit_{SYMBOL}/latest_state.json
    We lock onto that first, then fall back to a broader search.
    """
    sym = _norm_symbol(symbol)

    preferred = os.path.join(root, f"audit_{sym}", "latest_state.json")
    if os.path.exists(preferred):
        return preferred

    # Fallback: any latest_state.json that includes the symbol in its path
    candidates = glob.glob(os.path.join(root, "**", "latest_state.json"), recursive=True)
    candidates = [p for p in candidates if sym in p.upper()]
    candidates = sorted(set(candidates))
    return candidates[-1] if candidates else None


def find_full_history_csv(symbol: str, root: str = "validation_outputs") -> Optional[str]:
    """
    Your project currently writes full_history.csv under patterns like:
      validation_outputs/{SYMBOL}/release-audit-YYYYMMDD-vN/full_history.csv
    We lock onto that first, then fall back.
    """
    sym = _norm_symbol(symbol)

    preferred = glob.glob(os.path.join(root, sym, "release-audit-*", "full_history.csv"))
    preferred = sorted(preferred)
    if preferred:
        return preferred[-1]

    # Fallback: any full_history.csv that includes the symbol in its path
    candidates = glob.glob(os.path.join(root, "**", "full_history.csv"), recursive=True)
    candidates = [p for p in candidates if sym in p.upper()]
    candidates = sorted(set(candidates))
    return candidates[-1] if candidates else None


def find_asset_bundle(symbol: str, root: str = "validation_outputs") -> AssetBundlePaths:
    """
    Single source of truth: where to load UI data for an asset from.
    """
    sym = _norm_symbol(symbol)
    return AssetBundlePaths(
        symbol=sym,
        latest_state_json=find_latest_state_json(sym, root=root),
        full_history_csv=find_full_history_csv(sym, root=root),
    )
