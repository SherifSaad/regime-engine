# Hedge Fund Standards – Implementation Plan

**Goal:** Single canonical compute, full history, no caps, escalation everywhere.

---

## 1. Target State

| Principle | Target |
|-----------|--------|
| **Single canonical compute** | One compute path. Same logic, same output, for batch and real-time. |
| **Full history, no caps** | All bars from earliest to latest. No 2000-bar or other arbitrary lookback. |
| **Escalation everywhere** | Escalation computed and stored for all symbols, all timeframes. |
| **Single source of truth** | One output store. No divergence between scheduler and per-asset. |
| **Reproducibility** | Frozen/canonical input. Deterministic output. Audit trail. |

---

## 2. Current Gaps (To Fix)

| Gap | Current | Required |
|-----|---------|----------|
| Two compute paths | Polars (scheduler) vs compute_asset_full (per-asset) | One canonical compute |
| 2000 lookback | Scheduler uses last 2000 bars | Full history |
| No escalation in scheduler | Polars regime only | Escalation + regime + state |
| Two output stores | regime_cache.db + compute.db | Single canonical store |
| Daily symbols: 5000 cap | scheduler_earnings fetches 5000 on first run | Full backfill, then compute |

---

## 3. Architecture (Target)

```
Bars (canonical)
  data/assets/{symbol}/bars/{timeframe}/*.parquet   ← Full history, no cap

Compute (canonical)
  data/assets/{symbol}/compute.db           ← escalation_history_v3, state_history, latest_state
  Input: Parquet (full history)
  Output: compute.db
  No lookback cap

Scheduler
  1. Fetch new bars → append to Parquet
  2. Run canonical compute (full history from Parquet) → compute.db
  3. No separate regime_cache.db for state (or regime_cache = cache of latest_state from compute.db)
```

---

## 4. Implementation Phases

### Phase 8.1: Parquet input for compute_asset_full

**Goal:** compute_asset_full can read from Parquet instead of frozen SQLite.

- Add `--input parquet` (default) vs `--input frozen`
- When Parquet: load bars via BarsProvider.get_bars(symbol, tf).collect()
- Full history, no limit
- Output: compute.db (unchanged)

**Files:** `scripts/compute_asset_full.py`

---

### Phase 8.2: Scheduler uses canonical compute ✅

**Goal:** Scheduler invokes compute_asset_full (or shared core) instead of Polars regime.

- Remove Polars regime from scheduler
- After fetch: for each changed symbol, run compute_asset_full with Parquet input
- compute_asset_full writes to data/assets/{symbol}/compute.db
- Remove 2000 lookback; compute uses full Parquet history

**Files:** `scripts/scheduler_real_time.py`, `scripts/scheduler_earnings.py`

**Done:** Both schedulers now call `compute_asset_full --input parquet` via subprocess. No regime_cache.db writes. Full history.

---

### Phase 8.3: regime_cache.db role ✅

**Options:**

- **A) Deprecate regime_cache.db** – All state in compute.db. Consumers read from compute.db.
- **B) regime_cache as read-through cache** – Scheduler writes to compute.db; optional sync job copies latest_state to regime_cache for fast multi-symbol reads.

**Recommendation:** A. Single source of truth = compute.db.

**Done:**
- core/storage: Added `get_compute_db_path(symbol)`. Deprecation notice for regime_cache.
- validation_events_spy: Reads bars from Parquet (BarsProvider), not regime_cache.
- validation_leadtime_spy: Uses `get_compute_db_path("SPY")`; env VALIDATION_COMPUTE_DB or REGIME_DB_PATH.
- scheduler.py, scheduler_spy: Deprecation notice; use scheduler_real_time + scheduler_earnings.

---

### Phase 8.4: Daily symbols – full backfill

**Goal:** Daily symbols get full history before compute, no 5000-bar cap.

- Add backfill path for daily symbols (or extend backfill_asset_full to support daily_assets)
- Backfill: batches of 5000 until earliest (same as real-time)
- scheduler_earnings: only incremental fetch after backfill exists
- First-time daily symbol: run backfill first, then compute

**Files:** `scripts/backfill_asset_full.py` (extend to daily), or new `backfill_daily.py`

---

### Phase 8.5: Remove all caps

- Remove REGIME_LOOKBACK / 2000 from scheduler
- Remove any head(N) limits in compute path
- Twelve Data: 5000 per request is API limit; we page until done (already in backfill)

---

## 5. Data Flow (Final)

```
Backfill (real-time + daily)
  Twelve Data API (batches of 5000) → live.db → migrate_live_to_parquet → Parquet
  No cap on total bars

Compute (canonical)
  Parquet (full) → compute_asset_full → compute.db
  escalation_history_v3, state_history, latest_state
  No lookback cap

Scheduler
  Fetch → Parquet (append)
  Trigger compute_asset_full (Parquet input, full history) → compute.db
```

---

## 6. Validation Checklist

- [ ] Same bar, same symbol: identical regime_state from batch and scheduler
- [ ] Escalation present for all symbols in compute.db
- [ ] No 2000 or other arbitrary bar caps in compute path
- [ ] Full history used for all metrics
- [ ] Single output store (compute.db)
- [ ] Reproducible: same Parquet → same compute.db

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| compute_asset_full slow on 200k bars | Incremental compute (append new rows only); keep full-history correctness |
| Scheduler latency | Run compute async or in background; serve last known state |
| Migration | Phase rollout: Parquet input first, then scheduler switch |

---

## 8. Order of Work

1. **Phase 8.1** – Parquet input for compute_asset_full
2. **Phase 8.2** – Scheduler calls canonical compute (remove Polars regime path)
3. **Phase 8.3** – Deprecate or repurpose regime_cache.db
4. **Phase 8.4** – Full backfill for daily symbols
5. **Phase 8.5** – Remove all remaining caps
