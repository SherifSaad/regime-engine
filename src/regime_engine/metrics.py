# src/regime_engine/metrics.py

from __future__ import annotations
import numpy as np
import pandas as pd
from regime_engine.features import compute_ema


def clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


def compute_market_bias(close: pd.Series, fast: int = 20, slow: int = 100) -> float:
    """
    Market Bias in [-1, +1].

    Deterministic placeholder logic:
    - Trend direction: sign(EMA_fast - EMA_slow)
    - Trend strength: normalized distance of price from EMA_slow

    This is intentionally simple and robust; you will replace it with your official formula later.
    """
    if len(close) < slow + 5:
        return 0.0

    ema_fast = compute_ema(close, fast)
    ema_slow = compute_ema(close, slow)

    # Direction component in [-1, +1]
    direction = np.sign(ema_fast.iloc[-1] - ema_slow.iloc[-1])

    # Strength component: normalize distance to avoid ridiculous values
    price = close.iloc[-1]
    base = ema_slow.iloc[-1]
    if base == 0 or np.isnan(base):
        return 0.0

    dist = (price - base) / base  # e.g., 0.02 = +2%
    strength = clamp(dist * 10.0, -1.0, 1.0)  # scale: 10x then clamp

    bias = clamp(0.6 * float(direction) + 0.4 * float(strength), -1.0, 1.0)
    return bias
