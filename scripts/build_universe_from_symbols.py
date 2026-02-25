#!/usr/bin/env python3
"""
Build universe.json from core_symbols.txt and universe_symbols.txt.

- core_symbols.txt: poll every 15 min (update_frequency=15min)
- universe_symbols.txt: earnings list, poll once/day (update_frequency=daily)
- Overlap: symbols in BOTH get 15min (core wins – Mag 7 etc. already fully backfilled)

Output: universe.json

Usage:
  python scripts/build_universe_from_symbols.py
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_FILE = PROJECT_ROOT / "core_symbols.txt"
UNIVERSE_FILE = PROJECT_ROOT / "universe_symbols.txt"
OUTPUT = PROJECT_ROOT / "universe.json"

# Twelve Data provider_symbol overrides (symbol -> provider_symbol)
PROVIDER_OVERRIDES = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "AUDUSD": "AUD/USD",
    "USDJPY": "USD/JPY",
    "USDCAD": "USD/CAD",
    "BTCUSD": "BTC/USD",
    "ETHUSD": "ETH/USD",
    "BNBUSD": "BNB/USD",
    "XRPUSD": "XRP/USD",
    "ADAUSD": "ADA/USD",
    "SOLUSD": "SOL/USD",
    "DOGEUSD": "DOGE/USD",
    "AVAXUSD": "AVAX/USD",
    "LINKUSD": "LINK/USD",
    "TONUSD": "TON/USD",
    "XAUUSD": "XAU/USD",
    "XAGUSD": "XAG/USD",
    "XPTUSD": "XPT/USD",
    "XBRUSD": "XBR/USD",
    "WTIUSD": "WTI/USD",
    "NGUSD": "NG/USD",
    "HGUSD": "HG/USD",
    "ZCUSD": "ZC/USD",
}


def load_symbols(path: Path) -> list[str]:
    """Load symbols from text file, one per line, skip empty."""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [s.strip().upper() for s in lines if s.strip()]


def infer_asset_class(symbol: str) -> str:
    if symbol in ("SPY", "QQQ", "DIA", "IWM"):
        return "US_EQUITY_INDEX"
    if symbol.endswith("USD") and symbol not in ("BTCUSD", "ETHUSD", "BNBUSD", "XRPUSD", "ADAUSD", "SOLUSD", "DOGEUSD", "AVAXUSD", "LINKUSD", "TONUSD"):
        if symbol in ("XAUUSD", "XAGUSD", "XPTUSD", "XBRUSD", "WTIUSD", "NGUSD", "HGUSD", "ZCUSD"):
            return "Commodities"
        return "FX"
    if symbol in ("BTCUSD", "ETHUSD", "BNBUSD", "XRPUSD", "ADAUSD", "SOLUSD", "DOGEUSD", "AVAXUSD", "LINKUSD", "TONUSD"):
        return "CRYPTO"
    if symbol in ("BND", "HYG", "IEF", "IGOV", "LQD", "EMB", "TLT", "US02Y", "US10Y", "US30Y", "VIX"):
        return "Fixed Income"
    if symbol.startswith("X") and symbol in ("XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"):
        return "US_EQUITY_INDEX"
    if symbol in ("EEM", "EFA", "EWA", "EWJ", "EWZ", "EZU", "FXI", "VNQ", "VNQI"):
        return "US_EQUITY_INDEX"
    return "US_EQUITY"


def asset_entry(symbol: str, update_frequency: str) -> dict:
    provider = PROVIDER_OVERRIDES.get(symbol, symbol)
    return {
        "symbol": symbol,
        "provider_symbol": provider,
        "name": symbol,
        "asset_class": infer_asset_class(symbol),
        "exchange": "",
        "currency": "USD",
        "active": True,
        "scheduler_enabled": True,
        "tags": ["core"] if update_frequency == "15min" else [],
        "update_frequency": update_frequency,
    }


def main():
    core = set(load_symbols(CORE_FILE))
    universe = load_symbols(UNIVERSE_FILE)

    assets = []
    seen = set()

    # Core symbols first (15min)
    for s in sorted(core):
        if s not in seen:
            assets.append(asset_entry(s, "15min"))
            seen.add(s)

    # Universe (earnings) – daily, skip if already in core
    for s in universe:
        if s not in seen:
            assets.append(asset_entry(s, "daily"))
            seen.add(s)

    out = {
        "version": "2026-02-24",
        "last_updated_utc": "2026-02-24T00:00:00Z",
        "assets": assets,
    }

    import json
    OUTPUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(assets)} assets to {OUTPUT}")
    print(f"  Core (15min): {len(core)}")
    print(f"  Daily only: {len(assets) - len(core)}")
    overlap = len(core & set(universe))
    if overlap:
        print(f"  Overlap (in both): {overlap}")


if __name__ == "__main__":
    main()
