# Schema Versioning

**Purpose:** Canonical schema for Parquet bars and compute.db. Use when reading/writing data or migrating.

Version numbering: `v1`, `v2`, ... (increment on breaking changes).

---

## Parquet Bars Schema (v1)

**Location:** `data/assets/{SYMBOL}/bars/{timeframe}/` (partitioned by date)

| Column | Type | Description |
|--------|------|-------------|
| ts | Datetime | Bar timestamp |
| open | Float64 | Open price |
| high | Float64 | High price |
| low | Float64 | Low price |
| close | Float64 | Close price |
| volume | Int64 | Volume |

**Partition:** `date` (YYYY-MM-DD, derived from ts)

**Constants:** `core.schema_versions.PARQUET_BARS_SCHEMA_VERSION = "v1"`

---

## compute.db Schema (v1)

**Location:** `data/assets/{SYMBOL}/compute.db`

### schema_version (metadata table)

| Column | Type | Description |
|--------|------|-------------|
| version | TEXT | Schema version (e.g. v1) |
| updated_at | TEXT | Last update (UTC ISO) |

### escalation_history_v3

| Column | Type | Description |
|--------|------|-------------|
| symbol | TEXT | Asset symbol |
| timeframe | TEXT | 15min, 1h, 4h, 1day, 1week |
| asof | TEXT | Bar timestamp (asof) |
| esc_raw | REAL | Raw escalation value |
| esc_pctl | REAL | Production signal (= esc_pctl_era_adj, V2.1) |
| esc_pctl_expanding | REAL | Expanding-window percentile (comparison only; not production) |
| esc_pctl_252, esc_pctl_504, esc_pctl_1260, esc_pctl_2520 | REAL | Rolling percentiles (trailing 252/504/1260/2520 bars, 1day) |
| esc_pctl_52, esc_pctl_104, esc_pctl_260 | REAL | Rolling percentiles (trailing 52/104/260 bars, 1week) |
| esc_pctl_era | REAL | Era-conditioned percentile (raw, within-era expanding) |
| esc_pctl_era_confidence | REAL | Confidence: min(1, bars_in_era / CONF_TARGET); timeframe-consistent |
| esc_pctl_era_adj | REAL | **Production signal**: p_adj = 0.5 + (p - 0.5) * conf |
| esc_bucket | TEXT | Bucket label (NA when insufficient history) |
| fwd_absret_h | REAL | Forward absolute return |
| event_flag | INTEGER | Event flag |
| event_severity | TEXT | Event severity |

**Primary key:** (symbol, timeframe, asof)

### state_history

| Column | Type | Description |
|--------|------|-------------|
| symbol | TEXT | Asset symbol |
| timeframe | TEXT | Timeframe |
| asof | TEXT | Bar timestamp |
| state_json | TEXT | JSON: regime state with 11 metrics + escalation_v2 |

**Primary key:** (symbol, timeframe, asof)

### latest_state

| Column | Type | Description |
|--------|------|-------------|
| symbol | TEXT | Asset symbol |
| timeframe | TEXT | Timeframe |
| asof | TEXT | Latest bar timestamp |
| state_json | TEXT | Latest state JSON |
| hazard_score | REAL | Hazard score (0–100) |
| cross_tf_consensus | REAL | Cross-TF consensus |
| updated_at | TEXT | Last update |
| updated_utc | TEXT | Last update (UTC) |

**Primary key:** (symbol, timeframe)

---

## Reproducibility

See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for how to reproduce a given state from manifests.

## Compatibility

- **Current:** v1 for both Parquet and compute.db
- **Read path:** Support current version. Previous versions (v0/legacy) may be supported where feasible; migration scripts exist for legacy live.db/frozen.
- **Future:** When schema changes, increment version. Add migration or compatibility layer as needed.
