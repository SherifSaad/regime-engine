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
    L_up: float | None = None,
    L_dn: float | None = None,
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

    P = float(close.iloc[-1])

    # Key levels if given, otherwise proxy levels (deterministic fallback)
    if L_up is None:
        L_up = float(high.rolling(level_lookback).max().iloc[-1])
    if L_dn is None:
        L_dn = float(low.rolling(level_lookback).min().iloc[-1])

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


def compute_key_levels(
    df: pd.DataFrame,
    n_f: int = 20,
    W: int = 250,
    k: int = 3,
    eta: float = 0.35,     # epsilon = eta * ATR_f
    delta: float = 0.30,   # touch tolerance in ATR units
    tau_T: float = 3.0,
    h: int = 5,            # rejection horizon
    R_max: float = 2.0,
    rho: float = 5.0,      # round number closeness scale
    bins: int = 60,        # volume-at-price bins
    N: int = 3,            # keep top N each side
    min_strength: float = 0.35,
) -> dict:
    """
    Returns:
      {
        "supports": [{"price": float, "strength": float}, ...],
        "resistances": [{"price": float, "strength": float}, ...]
      }
    Deterministic, price+volume only.
    """
    if len(df) < max(W, (2 * k + 5), n_f + 5):
        return {"supports": [], "resistances": []}

    # last W bars only (search window)
    d = df.tail(W).copy()
    close = d["close"]
    high = d["high"]
    low = d["low"]
    vol = d["volume"] if "volume" in d.columns else None

    atr_f_series = compute_atr(d, n_f)
    ATR_f = float(atr_f_series.iloc[-1])
    if np.isnan(ATR_f) or ATR_f <= 0:
        return {"supports": [], "resistances": []}

    eps = eta * ATR_f
    P = float(close.iloc[-1])

    # -----------------------------
    # helpers
    # -----------------------------
    def _round_step(price: float) -> float:
        if price < 20:
            return 1.0
        if price < 200:
            return 5.0
        if price < 2000:
            return 25.0
        return 100.0

    def _cluster_candidates(cands: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """
        cands: list of (level_price, score in [0,1])
        returns clusters -> list of (L*, S*)
        Single-link clustering by sorting and grouping levels within eps.
        """
        if not cands:
            return []

        cands_sorted = sorted(cands, key=lambda x: x[0])

        clusters: list[list[tuple[float, float]]] = []
        current = [cands_sorted[0]]

        for lvl, sc in cands_sorted[1:]:
            prev_lvl = current[-1][0]
            if abs(lvl - prev_lvl) <= eps:
                current.append((lvl, sc))
            else:
                clusters.append(current)
                current = [(lvl, sc)]
        clusters.append(current)

        out: list[tuple[float, float]] = []
        for cl in clusters:
            weights = np.array([max(0.0, float(s)) for _, s in cl], dtype=float)
            levels = np.array([float(l) for l, _ in cl], dtype=float)

            wsum = float(weights.sum())
            if wsum <= 0:
                continue

            L_star = float((weights * levels).sum() / wsum)

            # S* = 1 - Π(1 - s)
            prod = 1.0
            for _, s in cl:
                prod *= (1.0 - clamp(float(s), 0.0, 1.0))
            S_star = float(1.0 - prod)

            out.append((L_star, clamp(S_star, 0.0, 1.0)))
        return out

    # -----------------------------
    # Evidence 1: Swing pivots
    # -----------------------------
    pivot_cands: list[tuple[float, float]] = []

    # pivot high if high[t] is max in [t-k, t+k]
    # pivot low if low[t] is min in [t-k, t+k]
    for i in range(k, len(d) - k):
        window_high = high.iloc[i - k : i + k + 1]
        window_low = low.iloc[i - k : i + k + 1]
        hi = float(high.iloc[i])
        lo = float(low.iloc[i])

        is_pivot_high = hi == float(window_high.max())
        is_pivot_low = lo == float(window_low.min())

        # score pivots by: touches, rejection, recency
        if is_pivot_high or is_pivot_low:
            L = hi if is_pivot_high else lo

            # touches: count bars where |close - L|/ATR <= delta
            dist = (close - L).abs() / ATR_f
            touches_idx = dist[dist <= delta].index
            touch_count = int(len(touches_idx))

            T = float(1.0 - np.exp(-(touch_count / tau_T)))  # saturating

            # rejection: for each touch, measure move away over h bars
            rej_vals = []
            for ts in touches_idx:
                pos = d.index.get_loc(ts)
                if isinstance(pos, slice):
                    continue
                j = pos + h
                if j >= len(d):
                    continue
                rej = abs(float(close.iloc[j]) - float(close.iloc[pos])) / ATR_f
                rej_vals.append(rej)

            if rej_vals:
                rej_mean = float(np.mean(rej_vals))
                R = clamp(rej_mean / R_max, 0.0, 1.0)
            else:
                R = 0.0

            # recency: bars since last touch
            if touch_count > 0:
                last_touch = touches_idx[-1]
                age = len(d) - 1 - d.index.get_loc(last_touch)
            else:
                age = W

            tau_Q = W / 3.0
            Q = float(np.exp(-(age / tau_Q)))

            score_pivot = clamp(0.5 * T + 0.3 * R + 0.2 * Q, 0.0, 1.0)
            pivot_cands.append((float(L), float(score_pivot)))

    # -----------------------------
    # Evidence 2: Volume-at-price (optional)
    # -----------------------------
    vap_cands: list[tuple[float, float]] = []
    if vol is not None and vol.notna().any():
        typ = (high + low + close) / 3.0
        pmin = float(typ.min())
        pmax = float(typ.max())
        if pmax > pmin:
            edges = np.linspace(pmin, pmax, bins + 1)
            hist = np.zeros(bins, dtype=float)

            # accumulate volume into bins
            idxs = np.searchsorted(edges, typ.values, side="right") - 1
            idxs = np.clip(idxs, 0, bins - 1)
            for b, v in zip(idxs, vol.values):
                if np.isnan(v):
                    continue
                hist[int(b)] += float(v)

            if hist.max() > 0:
                # pick top few peaks (simple: top 5 bins)
                top_bins = np.argsort(hist)[-5:][::-1]
                for b in top_bins:
                    center = float((edges[b] + edges[b + 1]) / 2.0)
                    score_vap = float(hist[b] / hist.max())
                    vap_cands.append((center, clamp(score_vap, 0.0, 1.0)))

    # -----------------------------
    # Evidence 3: Round numbers
    # -----------------------------
    round_cands: list[tuple[float, float]] = []
    step = _round_step(P)
    span = 10.0 * ATR_f

    lo_lvl = P - span
    hi_lvl = P + span
    start = np.floor(lo_lvl / step) * step
    end = np.ceil(hi_lvl / step) * step

    L = start
    while L <= end + 1e-9:
        score_round = float(np.exp(-(abs(P - L) / (rho * ATR_f))))
        round_cands.append((float(L), clamp(score_round, 0.0, 1.0)))
        L += step

    # -----------------------------
    # Merge + cluster all candidates
    # -----------------------------
    all_cands = pivot_cands + vap_cands + round_cands
    clusters = _cluster_candidates(all_cands)

    # classify support / resistance
    supports = []
    resistances = []
    for lvl, s in clusters:
        if s < min_strength:
            continue
        if lvl < P:
            supports.append((lvl, s))
        elif lvl > P:
            resistances.append((lvl, s))

    # keep nearest N, but prioritize strength too (simple sort: strength desc, then distance asc)
    def _rank(side: list[tuple[float, float]], is_support: bool):
        if is_support:
            return sorted(side, key=lambda x: (-x[1], abs(P - x[0])))
        return sorted(side, key=lambda x: (-x[1], abs(x[0] - P)))

    supports = _rank(supports, True)[:N]
    resistances = _rank(resistances, False)[:N]

    return {
        "supports": [{"price": float(l), "strength": float(s)} for l, s in supports],
        "resistances": [{"price": float(l), "strength": float(s)} for l, s in resistances],
    }


def compute_structural_score(
    df: pd.DataFrame,
    mb: float,
    rl: float,
    dsr: float,
    key_levels: dict,
    n_f: int = 20,
    n_s: int = 100,
    n_c: int = 20,
) -> float:
    """
    Structural Score (SS) in [-1, +1]

    ER (efficiency ratio):
      ER = |P - P[n_c]| / sum(|P[i]-P[i-1]| over last n_c)
    Stab = 1 - (0.6*RL + 0.4*DSR)
    C (key-level integrity):
      support hold: tanh((P - S1)/ATR_f)
      resistance pressure: tanh((R1 - P)/ATR_f)
      C = 0.6*s1*H_sup + 0.4*r1*H_res
    Final:
      SS = clip( MB*(0.55 + 0.25*ER + 0.20*Stab) + 0.25*C, -1, 1 )
    """
    if len(df) < max(n_s + 5, n_c + 5, n_f + 5):
        return 0.0

    close = df["close"]
    P = float(close.iloc[-1])

    atr_f_series = compute_atr(df, n_f)
    ATR_f = float(atr_f_series.iloc[-1])
    if np.isnan(ATR_f) or ATR_f <= 0:
        return 0.0

    # --- ER (Kaufman efficiency ratio) in [0,1]
    P_nc = float(close.iloc[-1 - n_c])
    net = abs(P - P_nc)

    diffs = close.diff().abs().tail(n_c)
    denom = float(diffs.sum())
    ER = 0.0 if denom <= 0 else clamp(net / denom, 0.0, 1.0)

    # --- Stability Stab in [0,1]
    Stab = 1.0 - (0.6 * clamp(float(rl), 0.0, 1.0) + 0.4 * clamp(float(dsr), 0.0, 1.0))
    Stab = clamp(Stab, 0.0, 1.0)

    # --- Key-level integrity C in [-1,1]
    supports = key_levels.get("supports", []) if isinstance(key_levels, dict) else []
    resistances = key_levels.get("resistances", []) if isinstance(key_levels, dict) else []

    if supports:
        S1 = float(supports[0]["price"])
        s1 = clamp(float(supports[0]["strength"]), 0.0, 1.0)
    else:
        S1, s1 = None, 0.0

    if resistances:
        R1 = float(resistances[0]["price"])
        r1 = clamp(float(resistances[0]["strength"]), 0.0, 1.0)
    else:
        R1, r1 = None, 0.0

    H_sup = 0.0
    if S1 is not None:
        delta_sup = (P - S1) / ATR_f
        H_sup = float(np.tanh(delta_sup))

    H_res = 0.0
    if R1 is not None:
        delta_res = (R1 - P) / ATR_f
        H_res = float(np.tanh(delta_res))

    C = 0.6 * s1 * H_sup + 0.4 * r1 * H_res
    C = clamp(C, -1.0, 1.0)

    # --- Final SS
    mb_f = clamp(float(mb), -1.0, 1.0)
    ss = mb_f * (0.55 + 0.25 * ER + 0.20 * Stab) + 0.25 * C
    return clamp(ss, -1.0, 1.0)


def compute_volatility_regime(
    df: pd.DataFrame,
    rl: float,
    n_f: int = 20,
    n_s: int = 100,
    n_sh: int = 10,
    n_lg: int = 50,
) -> dict:
    """
    Returns:
      {
        "vrs": float in [0,1],
        "label": "CALM"|"NORMAL"|"ELEVATED"|"STRESSED",
        "trend": "RISING"|"FALLING"|"FLAT"
      }
    """
    if len(df) < max(n_s + 5, n_lg + 5):
        return {"vrs": 0.0, "label": "NORMAL", "trend": "FLAT"}

    close = df["close"]
    r = compute_log_returns(close)

    sigma_f = float(r.rolling(n_f).std().iloc[-1])
    sigma_s = float(r.rolling(n_s).std().iloc[-1])

    # avoid division blowups
    if np.isnan(sigma_f) or sigma_f <= 0:
        return {"vrs": 0.0, "label": "NORMAL", "trend": "FLAT"}
    if np.isnan(sigma_s) or sigma_s <= 0:
        sigma_s = 1e-12

    VR = sigma_f / sigma_s

    atr_short = compute_atr(df, n_sh)
    atr_long = compute_atr(df, n_lg)

    ATR_s = float(atr_short.iloc[-1])
    ATR_l = float(atr_long.iloc[-1])

    if np.isnan(ATR_s) or np.isnan(ATR_l) or ATR_l <= 0:
        AR = 1.0
    else:
        AR = ATR_s / ATR_l

    # A) vol ratio score
    A = clamp(clamp(VR, 0.0, 3.0) / 3.0, 0.0, 1.0)

    # B) ATR expansion score
    B = clamp(clamp(AR, 0.0, 2.0) / 2.0, 0.0, 1.0)

    # C) risk confirmation
    C = clamp(float(rl), 0.0, 1.0)

    vrs = clamp(0.50 * A + 0.30 * B + 0.20 * C, 0.0, 1.0)

    # label rules
    if vrs < 0.25:
        label = "CALM"
    elif vrs < 0.45:
        label = "NORMAL"
    elif vrs < 0.70:
        label = "ELEVATED"
    else:
        label = "STRESSED"

    # trend tag based on delta VRS
    # compute previous VRS using previous values (shifted)
    sigma_f_prev = float(r.rolling(n_f).std().shift(1).iloc[-1])
    sigma_s_prev = float(r.rolling(n_s).std().shift(1).iloc[-1])
    if np.isnan(sigma_f_prev) or sigma_f_prev <= 0:
        vrs_prev = vrs
    else:
        if np.isnan(sigma_s_prev) or sigma_s_prev <= 0:
            sigma_s_prev = 1e-12
        VR_prev = sigma_f_prev / sigma_s_prev

        ATR_s_prev = float(atr_short.shift(1).iloc[-1])
        ATR_l_prev = float(atr_long.shift(1).iloc[-1])
        if np.isnan(ATR_s_prev) or np.isnan(ATR_l_prev) or ATR_l_prev <= 0:
            AR_prev = AR
        else:
            AR_prev = ATR_s_prev / ATR_l_prev

        A_prev = clamp(clamp(VR_prev, 0.0, 3.0) / 3.0, 0.0, 1.0)
        B_prev = clamp(clamp(AR_prev, 0.0, 2.0) / 2.0, 0.0, 1.0)
        vrs_prev = clamp(0.50 * A_prev + 0.30 * B_prev + 0.20 * C, 0.0, 1.0)

    dV = vrs - vrs_prev
    if dV >= 0.03:
        trend = "RISING"
    elif dV <= -0.03:
        trend = "FALLING"
    else:
        trend = "FLAT"

    return {"vrs": float(vrs), "label": label, "trend": trend}


def compute_momentum_state(
    df: pd.DataFrame,
    mb: float,
    ss: float,
    vrs: float,
    bp_up: float,
    bp_dn: float,
    n_f: int = 20,
    n_m: int = 20,
    k_m: float = 2.0,
    n_c: int = 20,  # for ER (same as SS)
) -> dict:
    """
    Returns:
      {
        "state": "STRONG_UP_IMPULSE"|"WEAK_UP_DRIFT"|"NEUTRAL_RANGE"|"WEAK_DOWN_DRIFT"|"STRONG_DOWN_IMPULSE",
        "cms": float in [-1,1],
        "ii": float in [0,1],
        "er": float in [0,1],
      }
    """
    if len(df) < max(n_m + 5, n_f + 5, n_c + 5):
        return {"state": "NEUTRAL_RANGE", "cms": 0.0, "ii": 0.0, "er": 0.0}

    close = df["close"]

    atr_f_series = compute_atr(df, n_f)
    ATR_f = float(atr_f_series.iloc[-1])
    if np.isnan(ATR_f) or ATR_f <= 0:
        return {"state": "NEUTRAL_RANGE", "cms": 0.0, "ii": 0.0, "er": 0.0}

    P = float(close.iloc[-1])
    P_nm = float(close.iloc[-1 - n_m])

    # M_t in ATR units
    M = (P - P_nm) / ATR_f

    # ER over n_c
    P_nc = float(close.iloc[-1 - n_c])
    net = abs(P - P_nc)
    diffs = close.diff().abs().tail(n_c)
    denom = float(diffs.sum())
    ER = 0.0 if denom <= 0 else clamp(net / denom, 0.0, 1.0)

    mb_f = clamp(float(mb), -1.0, 1.0)
    ss_f = clamp(float(ss), -1.0, 1.0)

    # CMS in [-1,1]
    cms = 0.50 * mb_f + 0.30 * float(np.tanh(M / k_m)) + 0.20 * ss_f
    cms = clamp(cms, -1.0, 1.0)

    # Impulse intensity
    Align = clamp(float(bp_up) - float(bp_dn), -1.0, 1.0)
    ii = abs(cms) * (0.6 * ER + 0.4 * (1.0 - clamp(float(vrs), 0.0, 1.0))) * (0.7 * abs(Align) + 0.3)
    ii = clamp(ii, 0.0, 1.0)

    # State rules
    if cms >= 0.55 and ii >= 0.50:
        state = "STRONG_UP_IMPULSE"
    elif cms >= 0.20 and ii < 0.50:
        state = "WEAK_UP_DRIFT"
    elif abs(cms) < 0.20:
        state = "NEUTRAL_RANGE"
    elif cms <= -0.55 and ii >= 0.50:
        state = "STRONG_DOWN_IMPULSE"
    elif cms <= -0.20 and ii < 0.50:
        state = "WEAK_DOWN_DRIFT"
    else:
        # edge cases between thresholds
        state = "NEUTRAL_RANGE"

    return {"state": state, "cms": float(cms), "ii": float(ii), "er": float(ER)}
