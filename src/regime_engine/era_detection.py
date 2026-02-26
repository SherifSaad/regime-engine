"""
Bai–Perron structural break detection on log(126-day realized volatility).

Constraints (frozen):
- ε = 1e-12 in log(RV_126 + ε)
- Breaks in MEAN of log(RV_126) only (not variance)
- Min segment length = 504 trading days
- BIC for model selection
"""
from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np
import pandas as pd

# Frozen constants
EPSILON = 1e-12
RV_WINDOW = 126
MIN_SEGMENT = 504


class EraDetectionResult(NamedTuple):
    """Result of Bai-Perron era detection."""

    break_indices: tuple[int, ...]  # 0-based indices where breaks occur (start of new segment)
    bic_by_k: dict[int, float]  # BIC for each k (number of breaks)
    log_rv: np.ndarray
    dates: pd.DatetimeIndex
    data_hash: str


def _segment_ssr(y: np.ndarray, i: int, j: int, cumsum_y: np.ndarray, cumsum_y2: np.ndarray) -> float:
    """Sum of squared residuals for segment [i, j) with constant mean. O(1) via prefix sums."""
    n = j - i
    if n <= 0:
        return 0.0
    s = cumsum_y[j] - cumsum_y[i]
    s2 = cumsum_y2[j] - cumsum_y2[i]
    mean = s / n
    return float(s2 - n * mean * mean)


def _build_segment_cost_matrix(y: np.ndarray, min_seg: int, cumsum_y: np.ndarray, cumsum_y2: np.ndarray) -> np.ndarray:
    """Precompute SSR for all segments [i,j) with j-i >= min_seg. Vectorized."""
    n = len(y)
    cost_seg = np.full((n + 1, n + 1), np.nan)
    for i in range(n - min_seg + 1):
        j_arr = np.arange(i + min_seg, n + 1, dtype=int)
        s = cumsum_y[j_arr] - cumsum_y[i]
        s2 = cumsum_y2[j_arr] - cumsum_y2[i]
        seg_n = j_arr - i
        ssr = s2 - s * s / seg_n
        cost_seg[i, i + min_seg : n + 1] = ssr
    return cost_seg


def _optimal_partition_dp(
    y: np.ndarray,
    min_seg: int,
    n_breaks: int,
) -> tuple[list[int], float]:
    """
    Find optimal partition with exactly n_breaks breaks via dynamic programming.
    Returns (break indices as start-of-segment, total SSR).
    """
    n = len(y)
    n_seg = n_breaks + 1
    if n_breaks < 0 or n_seg * min_seg > n:
        return [], float("inf")

    cumsum_y = np.concatenate([[0], np.cumsum(y)])
    cumsum_y2 = np.concatenate([[0], np.cumsum(y * y)])
    cost_seg = _build_segment_cost_matrix(y, min_seg, cumsum_y, cumsum_y2)

    INF = float("inf")
    cost = np.full((n_seg + 1, n + 1), INF)
    parent = np.full((n_seg + 1, n + 1), -1, dtype=int)

    for j in range(min_seg, n + 1):
        cost[1, j] = cost_seg[0, j]

    for s in range(2, n_seg + 1):
        for j in range(s * min_seg, n + 1):
            b_lo = (s - 1) * min_seg
            b_hi = j - min_seg + 1
            if b_hi <= b_lo:
                continue
            seg_costs = cost_seg[b_lo:b_hi, j]
            prev_costs = cost[s - 1, b_lo:b_hi]
            total = prev_costs + seg_costs
            best_idx = np.nanargmin(np.where(np.isfinite(total), total, np.inf))
            cost[s, j] = total[best_idx]
            parent[s, j] = b_lo + best_idx

    breaks = []
    j = n
    for s in range(n_seg, 1, -1):
        b = parent[s, j]
        if b < 0:
            break
        breaks.append(b)
        j = b
    breaks.reverse()
    return breaks, float(cost[n_seg, n])


def compute_log_rv(close: pd.Series, window: int = RV_WINDOW, epsilon: float = EPSILON) -> pd.Series:
    """
    126-day rolling realized volatility from log returns, then log(RV + ε).
    """
    log_ret = np.log(close / close.shift(1))
    rv = log_ret.rolling(window=window, min_periods=window).std()
    return np.log(rv + epsilon)


def detect_breaks_bai_perron(
    log_rv: np.ndarray,
    min_segment: int = MIN_SEGMENT,
) -> tuple[tuple[int, ...], dict[int, float]]:
    """
    Bai-Perron: detect breaks in MEAN of log_rv only.
    BIC for model selection. Returns (break_indices, bic_by_k).
    """
    y = np.asarray(log_rv, dtype=float)
    valid = np.isfinite(y)
    y = np.where(valid, y, np.nan)
    # Use only valid values for detection - but we need contiguous indices
    # So we work with the full series and NaN will make SSR large for segments with NaN
    # Simpler: drop leading NaN from rolling, use the valid part
    first_valid = 0
    for i in range(len(y)):
        if np.isfinite(y[i]):
            first_valid = i
            break
    last_valid = len(y) - 1
    for i in range(len(y) - 1, -1, -1):
        if np.isfinite(y[i]):
            last_valid = i
            break
    if last_valid - first_valid + 1 < 2 * min_segment:
        return (), {0: float("inf")}

    y_work = y[first_valid : last_valid + 1].copy()
    n = len(y_work)
    # Fill any remaining NaN with segment mean later - or exclude
    nan_mask = ~np.isfinite(y_work)
    if np.any(nan_mask):
        # Replace NaN with global mean for that segment - actually for SSR we need finite
        y_work[nan_mask] = np.nanmean(y_work)

    max_k = max(0, (n // min_segment) - 1)
    bic_by_k = {}
    best_breaks = ()
    best_bic = float("inf")

    for k in range(max_k + 1):
        breaks, rss = _optimal_partition_dp(y_work, min_segment, k)
        if rss == float("inf") or rss <= 0:
            bic = float("inf")
        else:
            # BIC = n*log(RSS/n) + p*log(n), p = k+1 (number of mean parameters)
            bic = n * math.log(rss / n) + (k + 1) * math.log(n)
        bic_by_k[k] = bic
        if bic < best_bic:
            best_bic = bic
            best_breaks = tuple(first_valid + b for b in breaks)

    return best_breaks, bic_by_k


def run_era_detection(
    close: pd.Series,
    min_segment: int = MIN_SEGMENT,
    data_hash: str = "",
) -> EraDetectionResult:
    """
    Full pipeline: RV_126 -> log(RV+ε) -> Bai-Perron -> break indices.
    """
    log_rv = compute_log_rv(close, window=RV_WINDOW, epsilon=EPSILON)
    arr = log_rv.values
    break_indices, bic_by_k = detect_breaks_bai_perron(arr, min_segment=min_segment)
    return EraDetectionResult(
        break_indices=break_indices,
        bic_by_k=bic_by_k,
        log_rv=arr,
        dates=close.index,
        data_hash=data_hash,
    )
