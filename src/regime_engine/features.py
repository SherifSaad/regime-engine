# src/regime_engine/features.py

from __future__ import annotations
import numpy as np
import pandas as pd


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def compute_returns(close: pd.Series) -> pd.Series:
    return close.pct_change()


def compute_realized_vol(returns: pd.Series, period: int = 20) -> pd.Series:
    return returns.rolling(period).std() * np.sqrt(252)


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.rolling(period).mean()


def compute_drawdown(close: pd.Series) -> pd.Series:
    cumulative_max = close.cummax()
    drawdown = (close - cumulative_max) / cumulative_max
    return drawdown


def compute_gaps(close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    return (close - prev_close) / prev_close


def compute_downside_semi_vol(returns: pd.Series, period: int = 20) -> pd.Series:
    downside = returns.copy()
    downside[downside > 0] = 0
    return downside.rolling(period).std() * np.sqrt(252)


def compute_log_returns(close: pd.Series) -> pd.Series:
    return np.log(close / close.shift(1))


def realized_vol_annualized(
    close: pd.Series,
    window: int = 20,
    trading_days: int = 252,
) -> pd.Series:
    """
    Annualized realized volatility using log returns.
    Keep 252 to avoid adding another degree of freedom during validation.
    """
    r = np.log(close).diff()
    rv = r.rolling(window).std() * np.sqrt(trading_days)
    return rv


def rolling_percentile_rank(series: pd.Series, lookback: int = 756) -> pd.Series:
    """
    Rolling percentile rank in [0,1] using a trailing lookback window.
    lookback=756 ~ 3 years of trading days.
    Deterministic. No ML.
    """

    def _pct_rank(x):
        last = x[-1]
        return np.mean(x <= last)

    return series.rolling(lookback, min_periods=lookback).apply(_pct_rank, raw=True)


def high_exposure_from_vol_rank(vol_rank: float) -> float:
    """clamp(0.4 + 0.6*(1 - vol_rank), 0.4, 1.0)"""
    x = 0.4 + 0.6 * (1.0 - float(vol_rank))
    return float(np.clip(x, 0.4, 1.0))
