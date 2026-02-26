# Where We Stand — Architecture & Calculations

**Purpose:** Final summary of the regime-engine architecture, canonical calculations, and current state. Single reference for "where do we stand."

**Date:** 2026-02-26

---

## 1. Architecture Overview

### 1.1 Data Flow

```
Twelve Data API → Parquet (data/assets/{symbol}/bars/{tf}/)
                        ↓
              validate_asset_bars.py
                        ↓
              compute_asset_full.py → compute.db (escalation_history_v3, state_history, latest_state)
```

- **Bars:** Parquet only (canonical). One folder per symbol/timeframe.
- **Compute output:** `data/assets/{symbol}/compute.db`
- **No frozen SQLite:** `--input frozen` deprecated.

### 1.2 Schedulers (Production)

| Scheduler | Assets | Timeframes | Trigger |
|-----------|--------|------------|---------|
| `scheduler_core.py` | core_assets() | 15min, 1h, 4h, 1day, 1week | Every 15 min |
| `scheduler_daily.py` | daily_assets() | 1day, 1week | Once/day (~17:00 EST) |

Both: fetch → Parquet (append) → `compute_asset_full` → compute.db.

### 1.3 Single Canonical Compute Path

| Entrypoint | Role |
|------------|------|
| `compute_asset_full.py` | Full backfill: escalation + state. **Only** writer of escalation_history_v3. |
| `scheduler_*.py` | Invoke compute_asset_full as subprocess when new bars arrive. |

**No dual engines.** Polars regime (`regime_engine_polars.py`) is experimental, non-canonical, marked in METRICS_AUDIT.

---

## 2. Calculations — Canonical Spec

**Reference:** `INSTITUTIONAL_RISK_INTELLIGENCE_STANDARD_V2.md` (v2.2, **LOCKED**)

### 2.1 11 Metrics (metrics.py)

| # | Metric | Output | Key formula |
|---|--------|--------|-------------|
| 1 | Market Bias (MB) | [-1, +1] | tanh(α·T + β·C), T=(EMA_f-EMA_s)/ATR, C=(P-EMA_s)/ATR |
| 2 | Risk Level (RL) | [0, 1] | Weighted: vol ratio, vol delta, drawdown, gap |
| 3 | Breakout Up/Down (BP) | [0, 1] each | Distance to key levels, ATR-normalized |
| 4 | Downside Shock Risk (DSR) | [0, 1] | Tail risk, semi-vol, drawdown, gap |
| 5 | Structural Score (SS) | [0, 1] | Price structure, key levels |
| 6 | Vol Regime (VRS) | [0, 1] | sigma_f/sigma_s, capped 3× |
| 7 | Momentum | State | EMA cross, direction |
| 8 | Liquidity (LQ) | [0, 1] | Volume context |
| 9 | Instability Index (IIX) | [0, 1] | Gap risk, vol acceleration |
| 10 | Asymmetry (ASM) | [-1, 1] | Upside vs downside skew |
| 11 | Key Levels | Used by SS, BP | Support/resistance from pivots |

**Constants:** ATR(20), EMA(20/100), sigma(20/100), peak_window=252. All documented in Standard §4.

### 2.2 Escalation v2

| Step | What |
|------|------|
| 1 | DSR, IIX, SS arrays → `compute_dsr_iix_ss_arrays_fast` |
| 2 | Raw composite from 5 percentile-based components (C1..C5), equal-weight |
| 3 | Expanding percentile of composite → esc_pct |
| 4 | **Production:** Era-conditioned `esc_pctl_era_adj` (Bai–Perron eras, confidence shrinkage) |
| 5 | Buckets: LOW / MED / HIGH from esc_pctl thresholds |

**Percentile:** Midrank `(count_less + (count_equal+1)/2) / n`. Never 0 or 1.

**Era-conditioned:** Percentile within each regime era. Confidence `min(1, bars_in_era / target)`. Shrinkage `0.5 + (p - 0.5) * conf`.

### 2.3 Regime Classifier

Deterministic rules over the 11 metrics → regime label (SHOCK, PANIC_RISK, TRENDING_BULL/BEAR, CHOP_RISK, TRANSITION). Confidence from strength, alignment, momentum, quality scores. Documented in Standard §6.

---

## 3. Alignment Status

| Area | Status |
|------|--------|
| **Standard vs code** | ✓ Locked. Standard V2.2 = production formulas. No divergence. |
| **Percentile** | ✓ Institutional (midrank, expanding, era-conditioned) |
| **Buckets** | ✓ Deterministic thresholds |
| **Metrics** | ✓ All 11 match Standard §4 |
| **Primitives** | ✓ ATR(20), EMA, log returns |
| **Failure modes** | ✓ Documented (ATR=0, flat price, short era → NA) |
| **Reproducibility** | ✓ Same bars + same code → same output |

**MATH_EVALUATION_INSTITUTIONAL_STANDARDS.md** documents full audit. All green.

---

## 4. Performance Baseline

**Benchmark (COST, 1day+1week, M1 MacBook):**

| Step | 1day (9,984 bars) | 1week (2,070 bars) |
|------|-------------------|---------------------|
| Escalation (1–5/5) | ~2–3 min | ~30 s |
| State compute | 401.7 s | 63.0 s |
| **Total** | ~13 min | ~3 min |

**Bottleneck:** Per-bar state compute (`compute_state_history_batch`). Escalation is fast.

**Optimizations in place:** Numba JIT (optional), batch state path, no `.copy()` in loop, batched DB writes.

**Not implemented:** Incremental compute (append new bars only). Deferred for stability; add if needed for scale.

---

## 5. Key Files

| Purpose | File |
|---------|------|
| Metrics | `src/regime_engine/metrics.py` |
| Escalation | `src/regime_engine/escalation_v2.py`, `escalation_fast.py`, `era_production.py` |
| Batch state | `escalation_fast.compute_state_history_batch` |
| CLI (11 metrics) | `src/regime_engine/cli.py` |
| Compute script | `scripts/compute_asset_full.py` |
| Canonical spec | `docs/INSTITUTIONAL_RISK_INTELLIGENCE_STANDARD_V2.md` |

---

## 6. Summary

- **Architecture:** Single canonical path. Parquet → compute_asset_full → compute.db. Schedulers invoke compute; no dual engines.
- **Calculations:** Standard V2.2 locked. All metrics, escalation, percentile, buckets aligned. Institutional-grade.
- **Stability:** Deterministic, documented, failure modes handled.
- **Performance:** ~16 min/symbol (2 TFs) on M1. State compute dominates. Parallel symbols for scale.
