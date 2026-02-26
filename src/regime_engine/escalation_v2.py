"""
Escalation v2: institutional production standard.

PRODUCTION MODE (default):
- Expanding-window percentile transform (no rolling).
- Component-level percentiles before aggregation.
- Equal-weight aggregation (no calibration study).
- Deterministic average-rank tie handling (midrank/N).
- Min 252 bars before percentile output.
- No hard-coded normalization caps (percentile-based scaling).

RESEARCH MODE:
- rolling_percentile_transform (deprecated) for experiments.
- Use only for backtests; not for live/production.
"""
import numpy as np
import pandas as pd

from regime_engine.standard_v2_1 import midrank_percentile_from_hist

# Numba-accelerated path when available (pip install regime-engine[perf])
try:
    import numba
    _HAS_NUMBA = True
except ImportError:
    _HAS_NUMBA = False

# --- Production Mode (default) ---
PRODUCTION_MODE = True
ESCALATION_PERCENTILE_MODE = "expanding"  # Default: expanding (not rolling)
ESCALATION_MIN_BARS = 252  # Minimum sample size before percentile output
ESCALATION_TIE_HANDLING = "average_rank"  # (count_less + (count_equal+1)/2) / n


def _clip01(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))


def _expanding_percentile_numba(values: np.ndarray, start: int) -> np.ndarray:
    """Numba JIT: expanding midrank percentile. Same math as midrank_percentile_from_hist.
    Denominator = len(hist) = i+1 to match original (NaN in hist excluded from rank counts).
    """
    n = len(values)
    out = np.full(n, np.nan, dtype=np.float64)
    for i in range(start, n):
        x = values[i]
        if np.isnan(x):
            continue
        count_less = 0.0
        count_equal = 0.0
        for j in range(i + 1):
            v = values[j]
            if np.isnan(v):
                continue
            if v < x:
                count_less += 1
            elif v == x:
                count_equal += 1
        n_valid = count_less + count_equal
        if n_valid <= 0:
            continue
        rank = count_less + (count_equal + 1.0) / 2.0
        out[i] = rank / (i + 1)  # match original: divide by len(hist)
    return out


if _HAS_NUMBA:
    _expanding_percentile_numba = numba.jit(nopython=True, cache=True)(_expanding_percentile_numba)


def expanding_percentile_transform(
    series: pd.Series,
    min_bars: int = 252,
) -> pd.Series:
    """
    Production default: expanding-window percentile transform.
    Tie handling: average-rank (see ESCALATION_TIE_HANDLING).
    Min sample: min_bars (default 252) before output; NaN otherwise.
    Use min_bars=1 for era-conditioned percentile (no blackout; pair with confidence).
    No lookahead.
    """
    values = np.asarray(series.values, dtype=float)
    n = len(values)
    start = 0 if min_bars <= 1 else min_bars

    if _HAS_NUMBA and n >= 100:
        out = _expanding_percentile_numba(values, start)
    else:
        out = np.full(n, np.nan, dtype=float)
        for i in range(start, n):
            hist = values[: i + 1]
            x = float(values[i])
            out[i] = midrank_percentile_from_hist(hist, x)

    return pd.Series(out, index=series.index)


def rolling_percentile_transform(series: pd.Series, window: int = 252 * 2) -> pd.Series:
    """
    RESEARCH MODE ONLY. Deprecated for production.
    Use expanding_percentile_transform (Production Mode) instead.
    Kept for backtests/experiments. Same tie handling: average-rank.
    """
    return _rolling_percentile_impl(series, window)


def _rolling_percentile_numba(values: np.ndarray, window: int) -> np.ndarray:
    """Numba JIT: rolling midrank percentile. Same math, fixed window."""
    n = len(values)
    out = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        start = max(0, i - window + 1)
        if i - start + 1 < window:
            continue
        x = values[i]
        if np.isnan(x):
            continue
        count_less = 0.0
        count_equal = 0.0
        for j in range(start, i + 1):
            v = values[j]
            if np.isnan(v):
                continue
            if v < x:
                count_less += 1
            elif v == x:
                count_equal += 1
        n_valid = count_less + count_equal
        if n_valid <= 0:
            continue
        rank = count_less + (count_equal + 1.0) / 2.0
        out[i] = rank / window  # window = len(hist) when full
    return out


if _HAS_NUMBA:
    _rolling_percentile_numba = numba.jit(nopython=True, cache=True)(_rolling_percentile_numba)


def _rolling_percentile_impl(series: pd.Series, window: int) -> pd.Series:
    """
    Rolling percentile with average-rank tie handling. Internal use.
    Canonical inclusion rule: hist = values[start:i+1] INCLUDES current bar (no lookahead).
    See METRIC_AND_ESCALATION_CODE.md §4a.
    """
    values = np.asarray(series.values, dtype=float)
    n = len(values)
    if _HAS_NUMBA and n >= window:
        out = _rolling_percentile_numba(values, window)
    else:
        out = np.full(n, np.nan, dtype=float)
        for i in range(n):
            start = max(0, i - window + 1)
            hist = values[start : i + 1]
            if len(hist) < window:
                continue
            x = float(values[i])
            out[i] = midrank_percentile_from_hist(hist, x)
    return pd.Series(out, index=series.index)


def compute_escalation_v2(
    dsr,
    iix,
    ss,
    close,
    ema,
    w_dsr_delta: int = 10,
    w_iix_delta: int = 5,
    w_struct_prev: int = 10,
    w_div_prev: int = 5,
) -> tuple[float, dict]:
    """
    Single-bar escalation from full arrays.
    Uses percentile-based components and equal-weight aggregation.
    Returns (composite, components_dict) with C1_DSR_level..C5_Div_accel, raw, audit.
    """
    dsr = np.asarray(dsr, dtype=float)
    iix = np.asarray(iix, dtype=float)
    ss = np.asarray(ss, dtype=float)
    close = np.asarray(close, dtype=float)
    ema = np.asarray(ema, dtype=float)
    n = len(close)
    w_max = max(w_dsr_delta, w_iix_delta, w_struct_prev, w_div_prev) + 2
    if n < w_max:
        return float("nan"), {}

    esc_series, components_series = compute_escalation_v2_series_with_components(
        dsr, iix, ss, close, ema,
        w_dsr_delta=w_dsr_delta,
        w_iix_delta=w_iix_delta,
        w_struct_prev=w_struct_prev,
        w_div_prev=w_div_prev,
    )
    if len(esc_series) == 0 or np.isnan(esc_series.iloc[-1]):
        return float("nan"), {}
    composite = float(esc_series.iloc[-1])
    parts = {
        "C1_DSR_level": float(components_series["C1_DSR_level"].iloc[-1]) if "C1_DSR_level" in components_series else 0.0,
        "C2_DSR_delta": float(components_series["C2_DSR_delta"].iloc[-1]) if "C2_DSR_delta" in components_series else 0.0,
        "C3_IIX_delta": float(components_series["C3_IIX_delta"].iloc[-1]) if "C3_IIX_delta" in components_series else 0.0,
        "C4_Structural_decay": float(components_series["C4_Structural_decay"].iloc[-1]) if "C4_Structural_decay" in components_series else 0.0,
        "C5_Div_accel": float(components_series["C5_Div_accel"].iloc[-1]) if "C5_Div_accel" in components_series else 0.0,
    }
    t = n - 1
    dsr_prev_avg = float(np.mean(dsr[t - w_dsr_delta : t]))
    dsr_prev_min = float(np.min(dsr[t - w_dsr_delta : t]))
    iix_prev_avg = float(np.mean(iix[t - w_iix_delta : t]))
    iix_prev_min = float(np.min(iix[t - w_iix_delta : t]))
    ss_prev_avg = float(np.mean(ss[t - w_struct_prev : t]))
    div = np.abs(close - ema) / np.maximum(ema, 1e-12)
    div_prev_avg = float(np.mean(div[t - w_div_prev : t]))
    div_prev_min = float(np.min(div[t - w_div_prev : t]))
    parts["raw"] = {
        "dsr_now": float(dsr[t]),
        "dsr_prev_avg": dsr_prev_avg,
        "dsr_prev_min": dsr_prev_min,
        "dsr_delta": 0.35 * max(0, dsr[t] - dsr_prev_avg) + 0.65 * max(0, dsr[t] - dsr_prev_min),
        "iix_now": float(iix[t]),
        "iix_prev_avg": iix_prev_avg,
        "iix_prev_min": iix_prev_min,
        "iix_delta": 0.35 * max(0, iix[t] - iix_prev_avg) + 0.65 * max(0, iix[t] - iix_prev_min),
        "ss_now": float(ss[t]),
        "ss_prev_avg": ss_prev_avg,
        "struct_decay": max(0, ss_prev_avg - ss[t]),
        "div_now": float(div[t]),
        "div_prev_avg": div_prev_avg,
        "div_prev_min": div_prev_min,
        "div_accel": 0.35 * max(0, div[t] - div_prev_avg) + 0.65 * max(0, div[t] - div_prev_min),
    }
    parts["audit"] = {
        "windows": {"w_dsr_delta": w_dsr_delta, "w_iix_delta": w_iix_delta, "w_struct_prev": w_struct_prev, "w_div_prev": w_div_prev},
        "percentile_mode": ESCALATION_PERCENTILE_MODE,
        "aggregation": "equal_weight",
    }
    return composite, parts


def compute_escalation_v2_series(
    dsr: np.ndarray | list,
    iix: np.ndarray | list,
    ss: np.ndarray | list,
    close: np.ndarray | list,
    ema: np.ndarray | list,
    w_dsr_delta: int = 10,
    w_iix_delta: int = 5,
    w_struct_prev: int = 10,
    w_div_prev: int = 5,
    min_bars: int = 252,
) -> np.ndarray:
    """
    Escalation composite series: percentile-based components, equal-weight aggregation.
    Returns composite array (percentile-based, in [0,1]). Does NOT apply final
    expanding percentile; caller should use expanding_percentile_transform for esc_pct.
    """
    composite, _ = compute_escalation_v2_series_with_components(
        dsr, iix, ss, close, ema,
        w_dsr_delta=w_dsr_delta,
        w_iix_delta=w_iix_delta,
        w_struct_prev=w_struct_prev,
        w_div_prev=w_div_prev,
    )
    return np.asarray(composite.values if isinstance(composite, pd.Series) else composite, dtype=float)


def compute_escalation_v2_pct_series(
    composite: pd.Series,
    min_bars: int = 252,
) -> pd.Series:
    """
    Final escalation percentile: expanding percentile of composite.
    Use for bucket lookup. Enforces min_bars.
    """
    return expanding_percentile_transform(composite, min_bars=min_bars)


def compute_escalation_v2_series_with_components(
    dsr: np.ndarray | list,
    iix: np.ndarray | list,
    ss: np.ndarray | list,
    close: np.ndarray | list,
    ema: np.ndarray | list,
    w_dsr_delta: int = 10,
    w_iix_delta: int = 5,
    w_struct_prev: int = 10,
    w_div_prev: int = 5,
) -> tuple[pd.Series, dict[str, pd.Series]]:
    """
    Raw components (no norm ranges) -> expanding percentile each -> equal-weight aggregate.
    Returns (composite_series, components_series_dict).
    """
    dsr = np.asarray(dsr, dtype=float)
    iix = np.asarray(iix, dtype=float)
    ss = np.asarray(ss, dtype=float)
    close = np.asarray(close, dtype=float)
    ema = np.asarray(ema, dtype=float)

    n = len(close)
    w_max = max(w_dsr_delta, w_iix_delta, w_struct_prev, w_div_prev) + 2
    if n < w_max:
        empty = pd.Series(dtype=float)
        return empty, {}

    dsr_prev_avg = _rolling_mean(dsr, w_dsr_delta)
    dsr_prev_min = _rolling_min(dsr, w_dsr_delta)
    iix_prev_avg = _rolling_mean(iix, w_iix_delta)
    iix_prev_min = _rolling_min(iix, w_iix_delta)
    ss_prev_avg = _rolling_mean(ss, w_struct_prev)
    div = np.abs(close - ema) / np.maximum(ema, 1e-12)
    div_prev_avg = _rolling_mean(div, w_div_prev)
    div_prev_min = _rolling_min(div, w_div_prev)

    c1_raw = np.full(n, np.nan, dtype=float)
    c2_raw = np.full(n, np.nan, dtype=float)
    c3_raw = np.full(n, np.nan, dtype=float)
    c4_raw = np.full(n, np.nan, dtype=float)
    c5_raw = np.full(n, np.nan, dtype=float)

    for t in range(w_max - 1, n):
        c1_raw[t] = dsr[t]

        dsr_delta_avg = max(0.0, dsr[t] - dsr_prev_avg[t])
        dsr_delta_min = max(0.0, dsr[t] - dsr_prev_min[t])
        c2_raw[t] = 0.35 * dsr_delta_avg + 0.65 * dsr_delta_min

        iix_delta_avg = max(0.0, iix[t] - iix_prev_avg[t])
        iix_delta_min = max(0.0, iix[t] - iix_prev_min[t])
        c3_raw[t] = 0.35 * iix_delta_avg + 0.65 * iix_delta_min

        c4_raw[t] = max(0.0, ss_prev_avg[t] - ss[t])

        div_accel_avg = max(0.0, div[t] - div_prev_avg[t])
        div_accel_min = max(0.0, div[t] - div_prev_min[t])
        c5_raw[t] = 0.35 * div_accel_avg + 0.65 * div_accel_min

    idx = pd.RangeIndex(n)
    c1_series = pd.Series(c1_raw, index=idx)
    c2_series = pd.Series(c2_raw, index=idx)
    c3_series = pd.Series(c3_raw, index=idx)
    c4_series = pd.Series(c4_raw, index=idx)
    c5_series = pd.Series(c5_raw, index=idx)

    pct_c1 = expanding_percentile_transform(c1_series, min_bars=ESCALATION_MIN_BARS)
    pct_c2 = expanding_percentile_transform(c2_series, min_bars=ESCALATION_MIN_BARS)
    pct_c3 = expanding_percentile_transform(c3_series, min_bars=ESCALATION_MIN_BARS)
    pct_c4 = expanding_percentile_transform(c4_series, min_bars=ESCALATION_MIN_BARS)
    pct_c5 = expanding_percentile_transform(c5_series, min_bars=ESCALATION_MIN_BARS)

    composite = (pct_c1 + pct_c2 + pct_c3 + pct_c4 + pct_c5) / 5.0
    composite = composite.clip(0.0, 1.0)

    components = {
        "C1_DSR_level": pct_c1,
        "C2_DSR_delta": pct_c2,
        "C3_IIX_delta": pct_c3,
        "C4_Structural_decay": pct_c4,
        "C5_Div_accel": pct_c5,
    }
    return composite, components


def _rolling_mean(arr: np.ndarray, w: int) -> np.ndarray:
    """Rolling mean of previous w values (exclusive of current)."""
    s = pd.Series(arr)
    rolling = s.rolling(w, min_periods=w).mean()
    return rolling.shift(1).values


def _rolling_min(arr: np.ndarray, w: int) -> np.ndarray:
    """Rolling min of previous w values (exclusive of current)."""
    s = pd.Series(arr)
    rolling = s.rolling(w, min_periods=w).min()
    return rolling.shift(1).values


def get_escalation_metadata() -> dict:
    """Metadata for institutional compliance."""
    return {
        "mode": "production" if PRODUCTION_MODE else "research",
        "percentile_mode": ESCALATION_PERCENTILE_MODE,
        "percentile_default": "expanding",
        "min_bars": ESCALATION_MIN_BARS,
        "aggregation": "equal_weight",
        "tie_handling": ESCALATION_TIE_HANDLING,
        "tie_formula": "(count_less + (count_equal + 1) / 2) / n",
    }
