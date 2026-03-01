# Global Snapshot Manifest

**Purpose:** Single auditable manifest per release. Enables the claim: *"Backtests and displayed metrics refer to snapshot YYYY-MM-DD."*

## Location

`data/snapshots/manifest_YYYY-MM-DD.json`

## V1 Schema

| Field | Type | Description |
|-------|------|-------------|
| `snapshot_id` | string | Date (YYYY-MM-DD) |
| `built_utc` | string | When manifest was built (UTC ISO) |
| `code_version` | string \| null | Git commit hash (short) |
| `symbols` | string[] | All symbols included |
| `symbols_data` | object | Per-symbol details |

### Per-symbol (`symbols_data[symbol]`)

| Field | Type | Description |
|-------|------|-------------|
| `timeframes` | object | Per-TF: `min_ts`, `max_ts`, `bar_count` |
| `compute_asof_utc` | string \| null | Latest bar timestamp used |
| `compute_db_sha256` | string | (optional) Hash for integrity |

## Usage

```bash
# Build for today (default)
python scripts/build_snapshot_manifest.py

# Build for specific date
python scripts/build_snapshot_manifest.py --date 2026-02-27

# Skip DB hashing (faster for large datasets)
python scripts/build_snapshot_manifest.py --no-db-hash
```

## When to Run

- After `pipeline_batch_full` completes
- After nightly scheduler run
- Before a release or deployment

Safe to run on Vultr or Mac. Reads existing `manifest.json`, `compute_manifest.json`, and `compute.db` per symbol. No data modification.

## Claim

With a built manifest, you can state:

> "Backtests and displayed metrics refer to snapshot 2026-02-27."

Even if each symbol has slightly different as-of timestamps, the snapshot manifest makes that explicit and auditable.
