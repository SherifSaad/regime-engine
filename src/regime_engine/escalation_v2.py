import numpy as np
import pandas as pd

def _clip01(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))

def _norm_linear_pos(x: float, lo: float, hi: float) -> float:
    """
    Deterministic linear normalization into [0,1], with clamping.
    Only meaningful for x >= 0 (we pass positive-part deltas).
    """
    if hi <= lo:
        raise ValueError("hi must be > lo for normalization.")
    return _clip01((x - lo) / (hi - lo))

def compute_escalation_v2(
    dsr, iix, ss, close, ema,
    # windows from Grok plan
    w_dsr_delta: int = 10,   # 5–10 days; using 10 for stability
    w_iix_delta: int = 5,
    w_struct_prev: int = 10,
    w_div_prev: int = 5,
    # deterministic scaling constants (tweak once, then lock)
    dsr_level_lo: float = 0.05,
    dsr_level_hi: float = 0.25,
    dsr_delta_lo: float = 0.00,
    dsr_delta_hi: float = 0.05,
    iix_delta_lo: float = 0.00,
    iix_delta_hi: float = 0.08,
    struct_decay_lo: float = 0.00,
    struct_decay_hi: float = 0.25,
    div_accel_lo: float = 0.00,
    div_accel_hi: float = 0.006,
):
    """
    Returns:
      escalation (float in [0,1]),
      plus a dict of components for auditability.
    """
    dsr = np.asarray(dsr, dtype=float)
    iix = np.asarray(iix, dtype=float)
    ss  = np.asarray(ss,  dtype=float)
    close = np.asarray(close, dtype=float)
    ema   = np.asarray(ema,   dtype=float)

    n = len(close)
    if not (len(dsr) == len(iix) == len(ss) == len(ema) == n):
        raise ValueError("All inputs must have the same length.")
    if n < max(w_dsr_delta, w_iix_delta, w_struct_prev, w_div_prev) + 2:
        raise ValueError("Not enough history for the chosen windows.")

    t = n - 1

    # C1: DSR level
    dsr_now = dsr[t]
    c1 = _norm_linear_pos(dsr_now, dsr_level_lo, dsr_level_hi)

    # ----- C2: DSR delta (positive lift-off)
    dsr_prev_avg = float(np.mean(dsr[t - w_dsr_delta : t]))
    dsr_prev_min = float(np.min(dsr[t - w_dsr_delta : t]))

    dsr_delta_avg = max(0.0, dsr_now - dsr_prev_avg)   # acceleration vs mean
    dsr_delta_min = max(0.0, dsr_now - dsr_prev_min)   # lift-off vs recent low

    # Blend: lift-off is more tail-relevant, but keep some avg-based stability
    dsr_delta = 0.35 * dsr_delta_avg + 0.65 * dsr_delta_min
    c2 = _norm_linear_pos(dsr_delta, dsr_delta_lo, dsr_delta_hi)

    # ----- C3: IIX delta (positive lift-off)
    iix_now = iix[t]
    iix_prev_avg = float(np.mean(iix[t - w_iix_delta : t]))
    iix_prev_min = float(np.min(iix[t - w_iix_delta : t]))

    iix_delta_avg = max(0.0, iix_now - iix_prev_avg)
    iix_delta_min = max(0.0, iix_now - iix_prev_min)

    iix_delta = 0.35 * iix_delta_avg + 0.65 * iix_delta_min
    c3 = _norm_linear_pos(iix_delta, iix_delta_lo, iix_delta_hi)

    # C4: Structural decay (structure breaking = score falling)
    ss_now = ss[t]
    ss_prev_avg = float(np.mean(ss[t - w_struct_prev : t]))
    struct_decay = max(0.0, ss_prev_avg - ss_now)
    c4 = _norm_linear_pos(struct_decay, struct_decay_lo, struct_decay_hi)

    # ----- C5: Momentum divergence acceleration (close vs EMA) with lift-off
    div = np.abs(close - ema) / np.maximum(ema, 1e-12)
    div_now = float(div[t])

    div_prev_avg = float(np.mean(div[t - w_div_prev : t]))
    div_prev_min = float(np.min(div[t - w_div_prev : t]))

    div_accel_avg = max(0.0, div_now - div_prev_avg)
    div_accel_min = max(0.0, div_now - div_prev_min)

    div_accel = 0.35 * div_accel_avg + 0.65 * div_accel_min
    c5 = _norm_linear_pos(div_accel, div_accel_lo, div_accel_hi)

    # Weighted tail composite (0–1)
    escalation = _clip01(
        0.30 * c1 +
        0.25 * c2 +
        0.20 * c3 +
        0.15 * c4 +
        0.10 * c5
    )

    components = {
        "C1_DSR_level": c1,
        "C2_DSR_delta": c2,
        "C3_IIX_delta": c3,
        "C4_Structural_decay": c4,
        "C5_Div_accel": c5,
        "raw": {
            "dsr_now": dsr_now,
            "dsr_prev_avg": dsr_prev_avg,
            "dsr_prev_min": dsr_prev_min,
            "dsr_delta": dsr_delta,
            "iix_now": iix_now,
            "iix_prev_avg": iix_prev_avg,
            "iix_prev_min": iix_prev_min,
            "iix_delta": iix_delta,
            "ss_now": ss_now,
            "ss_prev_avg": ss_prev_avg,
            "struct_decay": struct_decay,
            "div_now": div_now,
            "div_prev_avg": div_prev_avg,
            "div_prev_min": div_prev_min,
            "div_accel": div_accel,
        }
    }

    # --- Audit fields (no printing) ---
    components["audit"] = {
        "windows": {
            "w_dsr_delta": w_dsr_delta,
            "w_iix_delta": w_iix_delta,
            "w_struct_prev": w_struct_prev,
            "w_div_prev": w_div_prev,
        },
        "norm_ranges": {
            "dsr_level_lo": dsr_level_lo, "dsr_level_hi": dsr_level_hi,
            "dsr_delta_lo": dsr_delta_lo, "dsr_delta_hi": dsr_delta_hi,
            "iix_delta_lo": iix_delta_lo, "iix_delta_hi": iix_delta_hi,
            "struct_decay_lo": struct_decay_lo, "struct_decay_hi": struct_decay_hi,
            "div_accel_lo": div_accel_lo, "div_accel_hi": div_accel_hi,
        },
        "deltas": {
            "dsr_prev_avg": dsr_prev_avg,
            "dsr_prev_min": dsr_prev_min,
            "iix_prev_avg": iix_prev_avg,
            "iix_prev_min": iix_prev_min,
            "ss_prev_avg": ss_prev_avg,
            "div_prev_avg": div_prev_avg,
            "div_prev_min": div_prev_min,
        },
    }

    return escalation, components


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
    dsr_level_lo: float = 0.05,
    dsr_level_hi: float = 0.25,
    dsr_delta_lo: float = 0.00,
    dsr_delta_hi: float = 0.05,
    iix_delta_lo: float = 0.00,
    iix_delta_hi: float = 0.08,
    struct_decay_lo: float = 0.00,
    struct_decay_hi: float = 0.25,
    div_accel_lo: float = 0.00,
    div_accel_hi: float = 0.006,
) -> np.ndarray:
    """
    Vectorized escalation v2: returns array of escalation values for each bar.
    Same math as compute_escalation_v2 but applied to full series.
    """
    dsr = np.asarray(dsr, dtype=float)
    iix = np.asarray(iix, dtype=float)
    ss = np.asarray(ss, dtype=float)
    close = np.asarray(close, dtype=float)
    ema = np.asarray(ema, dtype=float)

    n = len(close)
    w_max = max(w_dsr_delta, w_iix_delta, w_struct_prev, w_div_prev) + 2
    if n < w_max:
        return np.full(n, np.nan)

    out = np.full(n, np.nan, dtype=float)

    # Rolling windows
    dsr_prev_avg = _rolling_mean(dsr, w_dsr_delta)
    dsr_prev_min = _rolling_min(dsr, w_dsr_delta)
    iix_prev_avg = _rolling_mean(iix, w_iix_delta)
    iix_prev_min = _rolling_min(iix, w_iix_delta)
    ss_prev_avg = _rolling_mean(ss, w_struct_prev)
    div = np.abs(close - ema) / np.maximum(ema, 1e-12)
    div_prev_avg = _rolling_mean(div, w_div_prev)
    div_prev_min = _rolling_min(div, w_div_prev)

    for t in range(w_max - 1, n):
        c1 = _norm_linear_pos(dsr[t], dsr_level_lo, dsr_level_hi)

        dsr_delta_avg = max(0.0, dsr[t] - dsr_prev_avg[t])
        dsr_delta_min = max(0.0, dsr[t] - dsr_prev_min[t])
        dsr_delta = 0.35 * dsr_delta_avg + 0.65 * dsr_delta_min
        c2 = _norm_linear_pos(dsr_delta, dsr_delta_lo, dsr_delta_hi)

        iix_delta_avg = max(0.0, iix[t] - iix_prev_avg[t])
        iix_delta_min = max(0.0, iix[t] - iix_prev_min[t])
        iix_delta = 0.35 * iix_delta_avg + 0.65 * iix_delta_min
        c3 = _norm_linear_pos(iix_delta, iix_delta_lo, iix_delta_hi)

        struct_decay = max(0.0, ss_prev_avg[t] - ss[t])
        c4 = _norm_linear_pos(struct_decay, struct_decay_lo, struct_decay_hi)

        div_accel_avg = max(0.0, div[t] - div_prev_avg[t])
        div_accel_min = max(0.0, div[t] - div_prev_min[t])
        div_accel = 0.35 * div_accel_avg + 0.65 * div_accel_min
        c5 = _norm_linear_pos(div_accel, div_accel_lo, div_accel_hi)

        out[t] = _clip01(0.30 * c1 + 0.25 * c2 + 0.20 * c3 + 0.15 * c4 + 0.10 * c5)

    return out


def _rolling_mean(arr: np.ndarray, w: int) -> np.ndarray:
    """Rolling mean of previous w values (exclusive of current). result[i] = mean(arr[i-w:i])."""
    s = pd.Series(arr)
    rolling = s.rolling(w, min_periods=w).mean()
    return rolling.shift(1).values


def _rolling_min(arr: np.ndarray, w: int) -> np.ndarray:
    """Rolling min of previous w values (exclusive of current). result[i] = min(arr[i-w:i])."""
    s = pd.Series(arr)
    rolling = s.rolling(w, min_periods=w).min()
    return rolling.shift(1).values


def rolling_percentile_transform(series: pd.Series, window: int = 252*2) -> pd.Series:
    """
    Deterministic rolling percentile transform.
    Maps raw escalation to [0,1] based on trailing window.
    No lookahead.
    """
    out = []
    values = series.values
    for i in range(len(values)):
        if i < window:
            out.append(np.nan)
            continue
        hist = values[i-window:i]
        rank = np.sum(hist <= values[i]) / len(hist)
        out.append(rank)
    return pd.Series(out, index=series.index)
