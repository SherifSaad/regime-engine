# core/assets_registry.py
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

# Robust absolute path – works regardless of CWD
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # core/ is one level below root
UNIVERSE_PATH = PROJECT_ROOT / "universe.json"


def load_universe() -> List[Dict]:
    """Load the canonical universe from absolute path."""
    if not UNIVERSE_PATH.exists():
        raise FileNotFoundError(f"Universe file not found at: {UNIVERSE_PATH}")

    with open(UNIVERSE_PATH, encoding="utf-8") as f:
        data = json.load(f)

    return [a for a in data.get("assets", []) if a.get("active", True)]


def _default_assets_symbols() -> List[str]:
    """Internal – returns core symbols only."""
    universe = load_universe()
    return [a["symbol"] for a in universe if a.get("tags") and "core" in a["tags"]][:5]


def scheduler_assets() -> List[Dict]:
    """Returns only assets explicitly enabled for scheduler."""
    return [a for a in load_universe() if a.get("scheduler_enabled", False)]


def real_time_assets() -> List[Dict]:
    """Assets that need near real-time updates (every 15 min). ~100 max."""
    return [a for a in load_universe() if a.get("update_frequency") == "real_time"]


def daily_assets() -> List[Dict]:
    """Assets updated once per day (earnings tier). ~1500."""
    return [a for a in load_universe() if a.get("update_frequency") == "daily"]


def weekly_assets() -> List[Dict]:
    """Assets updated once per week."""
    return [a for a in load_universe() if a.get("update_frequency") == "weekly"]


# ───────────────────────────────────────────────────────────────
# Compatibility layer – restore old Asset-style interface (Phase 1)
# Remove this in Phase 2 once all consumers are migrated
# ───────────────────────────────────────────────────────────────


@dataclass
class LegacyAsset:
    """Mimics old Asset object for backward compatibility."""

    symbol: str
    name: str
    asset_class: str
    exchange: str
    currency: str
    vendor_symbol: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict) -> "LegacyAsset":
        # Map new asset_class to old (Index, Stocks, FX, Crypto, etc.)
        ac = d.get("asset_class", "US_EQUITY")
        _map = {
            "US_EQUITY_INDEX": "Index",
            "US_EQUITY": "Stocks",
            "US_MEGA_CAP": "Stocks",
            "CRYPTO": "Crypto",
            "FX": "FX",
            "Commodities": "Commodities",
            "Futures": "Futures",
            "Fixed Income": "Fixed Income",
        }
        asset_class = _map.get(ac, "Stocks" if "EQUITY" in str(ac) else ac)
        return cls(
            symbol=d["symbol"],
            name=d.get("name", d["symbol"]),
            asset_class=asset_class,
            exchange=d.get("exchange", ""),
            currency=d.get("currency", "USD"),
            vendor_symbol=d.get("provider_symbol") or d["symbol"],
        )


def default_assets() -> List[LegacyAsset]:
    """Backward-compatible – returns LegacyAsset objects."""
    universe = load_universe()
    core_assets = [a for a in universe if a.get("tags") and "core" in a["tags"]][:5]
    if not core_assets:
        # Fallback: first 5 from universe if no "core" tags
        core_assets = universe[:5]
    return [LegacyAsset.from_dict(a) for a in core_assets]


def assets_by_class(assets: List[LegacyAsset]) -> Dict[str, List[LegacyAsset]]:
    """Backward-compatible – groups assets by asset_class."""
    out: Dict[str, List[LegacyAsset]] = {}
    for a in assets:
        out.setdefault(a.asset_class, []).append(a)
    return out


def get_asset(symbol: str, assets: List[LegacyAsset]) -> Optional[LegacyAsset]:
    """Backward-compatible lookup by symbol from asset list."""
    sym = str(symbol).upper().strip()
    for a in assets:
        if a.symbol.upper() == sym:
            return a
    return None
