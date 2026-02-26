# Reproducibility

**Purpose:** How to reproduce a given compute output. Manifests, version pinning, deterministic compute.

## Deterministic Compute

**Same bars + same code → same compute.db**

The regime compute is deterministic: given identical bar data (Parquet) and the same code version, `compute_asset_full` produces identical `compute.db` output. No randomness in the escalation or state computation.

## Manifests

### Bar manifest (`data/assets/{SYMBOL}/manifest.json`)

Written after backfill or migrate. Contains:

- `symbol`: Asset symbol
- `timeframes`: Per-TF counts, min_ts, max_ts
- `timestamp`: When written (UTC)

Use to verify which bars were available at a given time.

### Compute manifest (`data/assets/{SYMBOL}/compute_manifest.json`)

Written after compute. Contains:

- `symbol`: Asset symbol
- `asof`: Latest bar timestamp used (from escalation_history_v3)
- `bar_count_used`: Total bars read from Parquet for compute
- `schema_version`: Schema version (e.g. v1)
- `timestamp`: When written (UTC)

Use to verify which bars were used for a given compute run.

## Reproducing a Given State

1. **Identify the state:** Check `compute_manifest.json` for `asof` and `bar_count_used`.

2. **Ensure same bars:** Verify `manifest.json` shows the same timeframes and counts. Bars are in `data/assets/{SYMBOL}/bars/{tf}/`.

3. **Run compute:**
   ```bash
   python scripts/compute_asset_full.py --symbol {SYMBOL} --input parquet
   ```

4. **Result:** With identical Parquet bars and same code, the new `compute.db` matches the original (escalation_history_v3, state_history, latest_state).

## Version Pinning

For full reproducibility across time:

- Pin regime-engine code version (git commit)
- Use manifest timestamps to confirm bar state
- Schema versions (Parquet v1, compute.db v1) ensure compatibility
