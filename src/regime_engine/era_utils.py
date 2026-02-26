"""
Era resolution and boundary loading for Bai-Perron era-conditioned percentile.
Shared by compute_asset_full and cli (scheduler, build_audit_bundle).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
ERA_METADATA_DIR = _PROJECT_ROOT / "data" / "era_metadata"

ERAS_LEGACY = [
    ("pre2010", None, "2010-01-01"),
    ("2010_2019", "2010-01-01", "2020-01-01"),
    ("2020plus", "2020-01-01", None),
]

SYMBOL_TO_ERA_ASSET_CLASS = {
    "SPY": "EQUITIES_US", "QQQ": "EQUITIES_US", "DIA": "EQUITIES_US", "IWM": "EQUITIES_US",
    "HYG": "CREDIT_HY", "LQD": "CREDIT_IG", "TLT": "RATES_LONG", "IEF": "RATES_INTERMEDIATE",
    "EURUSD": "FX_MAJORS", "GBPUSD": "FX_MAJORS", "USDJPY": "FX_MAJORS", "AUDUSD": "FX_MAJORS", "USDCAD": "FX_MAJORS",
    "WTIUSD": "COMMODITIES_ENERGY", "XAUUSD": "COMMODITIES_METALS", "XAGUSD": "COMMODITIES_METALS",
    "BTCUSD": "CRYPTO", "ETHUSD": "CRYPTO", "BNBUSD": "CRYPTO", "SOLUSD": "CRYPTO", "XRPUSD": "CRYPTO",
}

UNIVERSE_AC_TO_ERA_AC = {
    "US_EQUITY_INDEX": "EQUITIES_US", "US_EQUITY": "EQUITIES_US", "US_MEGA_CAP": "EQUITIES_US",
    "CRYPTO": "CRYPTO", "FX": "FX_MAJORS", "Commodities": "COMMODITIES_METALS",
    "Fixed Income": "RATES_INTERMEDIATE",
}

ERA_CSV_AC_TO_CANONICAL = {
    "US_EQUITY_INDEX": "EQUITIES_US", "US_EQUITY": "EQUITIES_US", "FX": "FX_MAJORS",
    "CRYPTO": "CRYPTO", "Commodities": "COMMODITIES_METALS",
}


def resolve_era_asset_class(symbol: str) -> str | None:
    sym = symbol.upper()
    if sym in SYMBOL_TO_ERA_ASSET_CLASS:
        return SYMBOL_TO_ERA_ASSET_CLASS[sym]
    try:
        from core.assets_registry import load_universe
        for a in load_universe():
            if a.get("symbol", "").upper() == sym:
                ac = a.get("asset_class", "")
                return UNIVERSE_AC_TO_ERA_AC.get(ac)
    except Exception:
        pass
    return None


def load_era_boundaries(era_asset_class: str) -> list[tuple[str | None, str | None]]:
    """Load (start_date, end_date) per era from era_boundaries.csv. Returns [] if missing."""
    path = ERA_METADATA_DIR / "era_boundaries.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    if "asset_class" not in df.columns or "start_date" not in df.columns or "end_date" not in df.columns:
        return []
    acs = [era_asset_class] + [k for k, v in ERA_CSV_AC_TO_CANONICAL.items() if v == era_asset_class]
    sub = df[df["asset_class"].isin(acs)].sort_values("era_index")
    if sub.empty:
        return []
    return [(r["start_date"], r["end_date"]) for _, r in sub.iterrows()]


def get_era_bounds_for_symbol(symbol: str) -> list[tuple[str | None, str | None]]:
    """Get era boundaries for symbol. Returns legacy if no metadata."""
    era_ac = resolve_era_asset_class(symbol)
    if era_ac:
        bounds = load_era_boundaries(era_ac)
        if bounds:
            return bounds
    return [(s, e) for _, s, e in ERAS_LEGACY]
