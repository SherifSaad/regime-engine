"""
Era-conditioned production percentile (esc_pctl_era_adj).
Same logic as compute_asset_full: TimeframePolicy + min bars + confidence shrinkage.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from regime_engine.era_utils import get_era_bounds_for_symbol
from regime_engine.escalation_v2 import expanding_percentile_transform
from regime_engine.standard_v2_1 import TimeframePolicy


def compute_esc_pctl_era_adj(
    esc_series: pd.Series,
    df: pd.DataFrame,
    symbol: str,
    tf: str,
) -> pd.Series:
    """
    Compute era-conditioned production percentile with confidence shrinkage.
    Returns Series aligned to df.index. Same logic as compute_asset_full.
    """
    adj, _, _ = _compute_era_series(esc_series, df, symbol, tf)
    return adj


def compute_esc_pctl_era_all(
    esc_series: pd.Series,
    df: pd.DataFrame,
    symbol: str,
    tf: str,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (esc_pctl_era_adj, esc_pctl_era, esc_pctl_era_confidence)."""
    return _compute_era_series(esc_series, df, symbol, tf)


def _compute_era_series(
    esc_series: pd.Series,
    df: pd.DataFrame,
    symbol: str,
    tf: str,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    tf_policy = TimeframePolicy(tf)
    conf_target = tf_policy.bars_per_trading_year()
    pctl_min_bars = tf_policy.percentile_min_bars()

    esc_pctl_era_adj = pd.Series(np.full(len(df), np.nan, dtype=float), index=df.index)
    esc_pctl_era = pd.Series(np.full(len(df), np.nan, dtype=float), index=df.index)
    esc_pctl_era_confidence = pd.Series(np.full(len(df), np.nan, dtype=float), index=df.index)
    era_bounds = get_era_bounds_for_symbol(symbol)

    for start_s, end_s in era_bounds:
        start = pd.to_datetime(start_s) if start_s else None
        end = pd.to_datetime(end_s) if end_s else None
        mask = pd.Series(True, index=df.index)
        if start is not None:
            mask &= df.index >= start
        if end is not None:
            mask &= df.index < end
        if mask.sum() == 0:
            continue
        sub = esc_series.loc[mask]
        sub_vals = sub.values.astype(float)
        p = expanding_percentile_transform(
            pd.Series(sub_vals, index=sub.index), min_bars=pctl_min_bars
        ).values
        bars_in_era = np.arange(len(sub), dtype=float) + 1.0
        conf = np.minimum(1.0, bars_in_era / float(conf_target))
        p_adj = np.full_like(p, np.nan, dtype=float)
        valid = ~np.isnan(p)
        p_adj[valid] = 0.5 + (p[valid] - 0.5) * conf[valid]
        esc_pctl_era_adj.loc[mask] = p_adj
        esc_pctl_era.loc[mask] = p
        esc_pctl_era_confidence.loc[mask] = conf

    return esc_pctl_era_adj, esc_pctl_era, esc_pctl_era_confidence
