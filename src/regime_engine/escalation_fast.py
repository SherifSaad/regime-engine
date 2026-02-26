"""
Fast path for escalation v2: precomputes series once, then iterates with indexing.
Replaces O(n²) loop in cli.py with O(n*W) where W is key_levels window.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from regime_engine.features import compute_atr, compute_ema, compute_log_returns
from regime_engine.metrics import (
    clamp,
    compute_asymmetry_metric,
    compute_key_levels,
    compute_breakout_probability,
    compute_downside_shock_risk,
    compute_instability_index,
    compute_liquidity_context,
    compute_momentum_state,
    compute_structural_score,
    compute_volatility_regime,
)


def _close_for_returns(df: pd.DataFrame) -> pd.Series:
    return df["adj_close"] if "adj_close" in df.columns else df["close"]


def _precompute(df: pd.DataFrame) -> dict:
    """Precompute all series needed for metrics at each bar. O(n) once."""
    close = df["close"]
    close_ret = _close_for_returns(df)
    open_ = df["open"] if "open" in df.columns else close

    r = compute_log_returns(close_ret)
    ema_f = compute_ema(close, 20)
    ema_s = compute_ema(close, 100)
    atr_f = compute_atr(df, 20)

    sigma_f = r.rolling(20).std()
    sigma_s = r.rolling(100).std()

    return {
        "close": close,
        "close_ret": close_ret,
        "open": open_,
        "r": r,
        "ema_f": ema_f,
        "ema_s": ema_s,
        "atr_f": atr_f,
        "sigma_f": sigma_f,
        "sigma_s": sigma_s,
    }


def _market_bias_at(pc: dict, i: int, alpha: float = 0.7, beta: float = 0.3) -> float:
    emaf = pc["ema_f"].iloc[i]
    emas = pc["ema_s"].iloc[i]
    atr = pc["atr_f"].iloc[i]
    p = pc["close"].iloc[i]
    if np.isnan(atr) or atr <= 0:
        return 0.0
    T = (emaf - emas) / atr
    C = (p - emas) / atr
    mb = float(np.tanh(alpha * T + beta * C))
    return clamp(mb, -1.0, 1.0)


def _risk_level_at(
    pc: dict,
    df: pd.DataFrame,
    i: int,
    peak_window: int = 252,
    A_max: float = 3.0,
    B_max: float = 0.5,
    C1_max: float = 3.0,
    DD_max: float = 0.20,
    D_max: float = 2.0,
    w_A: float = 0.35,
    w_B: float = 0.20,
    w_C: float = 0.35,
    w_D: float = 0.10,
) -> float:
    if i < peak_window + 5:
        return 0.0

    sigma_f = float(pc["sigma_f"].iloc[i])
    sigma_s = float(pc["sigma_s"].iloc[i])
    sigma_f_prev = float(pc["sigma_f"].iloc[i - 1])
    atr_f = float(pc["atr_f"].iloc[i])
    ema_s = float(pc["ema_s"].iloc[i])
    p = float(pc["close"].iloc[i])
    close_ret = pc["close_ret"]
    open_ = pc["open"]

    if np.isnan(atr_f) or atr_f <= 0:
        return 0.0
    if np.isnan(sigma_f) or sigma_f <= 0:
        return 0.0
    if np.isnan(sigma_s) or sigma_s <= 0:
        sigma_s = 1e-12

    A_raw = sigma_f / sigma_s
    A = clamp(A_raw, 0.0, A_max) / A_max

    if np.isnan(sigma_f_prev) or sigma_f_prev <= 0:
        B = 0.0
    else:
        B_raw = (sigma_f - sigma_f_prev) / sigma_f
        B = clamp(B_raw, 0.0, B_max) / B_max

    C1_raw = (ema_s - p) / atr_f
    C1 = clamp(C1_raw, 0.0, C1_max) / C1_max

    # Match metrics: rolling(peak_window).max() uses window [i-251..i] for peak_window=252
    start = max(0, i - peak_window + 1)
    peak = float(close_ret.iloc[start : i + 1].max())
    p_ret = float(close_ret.iloc[i])
    if np.isnan(peak) or peak <= 0:
        C2 = 0.0
    else:
        DD = (peak - p_ret) / peak
        C2 = clamp(DD / DD_max, 0.0, 1.0)

    C = 0.5 * C1 + 0.5 * C2

    prev_close = float(pc["close"].iloc[i - 1])
    o = float(open_.iloc[i])
    gap_raw = abs(o - prev_close) / atr_f
    D = clamp(gap_raw, 0.0, D_max) / D_max

    rl = w_A * A + w_B * B + w_C * C + w_D * D
    return clamp(rl, 0.0, 1.0)


def compute_dsr_iix_ss_arrays_fast(
    df: pd.DataFrame,
    symbol: str,
    *,
    n_f: int = 20,
    n_s: int = 100,
    W: int = 250,
) -> tuple[list[float], list[float], list[float]]:
    """
    Compute DSR, IIX, SS arrays for bars 20..n-1 using precomputed series.
    Mathematically equivalent to the O(n²) loop but O(n*W) where W=250.
    """
    n = len(df)
    if n < 20:
        return [], [], []

    pc = _precompute(df)
    dsr_arr: list[float] = []
    iix_arr: list[float] = []
    ss_arr: list[float] = []

    for i in range(20, n):
        sub = df.iloc[: i + 1]
        mb = _market_bias_at(pc, i)
        rl = _risk_level_at(pc, df, i)

        vol_regime = compute_volatility_regime(sub, rl=rl, n_f=n_f, n_s=n_s, n_sh=10, n_lg=50)
        vrs = float(vol_regime["vrs"])

        start_kl = max(0, i - W + 1)
        kl_df = df.iloc[start_kl : i + 1]
        kl = compute_key_levels(kl_df, n_f=n_f, W=W, k=3, eta=0.35, N=3, min_strength=0.35)

        L_up = kl["resistances"][0]["price"] if kl["resistances"] else None
        L_dn = kl["supports"][0]["price"] if kl["supports"] else None

        bp_up, bp_dn = compute_breakout_probability(
            sub, mb=mb, rl=rl, n_f=n_f, atr_short_n=10, atr_long_n=50,
            level_lookback=50, L_up=L_up, L_dn=L_dn,
        )

        dsr = compute_downside_shock_risk(sub, mb=mb, rl=rl, n_f=n_f, n_s=n_s, H=60, m=2.5)

        ss = compute_structural_score(
            sub, mb=mb, rl=rl, dsr=dsr, key_levels=kl, n_f=n_f, n_s=n_s, n_c=20,
        )

        momentum = compute_momentum_state(
            sub, mb=mb, ss=ss, vrs=vrs, bp_up=bp_up, bp_dn=bp_dn,
            n_f=n_f, n_m=20, k_m=2.0, n_c=20,
        )
        er = float(momentum["er"])

        liquidity = compute_liquidity_context(sub, vrs=vrs, er=er, n_dv=20, h=5)
        lq = float(liquidity["lq"])

        iix = compute_instability_index(
            sub, rl=rl, dsr=dsr, vrs=vrs, lq=lq, er=er, n_f=n_f,
        )

        dsr_arr.append(float(dsr))
        ss_arr.append(float(ss))
        iix_arr.append(float(iix))

    return dsr_arr, iix_arr, ss_arr


def _trend_to_float(trend: str | float, rising: str, falling: str) -> float:
    """Convert string trend to numeric [-1, 1]."""
    if isinstance(trend, (int, float)):
        return float(trend)
    s = (trend or "").upper()
    if rising.upper() in s:
        return 0.5
    if falling.upper() in s:
        return -0.5
    return 0.0


def compute_state_history_batch(
    df: pd.DataFrame,
    symbol: str,
    asof_to_esc_pctl: dict[str, float | None],
    *,
    n_f: int = 20,
    n_s: int = 100,
    W: int = 250,
) -> list[tuple[str, dict]]:
    """
    Compute full market state for all bars 20..n-1 in one pass.
    Returns list of (asof, state_dict) matching compute_market_state_from_df output.
    Uses esc_pctl from asof_to_esc_pctl for bucket; no escalation recompute.
    """
    from regime_engine.classifier import classify_to_dict
    from regime_engine.escalation_buckets import compute_bucket_from_percentile
    from regime_engine.escalation_v2 import get_escalation_metadata

    n = len(df)
    if n < 20:
        return []

    pc = _precompute(df)
    close = pc["close"]
    ema_fast = pc["ema_f"]
    ema_slow = pc["ema_s"]
    r = pc["r"]
    rv = r.rolling(20).std() * np.sqrt(252)  # realized vol

    def _asof(i: int) -> str:
        if "ts_str" in df.columns:
            return str(df["ts_str"].iloc[i])
        idx = df.index[i]
        return str(idx.date()) if hasattr(idx, "date") else str(idx)[:10]

    results: list[tuple[str, dict]] = []
    for i in range(20, n):
        sub = df.iloc[: i + 1]
        asof = _asof(i)

        mb = _market_bias_at(pc, i)
        rl = _risk_level_at(pc, df, i)

        vol_regime = compute_volatility_regime(sub, rl=rl, n_f=n_f, n_s=n_s, n_sh=10, n_lg=50)
        vrs = float(vol_regime["vrs"])

        start_kl = max(0, i - W + 1)
        kl_df = df.iloc[start_kl : i + 1]
        kl = compute_key_levels(kl_df, n_f=n_f, W=W, k=3, eta=0.35, N=3, min_strength=0.35)

        L_up = kl["resistances"][0]["price"] if kl["resistances"] else None
        L_dn = kl["supports"][0]["price"] if kl["supports"] else None

        bp_up, bp_dn = compute_breakout_probability(
            sub, mb=mb, rl=rl, n_f=n_f, atr_short_n=10, atr_long_n=50,
            level_lookback=50, L_up=L_up, L_dn=L_dn,
        )

        dsr = compute_downside_shock_risk(sub, mb=mb, rl=rl, n_f=n_f, n_s=n_s, H=60, m=2.5)

        ss = compute_structural_score(
            sub, mb=mb, rl=rl, dsr=dsr, key_levels=kl, n_f=n_f, n_s=n_s, n_c=20,
        )

        momentum = compute_momentum_state(
            sub, mb=mb, ss=ss, vrs=vrs, bp_up=bp_up, bp_dn=bp_dn,
            n_f=n_f, n_m=20, k_m=2.0, n_c=20,
        )
        er = float(momentum["er"])

        liquidity = compute_liquidity_context(sub, vrs=vrs, er=er, n_dv=20, h=5)
        lq = float(liquidity["lq"])

        iix = compute_instability_index(
            sub, rl=rl, dsr=dsr, vrs=vrs, lq=lq, er=er, n_f=n_f,
        )

        asm = compute_asymmetry_metric(
            sub, bp_up=bp_up, bp_dn=bp_dn, dsr=dsr, rl=rl, mb=mb, er=er, iix=iix, H=60, gamma=1.0,
        )

        classification_metrics = {
            "MB": float(mb),
            "SS": float(ss),
            "IIX": float(iix),
            "ASM": float(asm),
            "DSR": float(dsr),
            "risk_level": float(rl),
            "BP_up": float(bp_up),
            "BP_dn": float(bp_dn),
            "VRS": float(vrs),
            "LQ": float(lq),
            "momentum": {
                "state": momentum["state"],
                "index": float(momentum["ii"]),
            },
            "vol_regime": {
                "value": float(vrs),
                "label": vol_regime["label"],
                "trend": _trend_to_float(vol_regime["trend"], "RISING", "FALLING"),
            },
            "liquidity": {
                "value": float(lq),
                "label": liquidity["label"],
                "trend": _trend_to_float(liquidity["trend"], "IMPROVING", "DETERIORATING"),
            },
        }
        classification = classify_to_dict(classification_metrics, diagnostics=False)

        pctl = asof_to_esc_pctl.get(asof)
        if pctl is not None and isinstance(pctl, (int, float)) and not np.isnan(float(pctl)):
            escalation_bucket, escalation_action, escalation_thresholds = compute_bucket_from_percentile(
                float(pctl)
            )
        else:
            escalation_bucket, escalation_action, escalation_thresholds = "NA", "NORMAL_SIZE", {}

        state = {
            "symbol": symbol.upper(),
            "asof": asof,
            "key_levels": kl,
            "vol_regime": vol_regime,
            "momentum": momentum,
            "liquidity": liquidity,
            "metrics": {
                "price": float(close.iloc[i]),
                "ema_fast": float(ema_fast.iloc[i]),
                "ema_slow": float(ema_slow.iloc[i]),
                "realized_vol": float(rv.iloc[i]) if not np.isnan(rv.iloc[i]) else 0.0,
                "market_bias": float(mb),
                "risk_level": float(rl),
                "vrs": float(vrs),
                "breakout_up": float(bp_up),
                "breakout_down": float(bp_dn),
                "downside_shock_risk": float(dsr),
                "structural_score": float(ss),
                "cms": float(momentum["cms"]),
                "ii": float(momentum["ii"]),
                "lq": float(lq),
                "instability_index": float(iix),
                "asymmetry_metric": float(asm),
            },
            "classification": classification,
            "escalation_bucket": escalation_bucket,
            "escalation_action": escalation_action,
            "escalation_bucket_thresholds": escalation_thresholds,
            "escalation_metadata": get_escalation_metadata(),
        }
        results.append((asof, state))

    return results
