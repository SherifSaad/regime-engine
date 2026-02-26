# Full Math Evaluation — Institutional Standards

**Purpose:** Exhaustive evaluation of equations, metrics, escalation, percentile, buckets, and compute logic against institutional standards. Identifies gaps and recommendations.

**Date:** 2026-02-26  
**Reference:** INSTITUTIONAL_RISK_INTELLIGENCE_STANDARD_V2.md (v2.2, locked), METRICS_AUDIT_INSTITUTIONAL_STANDARD.md

---

## Executive Summary

| Area | Status | Priority |
|------|--------|----------|
| **Percentile** | ✓ Institutional | — |
| **Buckets** | ✓ Aligned | — |
| **Era-conditioned** | ✓ Institutional | — |
| **Escalation flow** | ✓ Aligned | — |
| **Metrics** | ✓ Aligned (Standard V2.2) | — |
| **Confidence formula** | ✓ Documented mapping | — |
| **Failure modes** | ✓ Documented | — |
| **Calibration constants** | ✓ Documented | — |

**Bottom line:** Standard V2.2 (2026-02-26) is **locked** to production formulas. All metrics (MB, RL, DSR, SS, VRS, BP, Momentum, LQ, IIX, ASM, Key Levels) are canonical. Simplified Polars-style metrics moved to deprecated Appendix A.

---

## 1. Percentile

### 1.1 Midrank (Tie Handling)

| Aspect | Standard | Implementation | Status |
|--------|----------|----------------|--------|
| Formula | `(count_less + (count_equal+1)/2) / n` | `midrank_percentile_from_hist` | ✓ Match |
| Never 0 or 1 | Yes (stability) | Yes | ✓ |
| Deterministic | Yes | Yes | ✓ |

**Verdict:** Institutional. Matches scipy.stats.rankdata(method='average').

### 1.2 Expanding vs Rolling

| Mode | Standard | Implementation | Status |
|------|----------|----------------|--------|
| Production | Expanding | `expanding_percentile_transform` | ✓ |
| Min bars | 252 (daily) | `TimeframePolicy.percentile_min_bars()` | ✓ |
| Rolling inclusion | hist includes current bar | `values[start:i+1]` | ✓ |
| Research (deprecated) | Rolling 504 | `rolling_percentile_transform` | ✓ |

**Verdict:** Aligned.

### 1.3 Era-Conditioned (Production)

| Aspect | Standard | Implementation | Status |
|--------|----------|----------------|--------|
| Era boundaries | Asset-class from Bai–Perron | `get_era_bounds_for_symbol` | ✓ |
| Expanding per era | Yes | `expanding_percentile_transform` per era | ✓ |
| Confidence | `min(1, n / target_bars)` | `conf = min(1, bars_in_era / conf_target)` | ✓ |
| Shrinkage | `0.5 + (p - 0.5) * conf` | Same | ✓ |
| Short-era policy | NA for whole segment | NaN, bucket "NA" | ✓ |
| TimeframePolicy | 252 daily, 52 weekly, etc. | `TimeframePolicy(tf)` | ✓ |

**Verdict:** Institutional. Timeframe-consistent, no hardcoded 252 for intraday.

---

## 2. Buckets

| esc_pct | Bucket | Action | Implementation | Status |
|---------|--------|--------|----------------|--------|
| NaN | LOW | NORMAL_SIZE | `"LOW", "NORMAL_SIZE"` | ✓ |
| ≥ 0.85 | HIGH | HEDGE_OR_CASH | Same | ✓ |
| [0.60, 0.85) | MED | REDUCE_40 | Same | ✓ |
| < 0.60 | LOW | NORMAL_SIZE | Same | ✓ |

**Verdict:** Exact match. Deterministic.

---

## 3. Escalation v2

### 3.1 Flow

| Step | Standard | Implementation | Status |
|------|----------|----------------|--------|
| 1 | Raw components C1..C5 | `compute_escalation_v2_series_with_components` | ✓ |
| 2 | Each → expanding percentile | `expanding_percentile_transform` per component | ✓ |
| 3 | Equal-weight aggregate | `(c1+c2+c3+c4+c5)/5` | ✓ |
| 4 | esc_pct = expanding percentile of composite | `compute_escalation_v2_pct_series` | ✓ |
| 5 | Production signal | `esc_pctl_era_adj` (era-conditioned) | ✓ |

**Verdict:** Aligned.

### 3.2 Components

| Component | Standard | Implementation | Status |
|-----------|----------|----------------|--------|
| C1 | DSR level | `c1_raw[t] = dsr[t]` | ✓ |
| C2 | DSR delta | `0.35*(dsr-prev_avg) + 0.65*(dsr-prev_min)` | ✓ |
| C3 | IIX delta | Same blend | ✓ |
| C4 | Structural decay | `max(0, ss_prev_avg - ss)` | ✓ |
| C5 | Divergence accel | `|close-ema|/ema` blend | ✓ |

**Verdict:** Match.

### 3.3 Caps

| Aspect | Standard | Implementation | Status |
|--------|----------|----------------|--------|
| Escalation caps | None (percentile-based) | No hard-coded norm caps | ✓ |
| Component caps | None | Raw values, percentile transform | ✓ |

**Verdict:** Institutional.

---

## 4. Metrics — Aligned (Standard V2.2)

### 4.1 Standard Locked to Production

**Standard V2.2 (2026-02-26)** is locked to production formulas. Section 4 documents MB, RL, DSR, SS, VRS, BP, Momentum, LQ, IIX, ASM, Key Levels, and Breadth Proxy (placeholder) as canonical. **Implementation:** `src/regime_engine/metrics.py` matches the Standard.

### 4.2 Deprecated Simplified Metrics

Appendix A of the Standard contains the former Polars-style 11 metrics (Trend Strength, Vol Regime, etc.) as **deprecated reference only**. Do not use for implementation.

---

## 5. Confidence (Classifier)

### 5.1 Standard Formula

```
raw = 0.20 * trend_strength + 0.22 * alignment + 0.14 * momentum_intensity
    + 0.14 * institutional_quality + 0.10 * liquidity_quality
    + 0.10 * volatility_quality + 0.10 * shock_quality
conf = clip(raw * asymmetry_penalty, 0, 1)
```

### 5.2 Implementation (classifier.py)

```
raw = 0.20 * strength + 0.22 * align + 0.14 * mom_int
    + 0.14 * inst_q + 0.10 * lq_q + 0.10 * vol_q + 0.10 * shock_q
conf = clip(raw * asm_q, 0, 1)
```

| Term | Standard | Implementation | Status |
|------|----------|----------------|--------|
| trend_strength | | strength = 0.55*\|MB\| + 0.45*\|SS\| | ⚠ Different name |
| alignment | | align = MB/SS/mom_dir coherence | ✓ |
| momentum_intensity | | mom_int from state + index | ✓ |
| institutional_quality | | inst_q = 1 - IIX | ✓ (instability inverse) |
| liquidity_quality | | lq_q from LQ value/trend/label | ✓ |
| volatility_quality | | vol_q = 1 - VRS, adjusted by label | ✓ |
| shock_quality | | shock_q = 1 - DSR^1.35 | ✓ |
| asymmetry_penalty | | asm_q = 1 - 0.25*\|ASM\| | ✓ |

**Verdict:** Conceptually aligned. Weights match (0.20, 0.22, 0.14, 0.14, 0.10, 0.10, 0.10). Implementation uses richer inputs (MB, SS, momentum state, etc.). **Acceptable.**

---

## 6. Regime Label Rules

Standard and classifier.py regime rules were compared. **Match:** SHOCK, PANIC_RISK, TRENDING_BULL/BEAR, CHOP_RISK, TRANSITION, guardrails. Implementation is the reference.

---

## 7. Primitives

| Primitive | Standard | features.py | Status |
|-----------|----------|------------|--------|
| EMA | ewm(span=n, adjust=False) | `ewm(span=period, adjust=False).mean()` | ✓ |
| ATR | TR rolling mean, n=20 | `tr.rolling(period).mean()` | ✓ |
| Log returns | ln(close/close.shift(1)) | `np.log(close/close.shift(1))` | ✓ |
| RV | rolling_std * sqrt(252) | `r.rolling(20).std() * sqrt(252)` | ✓ |
| adj_close | For returns | `_close_for_returns` | ✓ |

**Verdict:** Aligned. ATR(20) canonical.

---

## 8. Failure Modes

| Case | Handling | Status |
|------|----------|--------|
| ATR=0 | 1e-12 or return 0 | ✓ |
| First N bars | Min bars check, NaN/0 | ✓ |
| Flat price (max==min) | Structural Score → 0.5 | ✓ |
| Missing volume | Liquidity → 0.5 | ✓ |
| NaN in series | Propagate or skip | ✓ |
| Short era | NA for whole segment | ✓ |

**Verdict:** Documented in Standard V2.1 and METRIC_AND_ESCALATION_CODE §8.

---

## 9. Recommendations Summary

### Addressed (Standard V2.2)

1. **Metric divergence:** Resolved. Standard V2.2 locked to production formulas.
2. **Breadth Proxy:** Marked as placeholder in Standard.
3. **Confidence formula:** Mapping documented in Standard §6.

### Future (Low Priority)

4. **Calibration study:** Consider formal calibration for scaling constants if tail discrimination matters.

### Low Priority

5. **Vol Regime cap:** Consider 5× instead of 3× if extreme regime discrimination is needed.
6. **Drawdown Pressure:** Clarify raw vs scaled (Polars /0.20) in Standard if Polars path is ever canonical.

---

## 10. What Is Already Institutional

- **Percentile:** Midrank, expanding, era-conditioned, confidence shrinkage, TimeframePolicy.
- **Buckets:** Deterministic, documented thresholds.
- **Escalation:** Component-level percentiles, equal-weight, no caps.
- **Primitives:** ATR(20), EMA, log returns, RV.
- **Failure modes:** Documented and handled.
- **Classifier:** Deterministic rules, confidence weights, guardrails.
- **Reproducibility:** Same bars + same code → same output.

---

*End of evaluation. Reference: INSTITUTIONAL_RISK_INTELLIGENCE_STANDARD_V2.md (v2.2), METRICS_AUDIT_INSTITUTIONAL_STANDARD.md, METRIC_AND_ESCALATION_CODE.md.*
