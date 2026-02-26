# Phase 1 Summary – Regime Intelligence Refactor

**Purpose:** Phase 1 folder structure, key files, and import verification. Archive reference.

**Status:** Complete  
**Date:** 2026-02-24

---

## 1. Folder Tree (Phase 1 Structure)

```
data/
├── bars/           # New: parquet bars (BarsProvider)
├── derived/
├── publish/
├── snapshots/
├── meta/
│   └── registry.json
├── locks/
├── index/          # Existing: build_registry output
│   ├── registry.json
│   ├── stats.json
│   └── universe_plan.json
└── assets/         # Existing: per-symbol live.db, frozen, compute.db
    └── ...

core/
├── __init__.py
├── assets_registry.py
├── asset_class_rules.py
├── storage/
│   └── __init__.py    # Moved from storage.py
├── providers/
│   ├── __init__.py
│   └── bars_provider.py
├── assets/             # Empty placeholder
├── compute/            # Empty placeholder
├── data_loader.py
├── engine.py
├── timeframes.py
├── twelvedata_client.py
└── audit.py
```

---

## 2. Key Files

### universe.json (project root)

```json
{
  "version": "2026-02-24",
  "last_updated_utc": "2026-02-24T00:00:00Z",
  "assets": [
    {
      "symbol": "SPY",
      "provider_symbol": "SPY",
      "name": "SPDR S&P 500 ETF Trust",
      "asset_class": "US_EQUITY_INDEX",
      "exchange": "ARCA",
      "currency": "USD",
      "active": true,
      "scheduler_enabled": true,
      "tags": ["core", "high_liquidity"]
    },
    {
      "symbol": "AAPL",
      "provider_symbol": "AAPL",
      "name": "Apple Inc.",
      "asset_class": "US_EQUITY",
      "exchange": "NASDAQ",
      "currency": "USD",
      "active": true,
      "scheduler_enabled": true,
      "tags": ["core"]
    },
    {
      "symbol": "BTCUSD",
      "provider_symbol": "BTC/USD",
      "name": "Bitcoin vs USD",
      "asset_class": "CRYPTO",
      "exchange": "CRYPTO",
      "currency": "USD",
      "active": true,
      "scheduler_enabled": true,
      "tags": ["crypto", "high_volatility"]
    },
    {
      "symbol": "EURUSD",
      "provider_symbol": "EUR/USD",
      "name": "Euro vs USD",
      "asset_class": "FX",
      "exchange": "FX",
      "currency": "USD",
      "active": true,
      "scheduler_enabled": false,
      "tags": ["fx"]
    }
  ]
}
```

### core/assets_registry.py (excerpts)

- **PROJECT_ROOT**, **UNIVERSE_PATH** – absolute paths
- **load_universe()** – loads from UNIVERSE_PATH, filters `active`
- **scheduler_assets()** – assets with `scheduler_enabled`
- **Compatibility layer:** `LegacyAsset`, `default_assets()`, `assets_by_class()`, `get_asset()` – for Dashboard, scheduler, asset_class_rules

### core/providers/bars_provider.py

- **PROJECT_ROOT**, **BARS_ROOT** – absolute paths
- **get_bars(symbol, timeframe, manifest_hash?, upto_ts?)** → `pl.LazyFrame`
- **write_bars(symbol, timeframe, df)** – append-only, dedupe, partitioned by date

### core/storage/__init__.py

- Content moved from `core/storage.py`
- `get_conn()`, `init_db()` – regime_cache.db schema
- Imports unchanged: `from core.storage import get_conn, init_db`

### pyproject.toml

```toml
dependencies = [
  "pandas>=2.0",
  "numpy>=1.24",
  "python-dateutil",
  "polars>=1.0.0,<2.0",
]
```

### data/meta/registry.json

```json
{
  "last_build_utc": null,
  "symbols_with_compute": []
}
```

---

## 3. Notes / Warnings

| Item | Status |
|------|--------|
| **Two asset sources** | `universe.json` (4 assets) vs `universe_final.json` (~1,500). Unify in Phase 2. |
| **Two registry paths** | `data/meta/registry.json` vs `data/index/registry.json`. Reconcile in Phase 2. |
| **BarsProvider not wired** | Writes to `data/bars/` parquet. Pipeline still uses live.db → frozen → compute.db. Integration in Phase 2. |
| **Volume type** | BarsProvider expects `Int64`. Twelve Data may return float. Handle in Phase 2. |

---

## 4. Import Verification

```python
from core.providers.bars_provider import BarsProvider
from core.assets_registry import load_universe, default_assets, UNIVERSE_PATH
from core.storage import get_conn, init_db
```

**Verified output:**
```
BarsProvider.ROOT: /Users/.../regime-engine/data/bars
UNIVERSE_PATH: /Users/.../regime-engine/universe.json
load_universe(): 4 assets
default_assets(): ['SPY', 'AAPL']
All imports OK
```

---

## 5. Phase 1 Commits (Reference)

- Phase 1: Add provider_symbol to universe.json schema
- Phase 1: Convert core/storage to proper package (move storage.py → __init__.py)
- Phase 1: Add compatibility layer in assets_registry.py for old Asset interface
- Phase 1: Add polars dependency (>=1.0.0,<2.0) for BarsProvider and future vectorized compute
- Phase 1: Fix bars_provider.py – correct LazyFrame handling, partitioned read/write, dedupe
- Phase 1: Make universe.json path absolute & robust in assets_registry.py
- Phase 1: Make BarsProvider.ROOT absolute & robust (final consistency fix)
