# Hedge Fund Standards – Full Implementation Plan

**Goal:** Apply all 9 standards. One clear architecture. No shortcuts.

---

## Approval & Risk Assessment

| Question | Answer |
|----------|--------|
| Can this be done in a planned fashion? | **Yes.** Phases are ordered by dependency. |
| Will it create a mess? | **No**, if we follow the order and verify each phase before proceeding. |
| Rollback? | Each phase is reversible; frozen/live.db kept until Phase 2 complete. |

**Rule:** Do not proceed to the next phase until the current phase is verified and working.

---

## The 9 Standards

| # | Standard | Status |
|---|----------|--------|
| 1 | One clear, consistent data model for all symbols | Pending |
| 2 | Parquet as the only bar source for compute | Partial (BarsProvider exists; pipeline still uses frozen) |
| 3 | No reliance on live.db or frozen DBs in main pipeline | Pending |
| 4 | Willingness to redo work (migrate, recompute) | Assumed |
| 5 | Backfill → Parquet directly (no live.db) | Pending |
| 6 | Compute only when changed | Pending (scheduler_daily) |
| 7 | Validation gates before compute | Partial (validate_asset_bars exists) |
| 8 | Schema versioning | Pending |
| 9 | Audit trail / reproducibility | Pending |

---

## Phase 1: Parquet-Only Pipeline (Standards 1, 2, 3)

**Goal:** One data model. Parquet only. No live.db or frozen in main path.

**Pre-condition:** None. Can start immediately.

**Dependency:** Phase 1.2 requires validate to support Parquet (see 1.2a).

### 1.1 Migrate all existing data to Parquet
- [ ] Run `migrate_live_to_parquet.py --all` for all symbols with live.db
- [ ] Run `migrate_bars_to_assets.py` if any data still in old `data/bars/`
- [ ] Verify: every symbol with bars has `data/assets/{SYMBOL}/bars/{tf}/`
- [ ] **Checkpoint:** Spot-check 3 symbols: `BarsProvider.get_bars(sym, tf)` returns data

### 1.2a Add Parquet support to validate (prerequisite for 1.2)
- [ ] `validate_asset_bars.py`: add `--input parquet` (default) and `--input live`
- [ ] When `--input parquet`: read from BarsProvider, check bar counts, OHLC sanity, duplicates, nulls
- [ ] When `--input live`: keep existing live.db validation for backward compat during transition

### 1.2 Update pipeline to Parquet-only
- [ ] Change `pipeline_asset_full.py`: backfill → migrate → validate(parquet) → compute(parquet)
- [ ] Remove freeze step from pipeline
- [ ] Compute always uses `--input parquet` (no `--input frozen`)
- [ ] Update `pipeline_batch_full.py` skip-if-done: check Parquet + compute.db (not frozen)
- [ ] **Checkpoint:** Run pipeline on 1 symbol (e.g. QQQ); verify compute.db written from Parquet

### 1.3 Deprecate frozen in compute
- [ ] Make `--input parquet` the default and only supported path in `compute_asset_full.py`
- [ ] Remove or deprecate `--input frozen` (emit warning if used)
- [ ] Update all docs and scripts that reference frozen

### 1.4 Unified pipeline for daily
- [ ] Add `pipeline_asset_full.py --mode daily` or `pipeline_daily.py` for daily symbols
- [ ] Flow: backfill_partial → migrate → validate(parquet) → compute(parquet)
- [ ] Ensure `pipeline_batch_full.py` supports `--mode daily` and batch file from earnings_symbols.txt
- [ ] **Checkpoint:** Run daily pipeline on 1 symbol; verify end-to-end

**Phase 1 complete when:** Core and daily pipelines run Parquet-only, no freeze, no frozen input.

---

## Phase 2: Backfill Direct to Parquet (Standard 5)

**Goal:** Backfill writes to Parquet. No live.db in pipeline.

**Pre-condition:** Phase 1 complete. All existing data in Parquet.

### 2.1 Add Parquet write path to backfill
- [ ] `backfill_asset_full.py`: add `--output parquet` (default) and `--output live` (legacy)
- [ ] When parquet: write via BarsProvider after each TF fetch (no live.db)
- [ ] `backfill_asset_partial.py`: same for daily (1day, 1week)
- [ ] **Checkpoint:** Backfill 1 symbol to Parquet only; verify bars in `data/assets/{SYMBOL}/bars/`

### 2.2 Remove live.db from pipeline
- [ ] Pipeline: backfill(→Parquet) → validate(parquet) → compute(parquet)
- [ ] Remove migrate step from pipeline (no longer needed for new backfills)
- [ ] Keep `migrate_live_to_parquet.py` as one-time migration tool for existing live.db only

### 2.3 Update validate default
- [ ] `validate_asset_bars.py`: default `--input parquet`; `--input live` only for legacy migration

**Phase 2 complete when:** New backfills write to Parquet. Pipeline has no migrate step. live.db optional.

---

## Phase 3: Compute Only When Changed (Standard 6)

**Goal:** Schedulers run compute only for symbols that received new bars.

**Pre-condition:** Phases 1–2 complete.

### 3.1 scheduler_daily
- [ ] Track `inserted` per symbol in fetch loop
- [ ] Run `run_canonical_compute(symbol)` only when `inserted > 0`
- [ ] Skip compute for symbols with no new bars
- [ ] **Checkpoint:** Run scheduler_daily; confirm compute only for symbols with new bars

### 3.2 scheduler_core
- [ ] Already runs compute only for `changed_symbols` (inserted > 0)
- [ ] Verify and add one-line comment in code

**Phase 3 complete when:** Both schedulers skip compute when no new bars.

---

## Phase 4: Validation Gates (Standard 7)

**Goal:** Automated checks before compute. Bar counts, OHLC sanity, gaps.

**Pre-condition:** Phase 1.2a done (validate already supports Parquet).

### 4.1 Extend validate_asset_bars
- [ ] Ensure all checks: bar count per TF, date range, OHLC sanity, no duplicates, no nulls
- [ ] Add gap detection (optional): flag large gaps in ts sequence

### 4.2 Integrate validation into pipeline
- [ ] Pipeline: run validate before compute; exit with code 1 if validation fails
- [ ] Scheduler: optional `--validate` flag; default skip for speed

### 4.3 Validation report
- [ ] Output clear pass/fail per symbol, per TF
- [ ] Exit code 1 if any failure; 0 only when all pass

**Phase 4 complete when:** Pipeline blocks compute on validation failure. Clear reports.

---

## Phase 5: Schema Versioning (Standard 8)

**Goal:** Version Parquet schema and compute.db schema for reproducibility.

**Pre-condition:** Phases 1–4 complete.

### 5.1 Parquet schema version
- [ ] Add `schema_version` to manifest (see Phase 6) or Parquet metadata
- [ ] Document schema: ts, open, high, low, close, volume
- [ ] BarsProvider: optional schema validation on read (future)

### 5.2 compute.db schema version
- [ ] Add `schema_version` table or metadata to compute.db
- [ ] Document escalation_history_v3, state_history, latest_state schemas
- [ ] Compute script: write version on create/update

### 5.3 Compatibility
- [ ] Define version numbering (e.g. v1, v2)
- [ ] Read path: support current + previous version where feasible

**Phase 5 complete when:** Schemas versioned and documented.

---

## Phase 6: Audit Trail (Standard 9)

**Goal:** Manifest/checksums for "as-of" reproducibility.

**Pre-condition:** Phases 1–5 complete.

### 6.1 Bar manifest
- [ ] Per symbol: `data/assets/{SYMBOL}/manifest.json`
- [ ] Include: symbol, timeframes, counts, min/max ts, timestamp
- [ ] Write after backfill or migrate

### 6.2 Compute manifest
- [ ] Per symbol: `data/assets/{SYMBOL}/compute_manifest.json`
- [ ] Include: symbol, asof, bar_count_used, schema_version, timestamp
- [ ] Write after compute

### 6.3 Reproducibility
- [ ] Document: same bars + same code → same compute.db (deterministic)
- [ ] Document how to reproduce a given state from manifest

**Phase 6 complete when:** Manifests written. Reproducibility documented.

---

## Execution Order

```
Phase 1 (Parquet-only)        → Foundation
  ├── 1.2a (validate Parquet)  → Must complete before 1.2
  └── 1.1, 1.2, 1.3, 1.4
Phase 2 (Backfill direct)     → Eliminate live.db
Phase 3 (Compute when changed) → Quick win
Phase 4 (Validation)           → Safety (4.1 largely done in 1.2a)
Phase 5 (Schema versioning)    → Reproducibility
Phase 6 (Audit trail)          → Compliance
```

**Estimated effort:** Phase 1–3 are the bulk. Phase 4–6 are incremental.

---

## Files to Modify (Summary)

| Phase | Files |
|-------|-------|
| 1 | validate_asset_bars.py, pipeline_asset_full.py, pipeline_batch_full.py, compute_asset_full.py |
| 2 | backfill_asset_full.py, backfill_asset_partial.py, validate_asset_bars.py |
| 3 | scheduler_daily.py, scheduler_core.py |
| 4 | validate_asset_bars.py |
| 5 | BarsProvider, compute_asset_full.py |
| 6 | New: manifest writers; backfill, compute |

---

## Rollback Strategy

| Phase | Rollback |
|-------|----------|
| 1 | Keep freeze step; revert pipeline to frozen. Parquet data remains. |
| 2 | Revert backfill to live.db; re-add migrate to pipeline. |
| 3 | Revert scheduler_daily to always compute. |
| 4–6 | Remove validation/manifest logic. No data loss. |

---

## Next Step

Start with **Phase 1.1**: Run migrate scripts. Then **Phase 1.2a**: Add validate `--input parquet`. Then Phase 1.2–1.4.
