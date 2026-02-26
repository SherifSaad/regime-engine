# Canonical Metric Formulas – Institutional Risk Intelligence Standard

**Version:** 1.0 (2026-02-25) — **DEPRECATED. Use INSTITUTIONAL_RISK_INTELLIGENCE_STANDARD_V2.md (v2.1).**

**Objective:** Define the exact, reproducible computation of the 11 core metrics, escalation, and regime classification. Single source of truth. No divergence between paths.

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

---

## 2. Primitives (Building Blocks)

| Name        | Polars Expression | Window | Notes          |
|-------------|-------------------|--------|----------------|
| returns     | `(close / close.shift(1) - 1)` | — | Daily return   |
| log_returns | `ln(close / close.shift(1))`   | — | Log return     |
| pos_returns | `returns.clip(lower=0)`         | — | Positive returns only |
| neg_returns | `(-returns).clip(lower=0)`     | — | Negative returns only |
| sma(n)      | `close.rolling_mean(window_size=n)` | n | Simple moving average |
| ema(n)      | `close.ewm_mean(span=n, adjust=False)` | n | Exponential moving average |
| rv(n)       | `log_returns.rolling_std(window_size=n) * (252**0.5)` | n | Annualized realized volatility |
| atr(n)      | `tr.rolling_mean(n)` where `tr = max(high-low, |high-prev_close|, |low-prev_close|)` | n | Average True Range (use rolling_mean, not rolling_max). *V2: canonical.* |
| rolling_max(n) | `close.rolling_max(window_size=n)` | n | Highest high in window |
| rolling_min(n) | `close.rolling_min(window_size=n)` | n | Lowest low in window |

---

## 3. The 11 Core Metrics (Canonical Definitions)

All metrics are clipped to [0, 1] range unless otherwise noted.

| # | Display Name        | Polars Expression (vectorized) | Window / Params | Notes |
|---|--------------------|--------------------------------|-----------------|-------|
| 1 | Trend Strength     | `clip((close - ema(close, 20)) / atr(20) * 0.2 + 0.5, 0, 1)` | EMA20, ATR20 | Distance from EMA normalized by volatility. *V2: use ATR(20), not 14.* |
| 2 | Vol Regime         | `clip(rv(20) / rv(100), 0, 3) / 3` | RV20, RV100 | Short vs long volatility ratio |
| 3 | Drawdown Pressure  | `clip((rolling_max(252) - close) / rolling_max(252), 0, 1)` | 252 | Current drawdown from peak |
| 4 | Downside Shock     | `clip(- (close - rolling_min(20)) / atr(20) * 10, 0, 1)` | 20 | Downside move normalized by ATR |
| 5 | Asymmetry / Skew   | `clip(neg_returns.rolling_std(20) / pos_returns.rolling_std(20), 0, 2) / 2` | 20 | Negative vs positive vol skew |
| 6 | Momentum State     | `clip((ema(close, 20) - ema(close, 100)) / atr(20) * 2 + 0.5, 0, 1)` | EMA20/100, ATR20 | EMA crossover normalized |
| 7 | Structural Score   | `clip((close - rolling_min(252)) / (rolling_max(252) - rolling_min(252)), 0, 1)` | 252 | Position within long-term range |
| 8 | Liquidity / Volume | `clip(volume / volume.rolling_mean(20), 0, 3) / 3` | 20 | Relative volume |
| 9 | Gap Risk           | `clip(abs(open - close.shift(1)) / (atr(20) + 1e-12), 0, 2) / 2` | ATR20 | Overnight gap normalized. *V2: add 1e-12 for safety.* |
| 10 | Key-Level Pressure | `clip(drawdown_pressure * (close < ema(close, 100)).cast(int), 0, 1)` | 252, EMA100 | Drawdown when below long EMA |
| 11 | Breadth Proxy      | `clip(trend_strength * (close > ema(close, 20)).cast(int), 0, 1)` | Trend Strength, EMA20 | Proxy for market participation |

---

## 4. Escalation v2 (from percentiles)

**Window = 504** (2 years daily)

```
esc_raw[i]    = DSR[i] * (1 + IIX[i]) * (1 + SS[i]) * (1 + ASM[i]) * (1 + LQ[i])
esc_pct[i]    = rolling_percentile_rank(esc_raw, window=504)
esc_bucket[i] =
  esc_pct >= 0.85 → "HIGH"   → "HEDGE_OR_CASH"
  esc_pct >= 0.60 → "MED"    → "REDUCE_40"
  else            → "LOW"    → "NORMAL_SIZE"
```

---

## 5. Regime Classifier (Confidence + Label)

### Confidence (0–1)

```
raw = 0.20 * trend_strength + 0.22 * alignment + 0.14 * momentum_intensity
    + 0.14 * institutional_quality + 0.10 * liquidity_quality
    + 0.10 * volatility_quality + 0.10 * shock_quality
conf = clip(raw * asymmetry_penalty, 0, 1)
```

### Regime Label

Deterministic rules based on MB, SS, IIX, ASM, DSR, momentum, BP_up, BP_dn (see `classifier.py` for exact logic).

---

## 6. Compute Order (Dependencies)

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

## 7. Canonical Output Schema

### metrics_11 (list of dicts – preferred for UI)

```json
[
  {"metric": "Trend Strength", "pct": 0.72, "label": "Strong"},
  {"metric": "Vol Regime",     "pct": 0.45, "label": "Normal"},
  ...
]
```

### latest_state (JSON in compute.db)

```json
{
  "regime_label": "TRENDING_BULL",
  "confidence": 0.78,
  "escalation_v2": "MED",
  "escalation_pct": 0.68,
  "metrics_11": [ ... ],
  "computed_at": "2026-02-25T14:30:00Z",
  "bar_count_used": 8323,
  "last_ts": "2026-02-24T16:00:00Z"
}
```

---

## Summary

**This document is now the single source of truth.**

- All paths (scheduler, backfill, per-symbol) must use these exact formulas.
- No dummy/fallback values in production.

**Next Step:** Use this as the target for unifying the compute engine.
