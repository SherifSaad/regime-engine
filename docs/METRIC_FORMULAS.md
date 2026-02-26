# Metric Formulas – Exact Specifications

**Purpose:** Exact formulas for all 11 metrics and primitives. Deterministic, no ML. Use when implementing or verifying metric math.

All formulas as implemented in the regime-engine codebase.

---

## 1. Primitive Indicators (from `features.py`)

### EMA (Exponential Moving Average)
```
EMA(series, period) = series.ewm(span=period, adjust=False).mean()
```

### Log Returns
```
r_t = ln(close_t / close_{t-1})
```

### ATR (Average True Range)
```
TR_t = max( high - low, |high - prev_close|, |low - prev_close| )
ATR_t = mean(TR over last `period` bars)
```
**Canonical: period=20 for all 11 metrics.** (features.py default=14 is legacy; metrics.py passes n_f=20.)

### Realized Volatility (annualized)
```
sigma = std(log_returns, window) * sqrt(252)
```

---

## 2. Core Metrics (from `metrics.py`)

### 2.1 Market Bias (MB) — range [-1, +1]
```
T_t = (EMA_fast - EMA_slow) / ATR_fast
C_t = (P - EMA_slow) / ATR_fast
MB_t = tanh(alpha * T_t + beta * C_t)
```
- Default: n_f=20, n_s=100, alpha=0.7, beta=0.3
- clamp(MB, -1, 1)

---

### 2.2 Risk Level (RL) — range [0, 1]
```
A = clip(sigma_fast / sigma_slow, 0, A_max) / A_max          # vol level
B = clip((sigma_fast - sigma_fast_prev) / sigma_fast, 0, B_max) / B_max   # vol expansion
C1 = clip((EMA_slow - P) / ATR_fast, 0, C1_max) / C1_max     # below-trend stress
C2 = clip(DD / DD_max, 0, 1)   where DD = (Peak - P) / Peak  # drawdown stress
  Peak = rolling_max(adj_close, peak_window)
C = 0.5 * C1 + 0.5 * C2
D = clip(|Open - PrevClose| / ATR_fast, 0, D_max) / D_max    # gap shockiness

RL = clip(w_A*A + w_B*B + w_C*C + w_D*D, 0, 1)
```
- Defaults: A_max=3, B_max=0.5, C1_max=3, DD_max=0.20, D_max=2
- Weights: w_A=0.35, w_B=0.20, w_C=0.35, w_D=0.10
- peak_window=252

---

### 2.3 Breakout Probability (BP_up, BP_dn) — range [0, 1]
```
L_up = rolling_max(high, level_lookback)   # or key_levels resistance
L_dn = rolling_min(low, level_lookback)    # or key_levels support

d_up = max(0, (L_up - P) / ATR_fast)
d_dn = max(0, (P - L_dn) / ATR_fast)
D_up = exp(-k * d_up)
D_dn = exp(-k * d_dn)

Comp = clip(1 - ATR_short/ATR_long, 0, 1)
Exp  = clip(ATR_short/ATR_short_prev - 1, 0, 1)
E = 0.6*Comp + 0.4*Exp

A_up = (1 + MB) / 2
A_dn = (1 - MB) / 2
R = 1 - RL

H = clip(1 - sigma_fast/sigma_cap, 0, 1)   # sigma_cap=0.035

BP_up = clip(D_up * (0.45*E + 0.35*A_up + 0.20*R) * (0.6*H + 0.4), 0, 1)
BP_dn = clip(D_dn * (0.45*E + 0.35*A_dn + 0.20*R) * (0.6*H + 0.4), 0, 1)
```
- level_lookback=50, k=1.0, atr_short_n=10, atr_long_n=50

---

### 2.4 Downside Shock Risk (DSR) — range [0, 1]
```
tau = m * sigma_fast   # m=2.5, sigma_fast = std(log_returns, n_f)

A_tail = 1 - exp(-lam * A)   where A = mean(I[r < -tau]) over last H bars, lam=30
B = clip(sigma_minus / sigma_plus, 0, B_max) / B_max   # semi-vol ratio, H bars
C = clip((EMA_slow - P) / ATR_fast, 0, C_max) / C_max
D = clip(-g, 0, D_max) / D_max   where g = (Open - PrevClose) / ATR_fast

DSR_raw = clip(w1*A_tail + w2*B + w3*C + w4*D + w5*RL, 0, 1)
Bear = (1 - MB) / 2
DSR = clip(DSR_raw * (0.6 + 0.4*Bear), 0, 1)
```
- Defaults: H=60, m=2.5, lam=30, B_max=2, C_max=3, D_max=2
- Weights: w1=0.30, w2=0.20, w3=0.20, w4=0.10, w5=0.20

---

### 2.5 Key Levels (KL) — returns supports/resistances
```
Pivot high: high[t] == max(high[t-k:t+k])
Pivot low:  low[t] == min(low[t-k:t+k])

For each pivot level L:
  T = 1 - exp(-touch_count / tau_T)   # touches: |close - L|/ATR <= delta
  R = clip(rejection_mean / R_max, 0, 1)   # move away over h bars
  Q = exp(-age / tau_Q)   # recency
  score = 0.5*T + 0.3*R + 0.2*Q

Merge: volume-at-price peaks, round numbers. Cluster within eps=eta*ATR.
Classify: L < P → support, L > P → resistance. Keep top N by strength.
```
- W=250, k=3, eta=0.35, delta=0.30, tau_T=3, h=5, R_max=2, N=3, min_strength=0.35

---

### 2.6 Structural Score (SS) — range [-1, +1]
```
ER = |P - P[n_c]| / sum(|P[i]-P[i-1]| over last n_c)   # Kaufman efficiency ratio
Stab = 1 - (0.6*RL + 0.4*DSR)

H_sup = tanh((P - S1) / ATR_fast)   # S1 = nearest support
H_res = tanh((R1 - P) / ATR_fast)   # R1 = nearest resistance
C = 0.6*s1*H_sup + 0.4*r1*H_res   # s1, r1 = strengths

SS = clip(MB * (0.55 + 0.25*ER + 0.20*Stab) + 0.25*C, -1, 1)
```
- n_c=20

---

### 2.7 Volatility Regime (VRS) — range [0, 1]
```
VR = sigma_fast / sigma_slow
AR = ATR_short / ATR_long

A = clip(clip(VR, 0, 3) / 3, 0, 1)
B = clip(clip(AR, 0, 2) / 2, 0, 1)
C = RL

VRS = clip(0.50*A + 0.30*B + 0.20*C, 0, 1)

Labels: VRS<0.25→CALM, <0.45→NORMAL, <0.70→ELEVATED, else STRESSED
Trend: dVRS >= 0.03→RISING, <= -0.03→FALLING, else FLAT
```

---

### 2.8 Momentum State — returns {state, cms, ii, er}
```
M = (P - P[n_m]) / ATR_fast   # n_m=20
ER = |P - P[n_c]| / sum(|diffs| over n_c)   # efficiency ratio

CMS = clip(0.50*MB + 0.30*tanh(M/k_m) + 0.20*SS, -1, 1)   # k_m=2

Align = BP_up - BP_dn
II = |CMS| * (0.6*ER + 0.4*(1-VRS)) * (0.7*|Align| + 0.3)

States:
  CMS>=0.55 and II>=0.50 → STRONG_UP_IMPULSE
  CMS>=0.20 and II<0.50  → WEAK_UP_DRIFT
  |CMS|<0.20             → NEUTRAL_RANGE
  CMS<=-0.55 and II>=0.50 → STRONG_DOWN_IMPULSE
  CMS<=-0.20 and II<0.50  → WEAK_DOWN_DRIFT
```

---

### 2.9 Liquidity Context (LQ) — range [0, 1]
```
DV = volume * close
RDV = DV_t / SMA(DV, n_dv)

A = clip(clip(RDV, 0, 2) / 2, 0, 1)   # relative dollar volume
B = 1 - VRS                            # volatility burden
C = 1 - clip(|Open - PrevClose|/ATR_fast, 0, 2)/2   # gap penalty (inverted)
D = ER                                 # choppiness proxy

LQ = clip(0.45*A + 0.25*B + 0.15*C + 0.15*D, 0, 1)

Labels: LQ>=0.70→DEEP, >=0.40→NORMAL, else THIN
Trend: delta vs SMA(LQ, h), ±0.05 → IMPROVING/DETERIORATING
```
- n_dv=20, h=5

---

### 2.10 Instability Index (IIX) — range [0, 1]
```
A = VRS
B = 0.6*RL + 0.4*DSR
C = 1 - LQ
D = 1 - ER
E = clip(|Open - PrevClose|/ATR_fast, 0, 2) / 2

# Acceleration kicker
dVRS = VRS_now - VRS_prev
K = clip(clip(dVRS, 0, 0.10) / 0.10, 0, 1)

IIX = clip(0.25*A + 0.25*B + 0.20*C + 0.15*D + 0.15*E, 0, 1)
IIX = clip(IIX + 0.10*K, 0, 1)
```

---

### 2.11 Asymmetry Metric (ASM) — range [-1, +1]
```
SkewVol = sigma_minus / sigma_plus   # over last H bars

A = BP_up - BP_dn
B = -DSR
C = -tanh(gamma * ln(SkewVol))   # gamma=1

Amp = 0.5 + 0.5*IIX   # applies when raw < 0

ASM_raw = 0.45*A + 0.15*MB + 0.20*C + 0.20*B
if ASM_raw < 0:  ASM = clip(ASM_raw * Amp, -1, 1)
else:             ASM = clip(ASM_raw, -1, 1)
```
- H=60

---

## 3. Escalation v2 (Tail Composite) — range [0, 1]

Uses DSR, IIX, SS arrays + close, EMA (100).

```
_norm(x, lo, hi) = clip((x - lo) / (hi - lo), 0, 1)

C1 = _norm(DSR_now, 0.05, 0.25)
dsr_delta = 0.35*max(0, DSR_now - mean(DSR_prev)) + 0.65*max(0, DSR_now - min(DSR_prev))
C2 = _norm(dsr_delta, 0, 0.05)

iix_delta = 0.35*max(0, IIX_now - mean(IIX_prev)) + 0.65*max(0, IIX_now - min(IIX_prev))
C3 = _norm(iix_delta, 0, 0.08)

struct_decay = max(0, mean(SS_prev) - SS_now)
C4 = _norm(struct_decay, 0, 0.25)

div = |close - EMA| / EMA
div_accel = 0.35*max(0, div_now - mean(div_prev)) + 0.65*max(0, div_now - min(div_prev))
C5 = _norm(div_accel, 0, 0.006)

escalation = clip(0.30*C1 + 0.25*C2 + 0.20*C3 + 0.15*C4 + 0.10*C5, 0, 1)
```
- Windows: w_dsr_delta=10, w_iix_delta=5, w_struct_prev=10, w_div_prev=5

### Rolling Percentile Transform
```
esc_pct[i] = (count of values in window where value <= esc[i]) / window_size
```
- window=504 (2 years daily)

### Escalation Bucket (from percentile)
```
esc_pct >= 0.85 → HIGH, HEDGE_OR_CASH
esc_pct >= 0.60 → MED, REDUCE_40
else            → LOW, NORMAL_SIZE
```

---

## 4. Mapping: 11 Metric Names → Underlying Metrics

| Display Name        | Source (Pandas CLI)                    | Source (Polars)                          |
|---------------------|----------------------------------------|------------------------------------------|
| Trend Strength      | — (not computed)                       | clip((close-ema20)/atr20*0.2+0.5, 0, 1)  |
| Vol Regime          | VRS                                    | clip(rv20/rv100, 0, 3)/3                 |
| Drawdown Pressure   | C2 in RL: (Peak-P)/Peak / 0.20         | (rolling_max-close)/rolling_max / 0.20    |
| Downside Shock      | DSR                                    | clip(-downside_ret.rolling_mean*10, 0, 1) |
| Asymmetry / Skew    | ASM                                    | clip(neg_vol/pos_vol, 0, 2)/2            |
| Momentum State     | momentum.ii or cms                     | clip(ema_slope*2+0.5, 0, 1)              |
| Structural Score   | SS                                     | net_move/total_move (efficiency ratio)   |
| Liquidity / Volume | LQ                                     | volume / rolling_mean(volume)            |
| Gap Risk           | D in RL (partial)                      | clip(\|open-prev_close\|/atr, 0, 2)/2     |
| Key-Level Pressure | from key_levels (H_sup, H_res)         | placeholder = drawdown_pressure          |
| Breadth Proxy       | — (not computed)                       | placeholder = trend_strength             |

---

## 5. Classifier (Confidence, Regime Label)

### Confidence — range [0, 1]
```
raw = 0.20*strength + 0.22*align + 0.14*mom_int + 0.14*inst_q + 0.10*lq_q + 0.10*vol_q + 0.10*shock_q
conf = clip(raw * asymmetry_penalty, 0, 1)
```
- strength, align, mom_int, inst_q, lq_q, vol_q, shock_q, asymmetry_penalty from classifier helpers.

### Regime Label
Deterministic rules from MB, SS, IIX, ASM, DSR, momentum, BP_up, BP_dn. See `classifier.py` for full logic.

---

## 6. Compute Order (Dependencies)

```
1. MB, RL (no metric deps)
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
```
