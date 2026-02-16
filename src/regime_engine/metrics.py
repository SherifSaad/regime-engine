# src/regime_engine/metrics.py

from __future__ import annotations
import numpy as np
import pandas as pd

from regime_engine.features import compute_ema, compute_atr, compute_log_returns


def clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


def compute_market_bias(
    df: pd.DataFrame,
    n_f: int = 20,
    n_s: int = 100,
    alpha: float = 0.7,
    beta: float = 0.3,
) -> float:
    """
    Market Bias (MB) in [-1, +1]
    MB_t = tanh( alpha * T_t + beta * C_t )
    T_t = (EMA_f - EMA_s) / ATR_f
    C_t = (P - EMA_s) / ATR_f
    """
    if len(df) < n_s + 5:
        return 0.0

    close = df["close"]
    ema_f = compute_ema(close, n_f)
    ema_s = compute_ema(close, n_s)
    atr_f = compute_atr(df, n_f)

    P = float(close.iloc[-1])
    EMAf = float(ema_f.iloc[-1])
    EMAs = float(ema_s.iloc[-1])
    ATRf = float(atr_f.iloc[-1])

    if np.isnan(ATRf) or ATRf <= 0:
        return 0.0

    T = (EMAf - EMAs) / ATRf
    C = (P - EMAs) / ATRf

    mb = float(np.tanh(alpha * T + beta * C))
    return clamp(mb, -1.0, 1.0)


def compute_risk_level(
    df: pd.DataFrame,
    n_f: int = 20,
    n_s: int = 100,
    peak_window: int = 252,
    # caps / references
    A_max: float = 3.0,
    B_max: float = 0.5,
    C1_max: float = 3.0,
    DD_max: float = 0.20,
    D_max: float = 2.0,
    # weights
    w_A: float = 0.35,
    w_B: float = 0.20,
    w_C: float = 0.35,
    w_D: float = 0.10,
) -> float:
    """
    Risk Level (RL) in [0, 1]

    A: vol level (relative): clip(sigma_f / sigma_s, 0, A_max) / A_max
    B: vol expansion: clip((sigma_f - sigma_f_prev)/sigma_f, 0, B_max) / B_max
    C: stress = 0.5*C1 + 0.5*C2
       C1: below-trend stress: clip((EMA_s - P)/ATR_f, 0, C1_max)/C1_max
       C2: drawdown stress: clip(DD/DD_max, 0, 1)   where DD = (Peak - P)/Peak
    D: gap shockiness: clip(Gap, 0, D_max) / D_max
       Gap = |Open - PrevClose| / ATR_f
    RL = clip(wA*A + wB*B + wC*C + wD*D, 0, 1)
    """
    if len(df) < max(n_s + 5, peak_window + 5):
        return 0.0

    close = df["close"]
    open_ = df["open"]

    # log returns
    r = compute_log_returns(close)

    # realized vol components (std of log returns)
    sigma_f_series = r.rolling(n_f).std()
    sigma_s_series = r.rolling(n_s).std()

    sigma_f = float(sigma_f_series.iloc[-1])
    sigma_s = float(sigma_s_series.iloc[-1])

    # ATR and EMA_s
    atr_f_series = compute_atr(df, n_f)
    atr_f = float(atr_f_series.iloc[-1])

    ema_s_series = compute_ema(close, n_s)
    ema_s = float(ema_s_series.iloc[-1])

    P = float(close.iloc[-1])

    if np.isnan(atr_f) or atr_f <= 0:
        return 0.0
    if np.isnan(sigma_f) or sigma_f <= 0:
        return 0.0
    if np.isnan(sigma_s) or sigma_s <= 0:
        # if baseline vol is missing, treat relative vol as max risk for A only
        sigma_s = 1e-12

    # --- A) Vol level (relative)
    A_raw = sigma_f / sigma_s
    A = clamp(A_raw, 0.0, A_max) / A_max

    # --- B) Vol expansion (instability)
    sigma_f_prev = float(sigma_f_series.shift(1).iloc[-1])
    if np.isnan(sigma_f_prev) or sigma_f_prev <= 0:
        B = 0.0
    else:
        B_raw = (sigma_f - sigma_f_prev) / sigma_f
        B = clamp(B_raw, 0.0, B_max) / B_max

    # --- C) Trend / drawdown stress
    # C1: below slow EMA, normalized by ATR
    C1_raw = (ema_s - P) / atr_f
    C1 = clamp(C1_raw, 0.0, C1_max) / C1_max

    # C2: drawdown stress
    peak = float(close.rolling(peak_window).max().iloc[-1])
    if np.isnan(peak) or peak <= 0:
        C2 = 0.0
    else:
        DD = (peak - P) / peak
        C2 = clamp(DD / DD_max, 0.0, 1.0)

    C = 0.5 * C1 + 0.5 * C2

    # --- D) Gap / shockiness
    prev_close = float(close.shift(1).iloc[-1])
    O = float(open_.iloc[-1])
    gap_raw = abs(O - prev_close) / atr_f
    D = clamp(gap_raw, 0.0, D_max) / D_max

    rl = w_A * A + w_B * B + w_C * C + w_D * D
    return clamp(rl, 0.0, 1.0)
