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


def compute_breakout_probability(
    df: pd.DataFrame,
    mb: float,
    rl: float,
    n_f: int = 20,
    atr_short_n: int = 10,
    atr_long_n: int = 50,
    level_lookback: int = 50,
    k: float = 1.0,
    sigma_cap: float = 0.035,
) -> tuple[float, float]:
    """
    Breakout Probability (BP) in [0,1], returns (BP_up, BP_dn)

    Uses proxy key levels (until Key Levels metric exists):
      L_up = rolling max(high, level_lookback)
      L_dn = rolling min(low, level_lookback)

    Formulas (from your spec):
      d_up = (L_up - P)/ATR_f
      d_dn = (P - L_dn)/ATR_f
      D(d) = exp(-k d)

      Comp = clip(1 - ATR_short/ATR_long, 0, 1)
      Exp  = clip(ATR_short/ATR_short_prev - 1, 0, 1)
      E    = 0.6*Comp + 0.4*Exp

      A_up = (1 + MB)/2
      A_dn = (1 - MB)/2
      R    = 1 - RL

      H = clip(1 - sigma_f/sigma_cap, 0, 1)

      BP_up = clip(D_up * (0.45E + 0.35A_up + 0.20R) * (0.6H + 0.4), 0, 1)
      BP_dn = clip(D_dn * (0.45E + 0.35A_dn + 0.20R) * (0.6H + 0.4), 0, 1)
    """
    if len(df) < max(n_f + 5, atr_long_n + 5, level_lookback + 5):
        return 0.0, 0.0

    close = df["close"]
    high = df["high"]
    low = df["low"]

    # ATRs
    atr_f_series = compute_atr(df, n_f)
    atr_short = compute_atr(df, atr_short_n)
    atr_long = compute_atr(df, atr_long_n)

    ATR_f = float(atr_f_series.iloc[-1])
    ATR_s = float(atr_short.iloc[-1])
    ATR_l = float(atr_long.iloc[-1])

    if np.isnan(ATR_f) or ATR_f <= 0:
        return 0.0, 0.0

    # Proxy levels (deterministic)
    L_up = float(high.rolling(level_lookback).max().iloc[-1])
    L_dn = float(low.rolling(level_lookback).min().iloc[-1])

    P = float(close.iloc[-1])

    # Distances in ATR units (never negative)
    d_up = max(0.0, (L_up - P) / ATR_f)
    d_dn = max(0.0, (P - L_dn) / ATR_f)

    D_up = float(np.exp(-k * d_up))
    D_dn = float(np.exp(-k * d_dn))

    # Energy term
    if np.isnan(ATR_s) or np.isnan(ATR_l) or ATR_l <= 0:
        Comp = 0.0
    else:
        Comp = clamp(1.0 - (ATR_s / ATR_l), 0.0, 1.0)

    ATR_s_prev = float(atr_short.shift(1).iloc[-1])
    if np.isnan(ATR_s_prev) or ATR_s_prev <= 0 or np.isnan(ATR_s):
        Exp = 0.0
    else:
        Exp = clamp((ATR_s / ATR_s_prev) - 1.0, 0.0, 1.0)

    E = 0.6 * Comp + 0.4 * Exp  # in [0,1]

    # Alignment + risk-on capacity
    A_up = clamp((1.0 + float(mb)) / 2.0, 0.0, 1.0)
    A_dn = clamp((1.0 - float(mb)) / 2.0, 0.0, 1.0)
    R = clamp(1.0 - float(rl), 0.0, 1.0)

    quality = (0.45 * E) + (0.35 * A_up) + (0.20 * R)
    quality_dn = (0.45 * E) + (0.35 * A_dn) + (0.20 * R)

    # Hold condition using sigma_f (std of log returns over n_f)
    r = compute_log_returns(close)
    sigma_f = float(r.rolling(n_f).std().iloc[-1])
    if np.isnan(sigma_f) or sigma_cap <= 0:
        H = 0.0
    else:
        H = clamp(1.0 - (sigma_f / sigma_cap), 0.0, 1.0)

    hold_factor = (0.6 * H) + 0.4

    bp_up = D_up * quality * hold_factor
    bp_dn = D_dn * quality_dn * hold_factor

    return clamp(bp_up, 0.0, 1.0), clamp(bp_dn, 0.0, 1.0)


def compute_downside_shock_risk(
    df: pd.DataFrame,
    mb: float,
    rl: float,
    n_f: int = 20,
    n_s: int = 100,
    H: int = 60,
    m: float = 2.5,
    lam: float = 30.0,
    B_max: float = 2.0,
    C_max: float = 3.0,
    D_max: float = 2.0,
    w1: float = 0.30,
    w2: float = 0.20,
    w3: float = 0.20,
    w4: float = 0.10,
    w5: float = 0.20,
) -> float:
    """
    Downside Shock Risk (DSR) in [0,1]

    A_tail = 1 - exp(-lam * A) where A = freq(r < -tau) over last H bars
    tau = m * sigma_f  (sigma_f = std(log returns, n_f))

    B = clip( sigma_minus / sigma_plus, 0, B_max) / B_max
    C = clip( (EMA_s - P)/ATR_f, 0, C_max) / C_max
    D = clip( -g, 0, D_max) / D_max , g = (Open - PrevClose)/ATR_f
    DSR_raw = clip(w1*A_tail + w2*B + w3*C + w4*D + w5*RL, 0, 1)
    Bear = (1 - MB)/2
    DSR = clip( DSR_raw * (0.6 + 0.4*Bear), 0, 1 )
    """
    if len(df) < max(n_s + 5, H + 5, n_f + 5):
        return 0.0

    close = df["close"]
    open_ = df["open"]

    # core series
    r = compute_log_returns(close)

    atr_f_series = compute_atr(df, n_f)
    ATR_f = float(atr_f_series.iloc[-1])
    if np.isnan(ATR_f) or ATR_f <= 0:
        return 0.0

    ema_s_series = compute_ema(close, n_s)
    EMA_s = float(ema_s_series.iloc[-1])
    P = float(close.iloc[-1])

    # sigma_f for tau
    sigma_f = float(r.rolling(n_f).std().iloc[-1])
    if np.isnan(sigma_f) or sigma_f <= 0:
        return 0.0

    tau = m * sigma_f

    # --- A) recent downside tail frequency
    window_r = r.tail(H)
    if window_r.isna().all():
        A_tail = 0.0
    else:
        I = (window_r < (-tau)).astype(float)
        A = float(I.mean())  # freq in [0,1]
        A_tail = float(1.0 - np.exp(-lam * A))

    A_tail = clamp(A_tail, 0.0, 1.0)

    # --- B) downside dominance (semi-vol ratio)
    rH = r.tail(H).dropna()
    if len(rH) < max(10, H // 4):
        B = 0.0
    else:
        neg = rH[rH < 0]
        pos = rH[rH > 0]

        sigma_minus = float(neg.std()) if len(neg) >= 5 else 0.0
        sigma_plus = float(pos.std()) if len(pos) >= 5 else 0.0

        if sigma_plus <= 0:
            ratio = B_max  # if no upside variation, treat as max downside dominance
        else:
            ratio = sigma_minus / sigma_plus

        B = clamp(ratio, 0.0, B_max) / B_max

    # --- C) trend fragility
    C_raw = (EMA_s - P) / ATR_f
    C = clamp(C_raw, 0.0, C_max) / C_max

    # --- D) downside gap pressure
    prev_close = float(close.shift(1).iloc[-1])
    O = float(open_.iloc[-1])
    g = (O - prev_close) / ATR_f
    D = clamp(-g, 0.0, D_max) / D_max

    # --- blend + bearish alignment
    dsr_raw = w1 * A_tail + w2 * B + w3 * C + w4 * D + w5 * clamp(float(rl), 0.0, 1.0)
    dsr_raw = clamp(dsr_raw, 0.0, 1.0)

    Bear = clamp((1.0 - float(mb)) / 2.0, 0.0, 1.0)
    dsr = dsr_raw * (0.6 + 0.4 * Bear)

    return clamp(dsr, 0.0, 1.0)
