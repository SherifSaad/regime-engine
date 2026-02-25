# Regime Intelligence Pipeline – Refactor Outline

**Status:** DRAFT – Pending approval before implementation  
**Goal:** Clean up inconsistencies without breaking the working version.

---

## 1. Current State Summary

### 1.1 Asset Sources (Dual, Inconsistent)

| Source | Location | Used By | Count |
|--------|----------|---------|-------|
| `core.assets_registry.default_assets()` | Python (hardcoded) | scheduler.py, Dashboard.py, asset_class_rules | 5 symbols |
| `data/assets/universe_final.json` | JSON file | backfill_asset_full.py | ~1,500 symbols |

**Problem:** Scheduler and Dashboard use a hardcoded list. Pipeline uses universe_final.json. Adding assets requires editing Python code for scheduler/Dashboard.

---

### 1.2 Compute Paths (Dual, Different Outputs)

| Path | Input | Output | Used By |
|------|-------|--------|---------|
| **Per-asset pipeline** | frozen_*.db | compute.db (per symbol) | run_batch, validation_leadtime_spy, build_registry |
| **Scheduler** | regime_cache.db bars | regime_cache.db (latest_state, state_history) | (no escalation) |

**Differences:**
- Per-asset: full history, expanding window, escalation_history_v3 + state_history + latest_state
- Scheduler: last N bars (lookback=2000), rolling window, latest_state + state_history only (no escalation)

**Problem:** Two different compute behaviors. Results not identical for the same bar.

---

### 1.3 Database Layouts (Dual)

| Layout | Path | Tables |
|--------|------|--------|
| **Per-asset** | `data/assets/{SYMBOL}/live.db`, `frozen_*.db`, `compute.db` | bars, fetch_cursor (live); bars (frozen); escalation_history_v3, state_history, latest_state (compute) |
| **Single** | `data/regime_cache.db` | bars, fetch_cursor, latest_state, state_history |

**Problem:** Scheduler writes to regime_cache.db. Pipeline uses per-asset. No single source of truth for live data.

---

### 1.4 Overlapping Scripts

| Script | Purpose | Redundant? |
|--------|---------|------------|
| scheduler.py | Fetch + compute, multi-asset, regime_cache.db | No (primary) |
| scheduler_spy.py | Fetch + compute, SPY only, regime_cache.db | Yes (subset of scheduler) |
| fetch_spy_bars.py | Fetch only, SPY, regime_cache.db, single run | Yes (scheduler does fetch) |

---

### 1.5 Dashboard & UI Data Flow

| Component | Data Source |
|-----------|-------------|
| Dashboard symbol list | `default_assets()` (5 hardcoded) |
| Dashboard state/history | `validation_outputs/audit_{SYMBOL}/latest_state.json`, `full_history.csv` |
| build_registry | Scans `data/assets/*`, reads per-asset compute.db |
| core.engine.get_snapshot | validation_outputs (JSON/CSV) |

**Note:** Dashboard does NOT read regime_cache.db or compute.db directly. It reads validation_outputs (audit bundles).

---

### 1.6 Validation Scripts

| Script | DB Used |
|--------|---------|
| validation_leadtime_spy.py | compute.db (SPY) – per-asset |
| validate_crisis_concentration.py | regime_cache_SPY_escalation_frozen_2026-02-19.db |
| validate_escalation_*.py (several) | regime_cache_SPY_escalation_frozen_2026-02-19.db |

**Problem:** Validation scripts use legacy regime_cache_SPY_escalation_frozen DB. Per-asset validation uses compute.db.

---

## 2. Proposed Changes (For Approval)

### 2.1 Phase 1: Remove Redundant Scripts (Low Risk)

**Actions:**
- Delete `scripts/fetch_spy_bars.py`
- Delete `scripts/scheduler_spy.py`

**Rationale:** scheduler.py covers both (multi-asset fetch + compute). No unique use case for fetch-only or SPY-only.

**Risk:** Low. If anyone runs these directly, they stop working. Document removal in CHANGELOG.

---

### 2.2 Phase 2: Unify Asset Source (Medium Risk)

**Actions:**
- Add `load_assets_from_universe(path)` in `core/assets_registry.py` that reads `universe_final.json` and returns `List[Asset]`
- Add optional `asset_class` mapping: universe has `asset_class` (e.g. US_EQUITY). Map to scheduler rules (Index, Stocks, FX, Crypto, etc.)
- Add `default_assets()` behavior: either (a) keep hardcoded 5 as fallback, or (b) load from universe with optional filter (e.g. `core_symbols.txt` or first N)
- Update `scheduler.py` to use assets from universe (with configurable filter: e.g. "scheduler_symbols.txt" or env var)
- Update `core/asset_class_rules.py`: build `SYMBOL_TO_ASSET_CLASS` from universe instead of default_assets
- Update `Dashboard.py`: load symbol list from `data/index/registry.json` (built by build_registry) OR from universe with filter, instead of default_assets

**Rationale:** Single source of truth. New assets added to universe_final.json automatically flow to scheduler (if in filter) and Dashboard (if in registry).

**Risk:** Medium. Dashboard and scheduler behavior changes. Need to ensure registry is built before Dashboard works.

**Open question:** What filter for scheduler? All ~1500 symbols would overwhelm API. Options: (a) `core_symbols.txt`, (b) `scheduler_symbols.txt`, (c) registry.json "has_compute" subset, (d) env var list.

---

### 2.3 Phase 3: Unify Compute Path & DB Layout (High Risk)

**Proposed target:** Single layout = per-asset. Scheduler writes to per-asset live.db. Compute reads frozen (or live for real-time) and writes compute.db.

**Actions:**
- Modify `scheduler.py` to write bars to `data/assets/{SYMBOL}/live.db` instead of regime_cache.db
- Scheduler must use per-asset fetch_cursor (already in live.db schema)
- Compute step: scheduler currently computes in-process. Options:
  - **Option A:** Scheduler calls `compute_asset_full.py` as subprocess when new bars arrive (reads frozen; but frozen is daily snapshot – mismatch for real-time)
  - **Option B:** Scheduler computes from live.db directly (new code path: read live.db, compute, write to compute.db). Align logic with compute_asset_full (full history vs lookback – must match)
  - **Option C:** Keep regime_cache for "live" scheduler output; add a sync job that copies latest_state from regime_cache to compute.db for dashboard consumption. (Adds complexity, keeps dual path)
- Deprecate `regime_cache.db`: migrate any consumers to per-asset compute.db
- Update `core/storage.py`: used by scheduler init_db. Either remove or repurpose for per-asset init

**Rationale:** One layout. No regime_cache. Pipeline and scheduler both use per-asset.

**Risk:** High. Scheduler logic changes significantly. Real-time compute from live.db vs batch compute from frozen – different use cases (live dashboard vs backtest/validation).

**Open question:** Is the scheduler for live dashboard updates, or for batch? If live: compute from live.db, write to compute.db. If batch: scheduler only fetches to live.db; separate cron runs freeze → compute.

---

### 2.4 Phase 4: Align Compute Logic (Medium Risk)

**Problem:** compute_asset_full uses expanding window (full history). Scheduler uses lookback (last 2000 bars). Results differ.

**Actions:**
- Decide: should scheduler compute use full history (like compute_asset_full) or keep lookback for speed?
- If full history: scheduler compute becomes slow (same as compute_asset_full per-bar for state). May need to compute only latest bar with full history (expensive).
- If lookback: document that scheduler output is "approximate" for real-time; compute_asset_full is "canonical" for backtest/validation.
- Add escalation to scheduler compute if we want identical output (currently scheduler has no escalation_history_v3).

**Rationale:** Either identical output (slower) or documented difference (faster).

---

### 2.5 Phase 5: Validation Scripts & Legacy DBs (Low–Medium Risk)

**Actions:**
- Audit all scripts that use `regime_cache_SPY_escalation_frozen_2026-02-19.db`
- Migrate to use `data/assets/SPY/compute.db` (per-asset) where schema aligns
- If schema differs (escalation_history vs escalation_history_v3), add adapter or update scripts
- Remove or archive legacy regime_cache_SPY_escalation_frozen DB references

**Rationale:** Single source for validation.

---

### 2.6 Phase 6: SPY Special Handling (Low Risk)

**Current:** scheduler_spy, fetch_spy_bars, validation_leadtime_spy, validation_events_spy – SPY-specific.

**Actions:**
- Remove scheduler_spy, fetch_spy_bars (Phase 1)
- validation_leadtime_spy, validation_events_spy: keep as SPY-focused validation tools (they validate methodology). No change unless we generalize to multi-symbol.
- Ensure SPY is in universe and scheduler symbol list like any other asset

**Rationale:** SPY is one symbol in the universe. No special code paths.

---

## 3. What Will NOT Change (Preserve Working Version)

- **Per-asset pipeline:** backfill_asset_full.py, validate_asset_bars.py, freeze_asset_db.py, compute_asset_full.py, pipeline_asset_full.py, pipeline_batch_full.py – logic unchanged
- **Data flow:** ingest → validate → freeze → compute → compute.db
- **Frozen:** bars-only snapshot, no skip (already done)
- **universe_final.json:** remains source for backfill
- **build_registry.py:** continues to scan data/assets/*, read compute.db
- **regime_engine:** compute_market_state_from_df, escalation logic – no changes

---

## 4. Implementation Order (Recommended)

1. **Phase 1** – Remove redundant scripts (immediate, low risk)
2. **Phase 2** – Unify asset source (enables Phase 3)
3. **Phase 5** – Migrate validation scripts to compute.db (can do in parallel with 2)
4. **Phase 6** – Remove SPY special handling in code (after Phase 1)
5. **Phase 3 & 4** – Unify compute path and align logic (requires decisions on open questions)

---

## 5. Open Questions for Approval

1. **Scheduler symbol filter:** How to select which symbols the scheduler fetches? (core_symbols.txt, scheduler_symbols.txt, registry subset, env var?)
2. **Scheduler output:** Should scheduler write to per-asset live.db + trigger compute, or keep regime_cache for "live" and have a separate sync?
3. **Compute alignment:** Should scheduler compute use full history (identical to compute_asset_full) or keep lookback (faster, approximate)?
4. **Dashboard symbol list:** Load from registry.json, universe_final.json, or keep a small curated list?
5. **Legacy validation DBs:** Migrate all to compute.db now, or phase out gradually?

---

## 6. Approval Checklist

- [ ] Phase 1 approved
- [ ] Phase 2 approved (including asset filter approach)
- [ ] Phase 3 direction approved (per-asset vs regime_cache)
- [ ] Phase 4 approach approved (full history vs lookback)
- [ ] Phase 5 approved
- [ ] Phase 6 approved
- [ ] Open questions answered
