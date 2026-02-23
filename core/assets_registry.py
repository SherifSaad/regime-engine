# core/assets_registry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Asset:
    symbol: str          # internal canonical symbol shown in UI (e.g., "SPY", "BTCUSD")
    name: str            # friendly display name
    asset_class: str     # Index / Stocks / Futures / FX / Crypto / Commodities / Bonds
    vendor_symbol: str   # symbol as expected by the data vendor (Twelve Data)


def default_assets() -> List[Asset]:
    """
    Starter registry: your already-validated set.
    We'll expand this to 60–80 assets once Twelve Data is wired.
    """
    return [
        Asset(symbol="SPY", name="S&P 500 ETF", asset_class="Index", vendor_symbol="SPY"),
        Asset(symbol="QQQ", name="Nasdaq 100 ETF", asset_class="Index", vendor_symbol="QQQ"),
        Asset(symbol="NVDA", name="NVIDIA", asset_class="Stocks", vendor_symbol="NVDA"),
        Asset(symbol="BTCUSD", name="Bitcoin / USD", asset_class="Crypto", vendor_symbol="BTC/USD"),
        Asset(symbol="XAUUSD", name="Gold / USD", asset_class="Commodities", vendor_symbol="XAU/USD"),
    ]


def assets_by_class(assets: List[Asset]) -> Dict[str, List[Asset]]:
    out: Dict[str, List[Asset]] = {}
    for a in assets:
        out.setdefault(a.asset_class, []).append(a)
    return out


def get_asset(symbol: str, assets: List[Asset]) -> Asset | None:
    sym = str(symbol).upper().strip()
    for a in assets:
        if a.symbol.upper() == sym:
            return a
    return None
