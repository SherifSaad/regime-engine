# Compute Pipeline Architecture

**Purpose:** Eliminate "Which model version is this?" ambiguity for third-party auditors.  
**Scope:** Compute entrypoints, call chains, and model-vs-table mapping.  
**No refactors. No behavior changes. Documentation only.**

---

## 1. Compute Entrypoints

| Entrypoint | Role | DB / Output |
|------------|------|-------------|
| `scripts/compute_asset_full.py` | Full backfill: escalation + state | `compute.db`: escalation_history_v3, state_history, latest_state |
| `scripts/scheduler.py` | Real-time: latest state per TF | `compute.db`: state_history, latest_state |
| `scripts/scheduler_spy.py` | Real-time SPY-only | `compute.db`: state_history, latest_state |
| `scripts/validate_regimes.py` | Validation: run engine over history | In-memory DataFrame (no DB write) |
| `scripts/build_audit_bundle.py` | Release audit: latest state + full history | JSON/CSV files (no DB write) |

---

## 2. Call Chains by Entrypoint

### 2.1 `compute_asset_full.py`

| Output | Call Chain |
|--------|------------|
| **DSR / IIX / SS** | `compute_dsr_iix_ss_arrays_fast(df, symbol)` → `escalation_fast.py` |
| **Escalation raw** | `compute_escalation_v2_series(dsr_arr, iix_arr, ss_arr, close_arr, ema_arr)` → `escalation_v2.py` |
| **Escalation percentile** | `compute_escalation_v2_pct_series(esc_series, min_bars=252)` → `escalation_v2.py` (expanding) |
| **11 metrics** | `compute_market_state_from_df(sub, symbol, include_escalation_v2=False)` → `cli.py` → `metrics.py` |

*Note: Escalation path is direct (no cli). State path uses cli for 11 metrics.*

### 2.2 `scheduler.py`

| Output | Call Chain |
|--------|------------|
| **DSR / IIX / SS** | Via `compute_market_state_from_df(..., include_escalation_v2=True)` → `cli.py` → `compute_dsr_iix_ss_arrays_fast` |
| **Escalation raw** | Via cli → `compute_escalation_v2` + `compute_escalation_v2_series` |
| **Escalation percentile** | Via cli → `compute_escalation_v2_pct_series` |
| **11 metrics** | Via cli → `compute_market_state_from_df` → `metrics.py` |

*Writes: state_history, latest_state (state_json contains all). Does NOT write escalation_history_v3.*

### 2.3 `scheduler_spy.py`

| Output | Call Chain |
|--------|------------|
| **DSR / IIX / SS** | Same as scheduler.py |
| **Escalation raw** | Same as scheduler.py |
| **Escalation percentile** | Same as scheduler.py |
| **11 metrics** | Same as scheduler.py |

*Writes: state_history, latest_state. Does NOT write escalation_history_v3.*

### 2.4 `validate_regimes.py`

| Output | Call Chain |
|--------|------------|
| **DSR / IIX / SS** | `compute_market_state_from_df(sub, symbol)` per bar → `metrics.py` (single-bar). Arrays built from output for escalation. |
| **Escalation raw** | `compute_escalation_v2(dsr_arr, iix_arr, ss_arr, close_arr, ema_arr)` — arrays from dsr_list, iix_list, ss_list (from metrics per bar) |
| **Escalation percentile** | Not computed (only raw escalation_v2 in output) |
| **11 metrics** | `compute_market_state_from_df(sub, symbol)` per bar → `metrics.py` |

*Output: DataFrame with regime, confidence, dsr, iix, vrs, escalation_v2, etc. No DB.*

### 2.5 `build_audit_bundle.py`

| Output | Call Chain |
|--------|------------|
| **DSR / IIX / SS** | Via `compute_market_state_from_df` + `run_engine_over_history` |
| **Escalation raw** | Via cli (latest) + run_engine_over_history (history) |
| **Escalation percentile** | Via cli when `include_escalation_v2=True` |
| **11 metrics** | Via `compute_market_state_from_df` + `run_engine_over_history` |

*Output: latest_state.json, full_history.csv. No DB.*

---

## 3. DSR / IIX / SS Source

| Source | Module | Function |
|--------|--------|----------|
| **Arrays (for escalation)** | `escalation_fast.py` | `compute_dsr_iix_ss_arrays_fast(df, symbol)` |
| **Single-bar (for 11 metrics)** | `metrics.py` | `compute_downside_shock_risk`, `compute_instability_index`, `compute_structural_score` |

*Both paths use the same metric logic; escalation_fast precomputes series and iterates.*

---

## 4. Escalation Raw → Percentile Flow

```
DSR, IIX, SS arrays
    → compute_escalation_v2_series (percentile-based components, equal-weight)
    → composite series
    → compute_escalation_v2_pct_series (expanding percentile, min 252 bars)
    → esc_pct
    → compute_bucket_from_percentile
```

---

## 5. 11 Metrics (via cli)

| # | Metric | Function (metrics.py) |
|---|--------|------------------------|
| 1 | Market Bias | `compute_market_bias` |
| 2 | Risk Level | `compute_risk_level` |
| 3 | Breakout Up/Down | `compute_breakout_probability` |
| 4 | Downside Shock Risk | `compute_downside_shock_risk` |
| 5 | Structural Score | `compute_structural_score` |
| 6 | Vol Regime | `compute_volatility_regime` |
| 7 | Momentum State | `compute_momentum_state` |
| 8 | Liquidity | `compute_liquidity_context` |
| 9 | Instability Index | `compute_instability_index` |
| 10 | Asymmetry | `compute_asymmetry_metric` |
| 11 | Key Levels | `compute_key_levels` (used by SS, BP) |

---

## 6. Model Logic vs DB Table Mapping (Ambiguity)

| Model Logic | DB Table | Ambiguity |
|-------------|----------|-----------|
| **escalation_v2** | `escalation_history_v3` | Version mismatch: logic=v2, table=v3 |

**Problem:** A third-party auditor sees `escalation_history_v3` and cannot infer that the logic is `escalation_v2` without reading this doc.

---

## 7. Recommendations (Documentation-Only)

### Option A: Add metadata column (minimal, no rename)

Add `model_version` to `escalation_history_v3`:

```sql
ALTER TABLE escalation_history_v3 ADD COLUMN model_version TEXT DEFAULT 'escalation_v2';
```

*Rationale: Single source of truth. No table rename. Backfill existing rows with 'escalation_v2'.*

### Option B: Rename table (breaking)

Rename `escalation_history_v3` → `escalation_v2_history`.

*Rationale: Aligns name with logic. Requires migration and updates to all readers.*

### Option C: Document in schema_version (no schema change)

Add to `schema_version` or manifest: `"escalation_table_model": "escalation_v2"`.

*Rationale: Central metadata. No per-row or table change.*

**Recommended:** Option A. Explicit, queryable, auditor-friendly.

---

## 8. Summary

| Entrypoint | DSR/IIX/SS | Esc Raw | Esc Pctl | 11 Metrics | Writes escalation_history_v3 |
|------------|------------|---------|----------|------------|-----------------------------|
| compute_asset_full | ✓ direct | ✓ direct | ✓ direct | ✓ via cli | ✓ |
| scheduler | ✓ via cli | ✓ via cli | ✓ via cli | ✓ via cli | ✗ |
| scheduler_spy | ✓ via cli | ✓ via cli | ✓ via cli | ✓ via cli | ✗ |
| validate_regimes | ✓ via cli | ✓ direct | ✗ | ✓ via cli | ✗ |
| build_audit_bundle | ✓ via cli | ✓ via cli | ✓ via cli | ✓ via cli | ✗ |

**Model logic:** `escalation_v2` (percentile-based components, expanding window, equal-weight).  
**Storage table:** `escalation_history_v3`.

**Percentile columns:**
- `esc_pctl` / `esc_pctl_expanding`: Production signal (expanding, min 252 bars).
- `esc_pctl_252`, `esc_pctl_504`, `esc_pctl_1260`, `esc_pctl_2520`: Rolling percentiles (trailing windows). Distinct values; not duplicated.
