# Canonical Metric Formulas – Institutional Risk Intelligence Standard

**Version:** 2.2 (2026-02-26)

**LOCKED:** This document is the canonical spec. Production code in `src/regime_engine/` must match these formulas. No divergence.

**Objective:** Define the exact, reproducible computation of the production metrics, escalation, and regime classification. Single source of truth.

---

## 1. Input Data Requirements (OHLCV Bars)

**Columns (required, case-sensitive):**

| Column  | Type     | Notes                    |
|---------|----------|--------------------------|
| ts      | datetime | UTC                      |
| open    | float64  |                          |
| high    | float64  |                          |
| low     | float64  |                          |
| close   | float64  |                          |
| volume  | int64    |                          |

**Assumptions:**

- Sorted ascending by ts
- No duplicates on ts
- No gaps (or gaps flagged in validation)
- Timeframe consistent within each df
- Use `adj_close` for return-based metrics when available; else `close`

---

## 2. Glossary (Acronyms)

| Acronym | Full Name |
|---------|-----------|
| **MB** | Market Bias |
| **RL** | Risk Level |
| **BP_up** | Breakout Probability (upside) |
| **BP_dn** | Breakout Probability (downside) |
| **DSR** | Downside Shock Risk |
| **SS** | Structural Score |
| **VRS** | Volatility Regime Score |
| **LQ** | Liquidity (context) |
| **IIX** | Instability Index |
| **ASM** | Asymmetry Metric |
| **er** | Efficiency Ratio (Kaufman) |
| **CMS** | Composite Momentum Score |
| **II** | Impulse Intensity |
| **ATR** | Average True Range |
| **RV** | Realized Volatility (annualized) |

---

## 3. Primitives (Building Blocks)

| Name        | Formula | Window | Notes          |
|-------------|---------|--------|----------------|
| log_returns | `ln(close / close.shift(1))` | — | Use adj_close when available |
| ema(n)      | `series.ewm(span=n, adjust=False).mean()` | n | Exponential moving average |
| tr          | `max(high - low, |high - prev_close|, |low - prev_close|)` | — | True Range |
| atr(n)      | `tr.rolling(n).mean()` | n | Average True Range |
| sigma(n)    | `log_returns.rolling(n).std()` | n | Std of log returns |

**ATR note:** ATR(20) is canonical for all metrics. Do not use ATR(14).

### Canonical Constants

| Constant | Value | Used in |
|----------|-------|---------|
| **ATR period** | **20** | All metrics that use ATR |
| EMA fast | 20 | MB, Momentum, Key Levels |
| EMA slow | 100 | MB, Momentum, Key Levels |
| sigma short | 20 | RL, DSR, VRS |
| sigma long | 100 | RL, VRS |
| peak_window | 252 | RL (drawdown) |
| Escalation percentile | **expanding** (default) | Min 252 bars (or TimeframePolicy) |
| Escalation tie handling | average-rank | `(count_less + (count_equal+1)/2) / n` |

---

## 4. Production Metrics (Canonical Definitions)

**Reference:** `src/regime_engine/metrics.py`

### 4.1 Market Bias (MB)

Output: `[-1, +1]`

```
T = (EMA_f - EMA_s) / ATR_f
C = (P - EMA_s) / ATR_f
MB = clip(tanh(alpha * T + beta * C), -1, 1)
```

- Defaults: `n_f=20`, `n_s=100`, `alpha=0.7`, `beta=0.3`
- Min bars: `n_s + 5`
- ATR=0: return 0

### 4.2 Risk Level (RL)

Output: `[0, 1]`

```
A = clip(sigma_f / sigma_s, 0, A_max) / A_max
B = clip((sigma_f - sigma_f_prev) / sigma_f, 0, B_max) / B_max
C1 = clip((EMA_s - P) / ATR_f, 0, C1_max) / C1_max
C2 = clip(DD / DD_max, 0, 1)   where DD = (Peak - P) / Peak, Peak = rolling_max(adj_close, peak_window)
D = clip(|Open - PrevClose| / ATR_f, 0, D_max) / D_max
C = 0.5*C1 + 0.5*C2
RL = clip(w_A*A + w_B*B + w_C*C + w_D*D, 0, 1)
```

- Defaults: `peak_window=252`, `A_max=3`, `B_max=0.5`, `C1_max=3`, `DD_max=0.20`, `D_max=2`
- Weights: `w_A=0.35`, `w_B=0.20`, `w_C=0.35`, `w_D=0.10`

### 4.3 Breakout Probability (BP_up, BP_dn)

Output: `[0, 1]` each

```
d_up = (L_up - P) / ATR_f
d_dn = (P - L_dn) / ATR_f
D_up = exp(-k * d_up)
D_dn = exp(-k * d_dn)

Comp = clip(1 - ATR_short/ATR_long, 0, 1)
Exp = clip(ATR_short/ATR_short_prev - 1, 0, 1)
E = 0.6*Comp + 0.4*Exp

A_up = (1 + MB) / 2
A_dn = (1 - MB) / 2
R = 1 - RL
H = clip(1 - sigma_f/sigma_cap, 0, 1)

BP_up = clip(D_up * (0.45E + 0.35A_up + 0.20R) * (0.6H + 0.4), 0, 1)
BP_dn = clip(D_dn * (0.45E + 0.35A_dn + 0.20R) * (0.6H + 0.4), 0, 1)
```

- Key levels: `L_up`, `L_dn` from Key Levels; fallback `rolling_max(high,50)`, `rolling_min(low,50)`
- ATR: `atr_short_n=10`, `atr_long_n=50`, `sigma_cap=0.035`

### 4.4 Downside Shock Risk (DSR)

Output: `[0, 1]`

```
tau = m * sigma_f
A_tail = 1 - exp(-lam * freq(r < -tau))   over last H bars
B = clip(sigma_minus / sigma_plus, 0, B_max) / B_max
C = clip((EMA_s - P) / ATR_f, 0, C_max) / C_max
D = clip(-g, 0, D_max) / D_max   where g = (Open - PrevClose) / ATR_f

DSR_raw = clip(w1*A_tail + w2*B + w3*C + w4*D + w5*RL, 0, 1)
Bear = (1 - MB) / 2
DSR = clip(DSR_raw * (0.6 + 0.4*Bear), 0, 1)
```

- Defaults: `H=60`, `m=2.5`, `lam=30`, `B_max=2`, `C_max=3`, `D_max=2`
- Weights: `w1=0.30`, `w2=0.20`, `w3=0.20`, `w4=0.10`, `w5=0.20`

### 4.5 Structural Score (SS)

Output: `[-1, +1]`

```
ER = |P - P[n_c]| / sum(|P[i] - P[i-1]| over n_c)   # Kaufman efficiency ratio, adj_close
Stab = 1 - (0.6*RL + 0.4*DSR)
H_sup = tanh((P - S1) / ATR_f)   # S1 = nearest support
H_res = tanh((R1 - P) / ATR_f)   # R1 = nearest resistance
C = 0.6*s1*H_sup + 0.4*r1*H_res   # s1, r1 = strengths from Key Levels

SS = clip(MB*(0.55 + 0.25*ER + 0.20*Stab) + 0.25*C, -1, 1)
```

- Key Levels: pivot/VAP/round-number logic; see `compute_key_levels`
- Fallback: no supports/resistances → C=0

### 4.6 Volatility Regime (VRS)

Output: `[0, 1]` + label (CALM, NORMAL, ELEVATED, STRESSED)

```
VR = sigma_f / sigma_s
AR = ATR_short / ATR_long
A = clip(VR, 0, 3) / 3
B = clip(AR, 0, 2) / 2
C = RL
vrs = clip(0.50*A + 0.30*B + 0.20*C, 0, 1)
```

- Labels: CALM (<0.25), NORMAL (<0.45), ELEVATED (<0.70), STRESSED (≥0.70)

### 4.7 Momentum State

Output: state (STRONG_UP_IMPULSE, WEAK_UP_DRIFT, NEUTRAL_RANGE, etc.), CMS `[-1,1]`, II `[0,1]`, ER `[0,1]`

```
M = (P - P[n_m]) / ATR_f
ER = net_move / sum(|diffs|) over n_c
CMS = clip(0.50*MB + 0.30*tanh(M/k_m) + 0.20*SS, -1, 1)
II = |CMS| * (0.6*ER + 0.4*(1-VRS)) * (0.7*|BP_up-BP_dn| + 0.3)
```

- State rules: thresholds on CMS and II (see `classifier.py` / `compute_momentum_state`)

### 4.8 Liquidity (LQ)

Output: `[0, 1]` + label (DEEP, NORMAL, THIN)

```
RDV = DV / SMA(DV, n_dv)   # dollar volume
A = clip(RDV, 0, 2) / 2
B = 1 - VRS
C = 1 - clip(GapAbs/2, 0, 1)   # gap penalty
D = ER
LQ = clip(0.45*A + 0.25*B + 0.15*C + 0.15*D, 0, 1)
```

- Fallback: no volume → A=0.5 (neutral)

### 4.9 Instability Index (IIX)

Output: `[0, 1]`

```
A = VRS
B = 0.6*RL + 0.4*DSR
C = 1 - LQ
D = 1 - ER
E = clip(GapAbs, 0, 2) / 2   where GapAbs = |Open - PrevClose| / ATR_f
K = clip(dVRS, 0, 0.10) / 0.10

IIX = clip(0.25*A + 0.25*B + 0.20*C + 0.15*D + 0.15*E, 0, 1)
IIX = clip(IIX + 0.10*K, 0, 1)
```

### 4.10 Asymmetry (ASM)

Output: `[-1, +1]`

```
A = BP_up - BP_dn
B = -DSR
SkewVol = sigma_minus / sigma_plus
C = -tanh(gamma * ln(SkewVol))
Amp = 0.5 + 0.5*IIX

ASM_raw = 0.45*A + 0.15*MB + 0.20*C + 0.20*B
if ASM_raw < 0:  ASM = clip(ASM_raw * Amp, -1, 1)
else:             ASM = clip(ASM_raw, -1, 1)
```

### 4.11 Key Levels

Output: `{supports: [{price, strength}], resistances: [{price, strength}]}`

- Evidence: pivot highs/lows, volume-at-price, round numbers
- Clustering: single-link within epsilon (eta*ATR)
- See `compute_key_levels` in metrics.py

### 4.12 Breadth Proxy

**PLACEHOLDER** until real breadth (advancers/decliners) available. Mark as placeholder in output.

---

## 5. Escalation v2

### Production Mode (default)

**Production signal:** `esc_pctl_era_adj` (era-conditioned, confidence shrinkage). See METRIC_AND_ESCALATION_CODE.md §7a.

**Flow:**
1. Raw components: C1=DSR level, C2=DSR delta, C3=IIX delta, C4=struct decay, C5=div accel
2. Each component → **expanding percentile** (min_bars from TimeframePolicy)
3. **Equal-weight** aggregate: `(c1 + c2 + c3 + c4 + c5) / 5`
4. Per era: expanding percentile of composite → confidence shrinkage → `esc_pctl_era_adj`

```
esc_composite[i] = mean( pct(C1[i]), pct(C2[i]), pct(C3[i]), pct(C4[i]), pct(C5[i]) )
esc_pctl_era_adj = 0.5 + (p - 0.5) * conf   # conf = min(1, bars_in_era / target)
esc_bucket =
  NaN     → "NA"
  ≥ 0.85  → "HIGH"   → "HEDGE_OR_CASH"
  [0.60, 0.85) → "MED"    → "REDUCE_40"
  < 0.60  → "LOW"    → "NORMAL_SIZE"
```

**Tie handling:** `rank = (count_less + (count_equal + 1) / 2) / n`

### Caps

**Escalation:** No hard-coded normalization caps; percentile-based scaling only.

---

## 6. Regime Classifier (Confidence + Label)

### Confidence (0–1)

**Reference:** `src/regime_engine/classifier.py` `compute_confidence`

```
strength = 0.55*|MB| + 0.45*|SS|
align = coherence of MB, SS, momentum direction
mom_int = from momentum state + index
inst_q = 1 - IIX
lq_q = from LQ value, trend, label
vol_q = 1 - VRS (adjusted by label)
shock_q = 1 - DSR^1.35
asm_q = 1 - 0.25*|ASM|

raw = 0.20*strength + 0.22*align + 0.14*mom_int + 0.14*inst_q + 0.10*lq_q + 0.10*vol_q + 0.10*shock_q
conf = clip(raw * asm_q, 0, 1)
```

*Mapping: trend_strength↔strength, alignment↔align, momentum_intensity↔mom_int, institutional_quality↔inst_q, liquidity_quality↔lq_q, volatility_quality↔vol_q, shock_quality↔shock_q, asymmetry_penalty↔asm_q.*

### Regime Label (Deterministic Rules)

**Priority order:** SHOCK > PANIC_RISK > TRENDING > CHOP_RISK > TRANSITION

| Regime | Condition |
|--------|-----------|
| **SHOCK** | (DSR≥0.70 AND (IIX≥0.70 OR RL≥0.75) AND VRS≥0.60 AND MB≤-0.25 AND SS≤-0.25) OR DSR≥0.80 OR (VRS≥0.75 AND IIX≥0.65) |
| **PANIC_RISK** | DSR≥0.65 OR IIX≥0.65 OR (VRS≥0.60 AND LQ_quality≤0.45) |
| **TRENDING_BULL** | MB≥0.55 AND SS≥0.40 AND mom_dir≥0 AND align≥0.70 AND IIX≤0.55 |
| **TRENDING_BEAR** | MB≤-0.55 AND SS≤-0.40 AND mom_dir≤0 AND align≥0.70 AND IIX≤0.55 |
| **TRENDING_BEAR** (soft) | MB≤-0.35 AND SS≤-0.25 AND conf≥0.45 |
| **CHOP_RISK** | (\|MB\|≤0.25 AND \|SS\|≤0.25 AND mom_int≤0.45) OR (align≤0.45 AND mom_int≤0.45 AND max(BP_up,BP_dn)≤0.55) |
| **TRANSITION_BREAKOUT_SETUP** | else AND max(BP_up, BP_dn)≥0.62 |
| **TRANSITION** | else |

**Guardrail:** If regime is TRENDING_BULL or TRENDING_BEAR and conf<0.65, downgrade to TRANSITION (except soft TRENDING_BEAR with conf≥0.45).

---

## 7. Compute Order (Dependencies)

1. MB, RL (no deps)
2. Vol Regime (needs RL)
3. Key Levels
4. BP_up, BP_dn (needs MB, RL, Key Levels)
5. DSR (needs MB, RL)
6. SS (needs MB, RL, DSR, Key Levels)
7. Momentum (needs MB, SS, VRS, BP)
8. Liquidity (needs VRS, momentum.er)
9. IIX (needs RL, DSR, VRS, LQ, er)
10. ASM (needs BP, DSR, MB, IIX)
11. Escalation v2 (needs DSR, IIX, SS arrays, close, EMA)

---

## 8. Canonical Output Schema

### latest_state (JSON in compute.db)

```json
{
  "regime_label": "TRENDING_BULL",
  "confidence": 0.78,
  "escalation_bucket": "MED",
  "esc_pctl_era_adj": 0.68,
  "metrics": { "market_bias": 0.55, "risk_level": 0.22, ... },
  "classification": { ... },
  "computed_at": "2026-02-25T14:30:00Z",
  "bar_count_used": 8323,
  "last_ts": "2026-02-24T16:00:00Z"
}
```

*Breadth Proxy: mark as placeholder in output until real breadth data available.*

---

## 9. Hard-Coded Caps (Metrics Only)

| Cap | Value | Justification |
|-----|-------|---------------|
| RL: A_max | 3 | Vol ratio >3× is extreme |
| RL: DD_max | 0.20 | 20% drawdown = stress threshold |
| RL: D_max | 2 | Gap >2 ATR = outlier |
| DSR: B_max | 2 | Semi-vol ratio cap |
| DSR: C_max, D_max | 3, 2 | ATR-normalized |
| VRS: VR cap | 3× | Vol regime saturation |
| IIX: GapAbs | 2 | ATR units |
| IIX: dVRS | 0.10 | Acceleration kicker |

---

## Summary

**This document is LOCKED. Production code must match.**

- All paths (scheduler, backfill, per-symbol) use these exact formulas.
- No dummy/fallback values in production.
- **Gap Risk:** Use 0 when first bar or open==prev_close.
- **Breadth Proxy:** Placeholder until real breadth data available.

---

## Appendix A: Deprecated Simplified Metrics (Reference Only)

**DEPRECATED.** The following Polars-style formulas do **not** match production. Kept for historical reference. Do not use for implementation.

| # | Name | Deprecated Formula |
|---|------|-------------------|
| 1 | Trend Strength | `clip((close - ema(20)) / atr(20) * 0.2 + 0.5, 0, 1)` |
| 2 | Vol Regime | `clip(rv(20)/rv(100), 0, 3) / 3` |
| 3 | Drawdown Pressure | `clip((rolling_max(252) - close) / (rolling_max(252) + 1e-12), 0, 1)` |
| 4 | Downside Shock | `clip(-(close - rolling_min(20)) / (atr(20) + 1e-12) * 10, 0, 1)` |
| 5 | Asymmetry / Skew | `clip(neg_std/pos_std, 0, 4) / 4` |
| 6 | Momentum State | `clip((ema20 - ema100) / atr(20) * 2 + 0.5, 0, 1)` |
| 7 | Structural Score | `clip((close - min252) / (max252 - min252 + 1e-12), 0, 1)` |
| 8 | Liquidity | `clip(volume / (volume.rolling_mean(20) + 1), 0, 3) / 3` |
| 9 | Gap Risk | `clip(abs(open - prev_close) / (atr(20) + 1e-12), 0, 2) / 2` |
| 10 | Key-Level Pressure | `clip(drawdown * (close < ema100), 0, 1)` |
| 11 | Breadth Proxy | `clip(trend_strength * (close > ema20), 0, 1)` |

*Production uses MB, RL, DSR, SS, VRS, BP, Momentum, LQ, IIX, ASM, Key Levels. See Section 4.*
