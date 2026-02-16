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
