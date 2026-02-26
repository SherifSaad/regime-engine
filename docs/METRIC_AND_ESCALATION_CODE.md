# Metric Calculations & Escalation Percentile — Code Reference

**Purpose:** Code-level reference for the 11 metrics, escalation v2, percentile transforms, and production constants. Use when implementing or auditing the compute engine.

**Source:** `src/regime_engine/metrics.py`, `escalation_v2.py`, `escalation_fast.py`, `escalation_buckets.py`, `features.py`

---

## Production vs Research Mode

| Aspect | **Production Mode** (default) | **Research Mode** |
|--------|-------------------------------|-------------------|
| Percentile transform | **Expanding** (full history) | Rolling (deprecated) |
| Default | `expanding_percentile_transform` | `rolling_percentile_transform` |
| Use case | Live, backfill, institutional | Backtests, experiments only |
| Min sample | **252 bars** before output | Window-dependent (e.g. 504) |
| Normalization caps | **None** (percentile-based) | Legacy fixed ranges |

**Production Mode** is the institutional standard. Research Mode is deprecated for production use.

---

## 1. Core Helpers

```python
def _close_for_returns(df: pd.DataFrame) -> pd.Series:
    """Use adj_close for return-based metrics when available; else raw close."""
    return df["adj_close"] if "adj_close" in df.columns else df["close"]

def clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))
```

---

## 2. Metric Calculations

### Market Bias (MB)

```
MB_t = tanh(alpha * T_t + beta * C_t)
T_t = (EMA_f - EMA_s) / ATR_f
C_t = (P - EMA_s) / ATR_f
```

- Defaults: `n_f=20`, `n_s=100`, `alpha=0.7`, `beta=0.3`
- Output: `[-1, +1]`

### Risk Level (RL)

```
A = clip(sigma_f / sigma_s, 0, A_max) / A_max
B = clip((sigma_f - sigma_f_prev) / sigma_f, 0, B_max) / B_max
C1 = clip((EMA_s - P) / ATR_f, 0, C1_max) / C1_max
C2 = clip(DD / DD_max, 0, 1)   where DD = (Peak - P) / Peak
D = clip(|Open - PrevClose| / ATR_f, 0, D_max) / D_max
RL = clip(w_A*A + w_B*B + w_C*C + w_D*D, 0, 1)
```

- Defaults: `peak_window=252`, `A_max=3`, `B_max=0.5`, `C1_max=3`, `DD_max=0.20`, `D_max=2`
- Weights: `w_A=0.35`, `w_B=0.20`, `w_C=0.35`, `w_D=0.10`
- Output: `[0, 1]`

### Breakout Probability (BP_up, BP_dn)

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

- Key levels: `L_up = rolling_max(high, 50)`, `L_dn = rolling_min(low, 50)` if not provided
- ATR windows: `atr_short_n=10`, `atr_long_n=50`

### Downside Shock Risk (DSR)

```
tau = m * sigma_f
A_tail = 1 - exp(-lam * freq(r < -tau))
B = clip(sigma_minus / sigma_plus, 0, B_max) / B_max
C = clip((EMA_s - P) / ATR_f, 0, C_max) / C_max
D = clip(-g, 0, D_max) / D_max   where g = (Open - PrevClose) / ATR_f

DSR_raw = clip(w1*A_tail + w2*B + w3*C + w4*D + w5*RL, 0, 1)
Bear = (1 - MB) / 2
DSR = clip(DSR_raw * (0.6 + 0.4*Bear), 0, 1)
```

- Defaults: `H=60`, `m=2.5`, `lam=30`, `B_max=2`, `C_max=3`, `D_max=2`
- Weights: `w1=0.30`, `w2=0.20`, `w3=0.20`, `w4=0.10`, `w5=0.20`

### Structural Score (SS)

```
ER = |P - P[n_c]| / sum(|P[i] - P[i-1]| over n_c)
Stab = 1 - (0.6*RL + 0.4*DSR)
C = 0.6*s1*tanh((P - S1)/ATR_f) + 0.4*r1*tanh((R1 - P)/ATR_f)
SS = clip(MB*(0.55 + 0.25*ER + 0.20*Stab) + 0.25*C, -1, 1)
```

- S1, R1 from Key Levels (supports/resistances)
- Output: `[-1, +1]`

### Volatility Regime (VRS)

```
VR = sigma_f / sigma_s
AR = ATR_short / ATR_long
A = clip(VR, 0, 3) / 3
B = clip(AR, 0, 2) / 2
C = RL
vrs = clip(0.50*A + 0.30*B + 0.20*C, 0, 1)
```

- Labels: `CALM` (<0.25), `NORMAL` (<0.45), `ELEVATED` (<0.70), `STRESSED` (≥0.70)

### Instability Index (IIX)

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

### Asymmetry (ASM)

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

---

## 3. Escalation v2 (Production Mode)

**Inputs:** DSR, IIX, SS arrays; close, EMA arrays

**Flow:**
1. Compute raw components (**no hard-coded normalization caps**)
2. Transform each to **expanding percentile** (default)
3. **Equal-weight** aggregate: `(c1 + c2 + c3 + c4 + c5) / 5`
4. Final `esc_pct` = expanding percentile of composite

**Components (raw → percentile):**

| Component | Raw formula |
|-----------|-------------|
| C1 | DSR level |
| C2 | DSR delta: `0.35*(dsr - prev_avg) + 0.65*(dsr - prev_min)` |
| C3 | IIX delta: same blend |
| C4 | Structural decay: `max(0, ss_prev_avg - ss_now)` |
| C5 | Divergence accel: `\|close-ema\|/ema` blend |

**Windows:** `w_dsr_delta=10`, `w_iix_delta=5`, `w_struct_prev=10`, `w_div_prev=5`

---

## 4. Escalation Percentile Transform

**Default: expanding-window** (Production Mode)

```python
def expanding_percentile_transform(series: pd.Series, min_bars: int = 252) -> pd.Series
```

| Parameter | Value | Justification |
|-----------|-------|---------------|
| **Percentile mode** | **expanding** (default) | Full history; no arbitrary window |
| **Min sample** | **252 bars** | 1 trading year; stable rank distribution |
| **Tie handling** | **average-rank** | Deterministic; matches scipy.stats.rankdata(method='average') |

**Tie-handling formula:**
```
rank = (count_less + (count_equal + 1) / 2) / n
```
For ties, each tied value receives the average of the ranks it would occupy. Example: three values tie for ranks 2,3,4 → each gets (2+3+4)/3 = 3.

### 4a. Rolling Percentile — Inclusion Rule (Canonical)

**Rule:** The rolling window **includes the current bar** in the ranking history.

```
start = max(0, i - window + 1)
hist = values[start : i + 1]   # current bar at index i is INCLUDED
pctl[i] = midrank_percentile_from_hist(hist, values[i])
```

- **Not lookahead:** Only data available at time `i` (inclusive) is used.
- **Canonical:** All rolling percentile implementations must use this rule to avoid divergence.
- **Output:** NaN until `len(hist) >= window`.

---

## 5. Escalation Bucket (from Percentile)

| esc_pct | Bucket | Action |
|---------|--------|--------|
| NaN | LOW | NORMAL_SIZE |
| ≥ 0.85 | HIGH | HEDGE_OR_CASH |
| [0.60, 0.85) | MED | REDUCE_40 |
| < 0.60 | LOW | NORMAL_SIZE |

---

## 6. Pipeline Flow

1. **`compute_dsr_iix_ss_arrays_fast(df)`** → DSR, IIX, SS arrays (bars 20..n-1)
2. **`compute_escalation_v2_series(...)`** → composite (percentile-based components, equal-weight)
3. **`compute_escalation_v2_pct_series(composite, min_bars=252)`** → expanding percentile
4. **`compute_bucket_from_percentile(esc_pct)`** → bucket + action

---

## 7. Canonical Constants (from Standard V2)

| Constant | Value |
|----------|-------|
| ATR period | 20 |
| EMA fast | 20 |
| EMA slow | 100 |
| RV short | 20 |
| RV long | 100 |
| Rolling max/min | 252 |
| Escalation percentile | **expanding** (default), min **252** bars |
| Rolling percentiles (DB) | 252, 504, 1260, 2520 bars (trailing windows) |

*Production signal: `esc_pctl_expanding`. Rolling columns (`esc_pctl_252`, etc.) are distinct, not duplicated.*

---

## 7a. Era-Conditioned Percentile (Standard V2.1 — Production)

**Source:** `scripts/compute_asset_full.py`, `src/regime_engine/standard_v2_1.py`

| Source | Description |
|-------|-------------|
| **Primary** | `data/era_metadata/era_boundaries.csv` — asset-class boundaries from `detect_eras_bai_perron.py` |
| **Fallback** | Hard-coded `ERAS_LEGACY` (pre2010, 2010_2019, 2020plus) when metadata missing |

**Logic:** For each era `[start, end)`, mask bars and compute **expanding percentile** within the era (min_bars from `TimeframePolicy.percentile_min_bars()`). Symbol → era asset class via `SYMBOL_TO_ERA_ASSET_CLASS` or `UNIVERSE_AC_TO_ERA_AC` fallback.

**Confidence:** `conf = min(1, bars_in_era / CONF_TARGET)` where `CONF_TARGET = TimeframePolicy(tf).bars_per_trading_year()` (252 daily, 52 weekly, 6552 for 15min, etc.).

**Shrinkage:** `p_adj = 0.5 + (p - 0.5) * conf`. Low confidence → neutral (0.5); full confidence → raw percentile.

**Production:** `esc_pctl_era_adj` is the production signal. Buckets use it. `esc_pctl_expanding` is comparison only.

### 7a.1 Short-Era Behavior Policy (Edge Case)

**When era segment length < PCTL_MIN_BARS:** The expanding percentile within that era never meets the min-bars gate. Result: `esc_pctl_era` and `esc_pctl_era_adj` are **NaN for the entire segment**; buckets are **"NA"**.

**Policy (canonical):** NA for the whole short era. Do not force neutral 0.5. Rationale: insufficient history to make any percentile-based decision; explicit NA is more honest than implying a neutral stance.

| Era length | Behavior |
|------------|----------|
| < PCTL_MIN_BARS | esc_pctl_era = NaN, esc_pctl_era_adj = NaN, bucket = "NA" |
| ≥ PCTL_MIN_BARS | Normal: percentile + confidence shrinkage |

---

## 8. Hard-Coded Caps (Metrics Only)

Escalation uses **no hard-coded normalization caps**; scaling is percentile-based.

Underlying metrics (RL, DSR, VRS, etc.) retain caps for numerical stability and domain bounds:

| Cap | Value | Justification |
|-----|-------|---------------|
| RL: A_max | 3 | Vol ratio >3× is extreme; saturates signal |
| RL: DD_max | 0.20 | 20% drawdown = stress threshold (institutional) |
| RL: D_max | 2 | Gap >2 ATR = outlier; clip for robustness |
| DSR: B_max | 2 | Semi-vol ratio cap; tail dominance |
| DSR: C_max, D_max | 3, 2 | ATR-normalized; same rationale as RL |
| VRS: VR cap | 3× | Vol regime saturation |
| IIX: GapAbs | 2 | ATR units; consistent with gap risk |
| IIX: dVRS | 0.10 | Acceleration kicker; avoid spikes |

*Calibration study may justify alternative values; document in audit.*

---

## 9. Performance (Vectorization)

| Component | Optimization | Notes |
|-----------|--------------|-------|
| `expanding_percentile_transform` | Numba JIT when `numba` installed (`pip install regime-engine[perf]`) | Same midrank math; ~10–50× faster |
| `rolling_percentile_transform` | Numba JIT when available | Same canonical inclusion rule |
| `run_state_tf` | `compute_state_history_batch` single-pass | One loop over bars; no per-bar escalation recompute |
| State loop | No `.copy()` on `df.iloc[:i+1]` | View only; metrics do not mutate |

Batch path: `escalation_fast.compute_state_history_batch` precomputes series once and iterates with indexing. Uses `esc_pctl` from `escalation_history_v3` for bucket; no escalation recompute per bar.
