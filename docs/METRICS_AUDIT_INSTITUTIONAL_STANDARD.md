# 11-Metric Audit – Institutional Risk Intelligence Standard

**Document:** Metrics Audit Report  
**Standard Reference:** INSTITUTIONAL_RISK_INTELLIGENCE_STANDARD_V2.md (v2.2, locked to production)  
**Version:** 2.0 (2026-02-25)  
**Scope:** All 11 core metrics, audited against 7 institutional criteria

---

## Changelog (v2.0)

- **Standard V2.1 updates applied:** Calibration footnotes, min bar requirements, fallbacks (Structural Score flat range, Liquidity missing volume, Gap Risk first bar), Breadth Proxy placeholder marking in output schema.
- **Addressed:** ATR(20) consistency, normalization validity notes, failure mode handling.
- **Deferred:** Unifying Downside Shock / Structural Score with full pandas implementation (multiple variants documented in Appendix).

---

## Audit Framework

Each metric is evaluated against:

| # | Criterion | Description |
|---|-----------|-------------|
| 1 | **Mathematical definition clarity** | Formula is unambiguous; inputs/outputs explicit; no implicit assumptions |
| 2 | **Economic meaning** | Metric captures a well-defined market concept; interpretable by practitioners |
| 3 | **Range logic** | Output range is correct; clipping/normalization justified |
| 4 | **Normalization validity** | Scaling constants (0.2, 0.5, caps) are defensible or documented |
| 5 | **Redundancy risk** | Overlap with other metrics; information content distinct |
| 6 | **Failure modes** | Edge cases (ATR=0, first bars, NaN, extremes) handled |
| 7 | **Measures intended concept** | Metric measures what it claims (trend, instability, risk, etc.) |

**Implementation references:** `src/regime_engine/metrics.py` (canonical). `core/compute/regime_engine_polars.py` is **experimental/non-canonical** — different formulas, not an equivalence reference.

---

## Metric 1: Trend Strength

**Standard formula:** `clip((close - ema(close, 20)) / atr(20) * 0.2 + 0.5, 0, 1)`

### 1. Mathematical definition clarity
- **Clarity:** Good. Inputs (close, ema20, atr20) and output [0,1] are explicit.
- **Ambiguity:** Resolved. Standard V2.1 and V1 (corrected) use ATR(20). Polars uses atr20. **Canonical: ATR(20) for all metrics.**
- **Spec vs implementation:** Polars matches. Pandas has no direct "Trend Strength"; MB (Market Bias) is related but uses tanh and different structure.

### 2. Economic meaning
- **Meaning:** Distance of price from short-term trend (EMA20), normalized by volatility (ATR). High = price above EMA (bullish); low = below (bearish).
- **Interpretation:** Measures *directional conviction* relative to noise, not trend persistence. Sensible for regime context.

### 3. Range logic
- **Raw:** `(close - ema20) / atr20` can be unbounded (e.g. ±5 in volatile moves).
- **Scaling:** `* 0.2 + 0.5` maps roughly: 0 → 0.5, ±2.5 ATR → 0 or 1. Linear mapping; ±2.5 ATR is a reasonable "extreme" for daily.
- **Clip:** Ensures [0,1]. Correct.

### 4. Normalization validity
- **0.2:** Arbitrary. Could calibrate from historical ATR multiples. Document as "calibration constant."
- **0.5:** Centers neutral at 0.5. Standard choice.
- **✓ Addressed in V2.1:** Standard now documents "0.2 chosen so ±2.5 ATR maps to [0,1]. Min 20 bars."

### 5. Redundancy risk
- **Overlap with Momentum State:** Both use EMA20 vs EMA100 or close vs EMA. Momentum State uses EMA crossover; Trend Strength uses distance from EMA20. Related but distinct (one is level, one is slope/crossover).
- **Overlap with Breadth Proxy:** Breadth Proxy = trend_strength when close > ema20. High redundancy when above EMA.
- **Verdict:** Moderate redundancy with Momentum State and Breadth Proxy. Acceptable if used for different purposes.

### 6. Failure modes
- **ATR=0:** Standard uses `atr(20) + 1e-12`. Safe.
- **First 20 bars:** EMA and ATR undefined. Need min 20 bars; return NaN or 0.5.
- **✓ Addressed in V2.1:** Standard documents min 20 bars.
- **Flat price:** close == ema20 → 0.5. Correct.
- **NaN propagation:** If close/ema/atr have NaN, output NaN. Document handling.

### 7. Measures intended concept
- **Intended:** Trend strength (directional conviction).
- **Actual:** Measures *distance from short-term trend*, not instability. Correct for name.
- **Instability:** No. Trend Strength is a *directional* metric, not instability.

---

## Metric 2: Vol Regime

**Standard formula:** `clip(rv(20) / rv(100), 0, 3) / 3`

### 1. Mathematical definition clarity
- **Clarity:** Good. RV = realized vol (annualized). Ratio of short vs long vol.
- **Spec vs implementation:** Pandas VRS uses 0.50*A + 0.30*B + 0.20*C (vol ratio + ATR expansion + RL). Standard simplifies to vol ratio only. **Divergence:** Full implementation is richer; standard is simplified.

### 2. Economic meaning
- **Meaning:** Short-term volatility relative to longer-term baseline. >1 = vol expansion; <1 = vol contraction.
- **Interpretation:** Captures *volatility regime* (calm vs stressed). Core instability indicator.

### 3. Range logic
- **Raw ratio:** [0, ∞). Capped at 3 → [0, 1] after /3. Correct.
- **Design choice:** 3× cap compresses extreme regimes. Documented in V2.

### 4. Normalization validity
- **3× cap:** Design choice. Extreme vol expansion (5×, 10×) maps to 1.0. Consider 5× if tail discrimination matters.
- **Division by 3:** Linear mapping. Valid.

### 5. Redundancy risk
- **Overlap with IIX:** IIX includes VRS. Vol Regime is a component. Not redundant—VRS is the vol-specific metric; IIX is composite.
- **Overlap with RL:** RL has vol component (A). Some overlap but RL is multi-factor.
- **Verdict:** Low redundancy. Distinct role.

### 6. Failure modes
- **rv(100)=0:** Standard uses `rv(100) + 1e-12`. Safe.
- **First 100 bars:** rv(100) undefined. Need min 100 bars.
- **Constant price:** rv=0 → ratio undefined. 1e-12 prevents blowup; result ~0.
- **Verdict:** Handled with epsilon.

### 7. Measures intended concept
- **Intended:** Volatility regime (instability).
- **Actual:** Measures vol expansion/contraction. **Yes—core instability metric.**

---

## Metric 3: Drawdown Pressure

**Standard formula:** `clip((rolling_max(252) - close) / (rolling_max(252) + 1e-12), 0, 1)`

### 1. Mathematical definition clarity
- **Clarity:** Good. Drawdown from 252-bar peak. Standard does NOT divide by 0.20 (Polars does: drawdown/0.20). **Divergence:** V2 spec has no 0.20; Polars uses it. Standard formula is raw drawdown (0–100%); Polars scales by DD_max=0.20.
- **Recommendation:** Clarify: raw drawdown [0,1] vs scaled. V2 uses raw; Polars scales.

### 2. Economic meaning
- **Meaning:** Current drawdown from 1-year high. 0 = at peak; 1 = total wipeout.
- **Interpretation:** Captures *capital at risk* from peak. Key risk metric.

### 3. Range logic
- **Raw:** (peak - close) / peak ∈ [0, 1] when close ≤ peak. Correct.
- **Clip:** Redundant if close never exceeds peak (rolling max). Defensive.
- **1e-12:** Prevents div by zero when peak=0 (shouldn't happen for price).

### 4. Normalization validity
- **No extra scaling in V2.** Raw drawdown is already [0,1]. Valid.
- **Polars:** Divides by 0.20 to amplify signal. Different from standard.

### 5. Redundancy risk
- **Overlap with Key-Level Pressure:** Key-Level = drawdown when below EMA100. Subset of Drawdown Pressure. Redundant when below EMA.
- **Overlap with RL (C2):** RL uses DD/DD_max. Same concept. RL is composite.
- **Verdict:** Drawdown Pressure is the canonical drawdown metric; others reference it.

### 6. Failure modes
- **First 252 bars:** rolling_max uses partial window. Polars/rolling typically returns expanding max. Check behavior.
- **peak=0:** 1e-12 prevents div by zero. Result ~1 (max drawdown).
- **Verdict:** Handled.

### 7. Measures intended concept
- **Intended:** Drawdown / capital at risk.
- **Actual:** Measures drawdown from peak. **Yes—risk metric, not instability per se.** Related to stress.

---

## Metric 4: Downside Shock

**Standard formula:** `clip(- (close - rolling_min(20)) / (atr(20) + 1e-12) * 10, 0, 1)`

### 1. Mathematical definition clarity
- **Clarity:** Moderate. `close - rolling_min(20)` = distance above recent low. When close < rolling_min (breakdown), negative. `- (negative)` = positive. So we capture *breakdown below recent low* in ATR units.
- **Ambiguity:** Formula assumes close can go below rolling_min. rolling_min = min of close over 20 bars. So close can equal rolling_min (at the bar that made the low) but typically not below. The formula measures: when we're above the low, how far? Actually: `- (close - rolling_min)` = rolling_min - close. Positive when close < rolling_min. So we measure *how far below the 20-bar low we've broken*. When above low, negative → clipped to 0.
- **Spec vs implementation:** Pandas DSR is completely different (tail frequency, semi-vol ratio, trend fragility, gap, RL). Polars uses `-downside_ret.rolling_mean(20)*10`. **Major divergence.** Standard formula is a third variant.
- **Recommendation:** Standard defines a *simplified* Downside Shock. Document that full DSR (metrics.py) is richer; standard is vectorized proxy.

### 2. Economic meaning
- **Meaning:** Magnitude of breakdown below recent low, in ATR units. High = sharp drop through support.
- **Interpretation:** Captures *downside breakout* or *breakdown severity*. Instability/risk indicator.

### 3. Range logic
- **Raw:** (rolling_min - close) / atr20 can be large (e.g. 5 ATR drop). * 10 amplifies. Clip to [0,1].
- **Scaling:** *10 is arbitrary. 0.1 ATR drop → 1.0. Very sensitive. Consider smaller multiplier (e.g. 2–5).
- **Verdict:** Range correct but scaling may need calibration.

### 4. Normalization validity
- ***10:** No documented justification. Recommend backtest or reduce to 2–5.
- **✓ Addressed in V2.1:** Standard now documents "*10 maps ~0.1 ATR drop to 1.0. Min 20 bars."

### 5. Redundancy risk
- **Overlap with Drawdown Pressure:** Both capture downside. Drawdown = from peak; Downside Shock = from recent low. Different horizons.
- **Overlap with DSR:** DSR (full) includes this concept plus tail frequency, etc. Standard Downside Shock is a component.
- **Verdict:** Low redundancy. Complementary.

### 6. Failure modes
- **ATR=0:** 1e-12. Safe.
- **First 20 bars:** rolling_min and ATR need 20 bars.
- **Flat price:** close = rolling_min → 0. Correct.
- **Verdict:** Handled.

### 7. Measures intended concept
- **Intended:** Downside shock / breakdown severity.
- **Actual:** Measures breakdown below recent low. **Yes—instability/risk metric.**

---

## Metric 5: Asymmetry / Skew

**Standard formula:** `clip(neg_returns.rolling_std(20) / (pos_returns.rolling_std(20) + 1e-12), 0, 4) / 4`

### 1. Mathematical definition clarity
- **Clarity:** Good. Ratio of downside vol to upside vol. >1 = negative skew.
- **Spec vs implementation:** Pandas ASM uses BP_up-BP_dn, DSR, SkewVol (sigma_minus/sigma_plus), with Amp modifier. Different structure. Polars uses same ratio, clip 0–2. Standard uses 0–4 (V2 update).
- **pos_returns, neg_returns:** Standard uses `returns.clip(lower=0)` and `(-returns).clip(lower=0)`. For std: need returns where r<0 and r>0 separately. `neg_returns` = zero for r>0; `pos_returns` = zero for r<0. So we get std of negative returns and std of positive returns. Correct for semi-volatility.

### 2. Economic meaning
- **Meaning:** Downside volatility relative to upside. High = more violent down moves than up (negative skew).
- **Interpretation:** Tail risk / skewness proxy. Instability indicator.

### 3. Range logic
- **Raw ratio:** [0, ∞). Cap 4 → [0, 1]. V2 raised from 2 to 4 for crash regimes. Good.
- **Verdict:** Correct.

### 4. Normalization validity
- **4× cap:** Documented in V2. Crashes can exceed 2×. Valid.
- **Verdict:** Good.

### 5. Redundancy risk
- **Overlap with DSR (B component):** DSR uses sigma_minus/sigma_plus. Same concept. ASM is the standalone skew metric; DSR is composite.
- **Verdict:** Low redundancy. ASM is canonical skew.

### 6. Failure modes
- **pos_returns all zero (only down days):** std of zeros = 0 or NaN. 1e-12 in denominator. Ratio → large; cap at 4. Handled.
- **neg_returns all zero (only up days):** std of zeros = 0. Ratio = 0. Correct (no downside vol).
- **Few observations:** std with n<2 is NaN. May need min period.
- **✓ Addressed in V2.1:** Standard documents min 5 observations for std.

### 7. Measures intended concept
- **Intended:** Asymmetry / skew (downside vs upside vol).
- **Actual:** Measures semi-vol ratio. **Yes—skew/instability metric.**

---

## Metric 6: Momentum State

**Standard formula:** `clip((ema(close, 20) - ema(close, 100)) / (atr(20) + 1e-12) * 2 + 0.5, 0, 1)`

### 1. Mathematical definition clarity
- **Clarity:** Good. EMA20 - EMA100 = fast minus slow. Positive = bullish crossover. Normalized by ATR.
- **Spec vs implementation:** Pandas momentum uses CMS (0.5*MB + 0.3*tanh(M/k) + 0.2*SS), II, ER, and state rules. Different. Polars uses `(ema20 - ema20.shift(5)) / atr20 * 2 + 0.5` (EMA slope, not crossover). **Divergence:** Standard uses EMA20-EMA100; Polars uses ema20 - ema20.shift(5). Standard is crossover; Polars is slope.
- **Recommendation:** Standard formula is crossover-based. Document clearly.

### 2. Economic meaning
- **Meaning:** Short-term trend vs medium-term. Positive = bullish momentum; negative = bearish.
- **Interpretation:** Classic momentum indicator. Directional, not instability.

### 3. Range logic
- **Raw:** (ema20 - ema100) / atr20 can be ±several ATR. *2 + 0.5 maps: 0 → 0.5, ±0.25 ATR → 0 or 1. Very sensitive.
- **Verdict:** May saturate quickly. Consider larger divisor (e.g. 4 or 5).

### 4. Normalization validity
- ***2 + 0.5:** Arbitrary. ±0.25 ATR diff → extremes. EMA20 vs EMA100 can differ by 1–3 ATR in strong trends. Calibration needed.
- **✓ Addressed in V2.1:** Standard now documents calibration and min 100 bars.

### 5. Redundancy risk
- **Overlap with Trend Strength:** Both use EMA. Trend Strength = distance from EMA20; Momentum = EMA20 vs EMA100. Related but distinct.
- **Overlap with MB:** MB uses (EMA_f - EMA_s)/ATR and (P - EMA_s)/ATR. Similar structure. MB is richer (includes price).
- **Verdict:** Moderate overlap with MB and Trend Strength. Acceptable.

### 6. Failure modes
- **ATR=0:** 1e-12. Safe.
- **First 100 bars:** EMA100 undefined. Need min 100 bars.
- **Verdict:** Handled with min bars.

### 7. Measures intended concept
- **Intended:** Momentum state (directional).
- **Actual:** Measures EMA crossover. **Yes—momentum metric. Not instability.**

---

## Metric 7: Structural Score

**Standard formula:** `clip((close - rolling_min(252)) / (rolling_max(252) - rolling_min(252) + 1e-12), 0, 1)`

### 1. Mathematical definition clarity
- **Clarity:** Good. Position within 252-bar range. 0 = at low; 1 = at high.
- **Spec vs implementation:** Pandas SS uses MB*(0.55+0.25*ER+0.20*Stab)+0.25*C (key levels). Range [-1,1]. Completely different. Polars uses efficiency ratio (net_move/total_move). **Major divergence.** Standard formula is *position in range*; pandas SS is *directional structure with key levels*.
- **Recommendation:** Standard defines a *simplified* Structural Score (range position). Full SS in metrics.py is different. Document as "Structural Score (simplified)" or "Range Position."

### 2. Economic meaning
- **Meaning:** Where price sits within the past year's range. 1 = at highs; 0 = at lows.
- **Interpretation:** "Bought the high" vs "bought the low" proxy. Risk/positioning metric.

### 3. Range logic
- **Raw:** (close - min) / (max - min) ∈ [0, 1] when min < max. Correct.
- **Flat range:** max = min → denom 0. 1e-12. Result undefined; clip may give 0 or 1. Document: use 0.5 when max=min.
- **✓ Addressed in V2.1:** Standard documents fallback 0.5 when rolling_max(252)==rolling_min(252). Min 252 bars.

### 4. Normalization validity
- **No extra scaling.** Natural [0,1]. Valid.
- **Verdict:** Good.

### 5. Redundancy risk
- **Overlap with Drawdown Pressure:** Drawdown = (max - close)/max. Structural = (close - min)/(max - min). Related but different. Structural is symmetric (high vs low); Drawdown is one-sided.
- **Verdict:** Low redundancy. Complementary.

### 6. Failure modes
- **First 252 bars:** Expanding window. Handled.
- **max = min:** 1e-12; result can be 0.5 or arbitrary. Recommend explicit: if max==min then 0.5.
- **Verdict:** Add explicit handling for flat range.

### 7. Measures intended concept
- **Intended:** Structural score / position in range.
- **Actual:** Measures range position. **Yes—positioning metric. Not instability.** (Structure can imply stability when at support.)

---

## Metric 8: Liquidity / Volume

**Standard formula:** `clip(volume / (volume.rolling_mean(20) + 1), 0, 3) / 3`

### 1. Mathematical definition clarity
- **Clarity:** Good. Relative volume = current / 20-bar average.
- **Spec vs implementation:** Pandas LQ uses 0.45*RDV + 0.25*(1-VRS) + 0.15*gap_penalty + 0.15*ER. RDV = dollar volume / SMA(dollar volume). Different. Polars uses volume/vol_ma. Standard matches Polars (simplified).
- **Recommendation:** Standard is simplified (volume only). Full LQ includes vol burden, gap, choppiness.

### 2. Economic meaning
- **Meaning:** Current volume relative to recent average. High = elevated participation; low = thin.
- **Interpretation:** Liquidity proxy. Low = instability risk (thin market).

### 3. Range logic
- **Raw:** volume / (mean + 1). Can exceed 3 in spikes. Cap at 3 → [0, 1]. Correct.
- **Zero volume:** 0 / (mean+1) = 0. Correct.
- **Verdict:** Good.

### 4. Normalization validity
- **3× cap:** Reasonable. Volume spikes rarely >3× average for extended periods.
- **+1 in denominator:** Prevents div by zero when mean=0. Valid.
- **Verdict:** Good.

### 5. Redundancy risk
- **Overlap with IIX:** IIX includes (1-LQ). LQ is the liquidity metric; IIX consumes it.
- **Verdict:** No redundancy. LQ is canonical.

### 6. Failure modes
- **First 20 bars:** rolling_mean undefined. Need min 20.
- **Zero volume history:** mean=0, +1 saves. Handled.
- **Missing volume:** Some assets lack volume. Return 0.5 (neutral) or NaN. Document.
- **✓ Addressed in V2.1:** Standard documents fallback 0.5 when volume missing or all zeros. Min 20 bars.

### 7. Measures intended concept
- **Intended:** Liquidity / volume participation.
- **Actual:** Measures relative volume. **Yes—liquidity metric. Inverse correlates with instability (thin = risky).**

---

## Metric 9: Gap Risk

**Standard formula:** `clip(abs(open - close.shift(1)) / (atr(20) + 1e-12), 0, 2) / 2`

### 1. Mathematical definition clarity
- **Clarity:** Good. Overnight gap in ATR units.
- **Spec vs implementation:** Matches Polars and RL component D. Pandas handles in RL and IIX.
- **Fallback (V2):** First bar or open==prev_close → 0. Documented.

### 2. Economic meaning
- **Meaning:** Magnitude of overnight gap (open vs prior close). High = discontinuity; execution risk.
- **Interpretation:** Gap = instability / discontinuity. Key risk metric.

### 3. Range logic
- **Raw:** gap / atr ∈ [0, ∞). Cap at 2 ATR → [0, 1]. 2 ATR gap = extreme. Reasonable.
- **Verdict:** Good.

### 4. Normalization validity
- **2 ATR cap:** Overnight gaps >2 ATR are rare. Valid.
- **Verdict:** Good.

### 5. Redundancy risk
- **Overlap with RL (D):** RL uses same gap/ATR. Gap Risk is standalone; RL is composite.
- **Overlap with IIX (E):** IIX includes gap. Same.
- **Verdict:** Gap Risk is canonical; others consume it.

### 6. Failure modes
- **First bar:** prev_close undefined. Fallback: 0. Documented in V2.
- **Holiday / open==prev_close:** Gap=0. Fallback: 0. Documented.
- **ATR=0:** 1e-12. Safe.
- **Verdict:** Well handled.

### 7. Measures intended concept
- **Intended:** Gap risk / discontinuity.
- **Actual:** Measures overnight gap. **Yes—instability metric.**

---

## Metric 10: Key-Level Pressure

**Standard formula:** `clip(drawdown_pressure * (close < ema(close, 100)).cast(int), 0, 1)`

### 1. Mathematical definition clarity
- **Clarity:** Good. Drawdown pressure only when below long EMA (bearish zone).
- **Spec vs implementation:** Pandas Key Levels returns supports/resistances; Key-Level Pressure is derived from SS (key-level integrity). Polars uses drawdown_pressure as placeholder. Standard uses drawdown * below_EMA flag. Simplified.
- **Recommendation:** Standard is a *proxy* until full key levels integrated. Document.

### 2. Economic meaning
- **Meaning:** Drawdown pressure when price is below trend (bearish). Ignores drawdown when above EMA.
- **Interpretation:** "Stress when we're in the wrong place." Risk metric.

### 3. Range logic
- **Product:** drawdown_pressure ∈ [0,1], flag ∈ {0,1}. Product ∈ [0,1]. Correct.
- **Verdict:** Good.

### 4. Normalization validity
- **No extra scaling.** Valid.
- **Verdict:** Good.

### 5. Redundancy risk
- **Overlap with Drawdown Pressure:** Key-Level = Drawdown when below EMA. Subset. Redundant by design (conditional drawdown).
- **Verdict:** Intentional. Key-Level is *conditional* drawdown.

### 6. Failure modes
- **First 252 bars:** drawdown needs 252; EMA100 needs 100. Use max(252, 100).
- **Verdict:** Handled.

### 7. Measures intended concept
- **Intended:** Key-level pressure (stress near supports).
- **Actual:** Conditional drawdown. **Partial—true key levels would use support/resistance proximity.** Current is proxy.

---

## Metric 11: Breadth Proxy

**Standard formula:** `clip(trend_strength * (close > ema(close, 20)).cast(int), 0, 1)`

### 1. Mathematical definition clarity
- **Clarity:** Good. Trend strength when above EMA20; 0 when below.
- **Spec vs implementation:** Polars uses trend_strength (no filter). Standard adds filter. Documented as placeholder in V2.
- **Recommendation:** Explicitly "placeholder until advancers/decliners available."

### 2. Economic meaning
- **Meaning:** "Breadth" typically = advancers/decliners, % above 200d MA, etc. This is *trend strength when price is above short EMA*—a weak proxy.
- **Interpretation:** Participation proxy: only count strength when we're in "bullish" zone. Weak substitute for true breadth.

### 3. Range logic
- **Product:** trend_strength ∈ [0,1], flag ∈ {0,1}. Product ∈ [0,1]. Correct.
- **Verdict:** Good.

### 4. Normalization validity
- **No extra scaling.** Valid.
- **Verdict:** Good.

### 5. Redundancy risk
- **Overlap with Trend Strength:** Breadth Proxy = Trend Strength when close > EMA20; 0 otherwise. **High redundancy.** Almost the same metric with a filter.
- **Verdict:** High redundancy. Acceptable only as temporary placeholder.

### 6. Failure modes
- **First 20 bars:** trend_strength and EMA20 need 20 bars.
- **Verdict:** Handled.

### 7. Measures intended concept
- **Intended:** Breadth (market participation).
- **Actual:** Filtered trend strength. **No—does not measure breadth.** Placeholder only. Replace with advancers/decliners or similar when available.
- **✓ Addressed in V2.1:** Standard marks as PLACEHOLDER in output schema; include `"label": "Placeholder"` in metrics_11.

---

## Summary Table

*Post–Standard V2.1: items marked ✓ were addressed in the Standard.*

| Metric | Clarity | Economic | Range | Normalization | Redundancy | Failure Modes | Measures Concept |
|--------|---------|----------|-------|---------------|------------|--------------|-------------------|
| 1. Trend Strength | ✓ | ✓ | ✓ | ✓ (V2.1) | ⚠ Mod | ✓ | ✓ (direction) |
| 2. Vol Regime | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (instability) |
| 3. Drawdown Pressure | ⚠ Spec vs Polars | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (risk) |
| 4. Downside Shock | ⚠ 3 variants | ✓ | ✓ | ✓ (V2.1) | ✓ | ✓ | ✓ (instability) |
| 5. Asymmetry / Skew | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (V2.1) | ✓ (instability) |
| 6. Momentum State | ✓ | ✓ | ✓ | ✓ (V2.1) | ⚠ Mod | ✓ | ✓ (direction) |
| 7. Structural Score | ⚠ Spec vs pandas | ✓ | ✓ | ✓ | ✓ | ✓ (V2.1) | ✓ (positioning) |
| 8. Liquidity / Volume | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (V2.1) | ✓ (liquidity) |
| 9. Gap Risk | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (instability) |
| 10. Key-Level Pressure | ✓ | ✓ | ✓ | ✓ | ✓ by design | ✓ | ⚠ Proxy |
| 11. Breadth Proxy | ✓ | ⚠ Weak | ✓ | ✓ | ⚠ High | ✓ | ✗ Placeholder (V2.1) |

---

## Recommendations

### Addressed in Standard V2.1 ✓
- **ATR consistency:** ATR(20) used everywhere.
- **Calibration constants:** Documented for Trend Strength, Momentum, Downside Shock.
- **Structural Score flat range:** Fallback 0.5 when max==min.
- **Asymmetry min period:** Min 5 observations documented.
- **Missing volume:** Fallback 0.5 when volume absent.
- **Breadth Proxy:** Marked as PLACEHOLDER in output schema.

### Deferred (documented for future work)
1. **Unify Downside Shock:** Three variants exist (Standard, Polars, pandas DSR). Pick one as canonical in future engine unification.
2. **Unify Structural Score:** Standard (range position) vs pandas (ER + key levels). Different metrics; consider rename or alignment.
3. **Vol Regime cap:** Consider 5× if tail discrimination needed.
4. **Drawdown Pressure:** Clarify raw vs scaled (Polars uses /0.20). Standard uses raw.

---

## Appendix: Spec vs Implementation Mapping

*Standard reference: INSTITUTIONAL_RISK_INTELLIGENCE_STANDARD_V2.md (v2.1)*

| Metric | Standard V2.1 | Polars | Pandas (metrics.py) |
|--------|-------------|--------|----------------------|
| Trend Strength | close-ema20/atr20*0.2+0.5 | Same | — (MB is related) |
| Vol Regime | rv20/rv100, cap 3 | Same | VRS: 0.5*A+0.3*B+0.2*RL |
| Drawdown Pressure | (max-close)/max | /0.20 | In RL (C2) |
| Downside Shock | -(close-min20)/atr20*10 | -down_ret.mean*10 | DSR (multi-factor) |
| Asymmetry | neg_std/pos_std, cap 4 | cap 2 | ASM (BP, DSR, SkewVol) |
| Momentum State | (ema20-ema100)/atr20*2+0.5 | ema slope | CMS, II, ER, state |
| Structural Score | (close-min)/(max-min) | net/total move | SS (ER, Stab, key levels) |
| Liquidity | vol/vol_ma, cap 3 | Same | LQ (RDV, VRS, gap, ER) |
| Gap Risk | \|open-prev_close\|/atr20 | Same | In RL, IIX |
| Key-Level Pressure | drawdown*(close<ema100) | drawdown | Key levels + SS |
| Breadth Proxy | trend*(close>ema20) | trend | — |

---

*End of audit. Reference: INSTITUTIONAL_RISK_INTELLIGENCE_STANDARD_V2.md (v2.1), 2026-02-25.*
