"""
Standard V2.1: Institutional math package.
Canonical percentile (midrank), confidence ramp, early-era shrinkage.
Timeframe-consistent stability targets.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class TimeframePolicy:
    """
    Institutional policy: time-based stability targets expressed in bars.
    Targets correspond to "about 1 trading year" for confidence to reach 1.0,
    then convert to bars. Do not leave 252 hardcoded for every timeframe.
    """
    tf: str

    def bars_per_trading_year(self) -> int:
        tf = self.tf.lower().strip()

        # --- Daily-native anchor: 252 trading days/year ---
        if tf in ("1d", "d", "day", "daily", "1day"):
            return 252

        # --- Weekly: ~52 bars/year ---
        if tf in ("1w", "w", "week", "weekly", "1week"):
            return 52

        # --- Intraday approximations (equities-like schedule) ---
        # 6.5 trading hours/day => 390 minutes/day.
        if tf in ("15min", "15m"):
            bars_per_day = 390 // 15  # 26
            return 252 * bars_per_day  # 6552
        if tf in ("1h", "60min", "60m"):
            bars_per_day = 6  # 6.5h rounded down
            return 252 * bars_per_day  # 1512
        if tf in ("4h", "240min", "240m"):
            bars_per_day = 2  # roughly 2 bars/day
            return 252 * bars_per_day  # 504

        # --- Fallback: treat unknown as daily ---
        return 252

    def percentile_min_bars(self) -> int:
        """
        Minimum bars before we allow ANY percentile-based decision to be meaningful.
        Institutional stance: do not bucket with N < ~quarter-year of bars.
        """
        target = self.bars_per_trading_year()
        return max(60, int(round(target * 0.25)))


def midrank_percentile_from_hist(hist: np.ndarray, x: float) -> float:
    """
    Canonical percentile (plotting position):
    midrank / N   where midrank = count_less + (count_equal + 1)/2

    Properties:
    - tie-safe (average rank)
    - never hits exactly 0 or 1 (good for stability)
    """
    count_less = float(np.sum(hist < x))
    count_equal = float(np.sum(hist == x))
    rank = count_less + (count_equal + 1.0) / 2.0
    return float(rank / len(hist))


def confidence_ramp(n: int, target_bars: int) -> float:
    """
    Institutional confidence scaling:
    conf = min(1, n / target_bars)

    This measures "how much history exists" in the current context.
    """
    if target_bars <= 0:
        return 1.0
    return float(min(1.0, n / float(target_bars)))


def shrink_percentile_toward_neutral(p: float, conf: float) -> float:
    """
    Institutional early-history correction:
    p_adj = 0.5 + (p - 0.5) * conf

    - If conf=0 -> p_adj=0.5 (neutral)
    - If conf=1 -> p_adj=p
    """
    return float(0.5 + (p - 0.5) * conf)
