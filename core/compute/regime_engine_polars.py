"""
Polars vectorized regime engine – fast compute for large histories.

Replaces per-bar pandas loops with vectorized Polars expressions.
Designed for: ~200k bars (crypto), 1500 earnings symbols, quick re-compute.

Phase 6 Step 1: Initial implementation with core metrics. Expand to full 11-metric
engine in later steps.
"""

from __future__ import annotations

import polars as pl


def _clip01(x: pl.Expr) -> pl.Expr:
    """Clip expression to [0, 1]."""
    return pl.when(x < 0).then(0.0).when(x > 1).then(1.0).otherwise(x)


def compute_regime_polars(df: pl.DataFrame) -> pl.DataFrame:
    """
    Vectorized regime computation. df has columns: ts, open, high, low, close, volume.

    Adds 11-metric placeholders + regime_state. All computed in one pass.
    """
    if df.is_empty() or len(df) < 50:
        return df

    close = pl.col("close")
    n_f, n_s = 20, 100

    # Ensure numeric
    df = df.with_columns([
        pl.col("open").cast(pl.Float64),
        pl.col("high").cast(pl.Float64),
        pl.col("low").cast(pl.Float64),
        pl.col("close").cast(pl.Float64),
        pl.col("volume").cast(pl.Int64),
    ])

    # 1) Returns
    returns = (close / close.shift(1) - 1)

    # 2) SMA / EMA
    sma20 = close.rolling_mean(window_size=n_f)
    sma100 = close.rolling_mean(window_size=n_s)
    ema20 = close.ewm_mean(span=n_f, adjust=False)
    ema100 = close.ewm_mean(span=n_s, adjust=False)

    # 3) Realized vol (annualized, 252 days)
    log_ret = (close / close.shift(1)).log()
    rv20 = log_ret.rolling_std(window_size=n_f) * (252 ** 0.5)
    rv100 = log_ret.rolling_std(window_size=n_s) * (252 ** 0.5)

    # 4) ATR (True Range)
    prev_close = close.shift(1)
    tr = pl.max_horizontal(
        pl.col("high") - pl.col("low"),
        (pl.col("high") - prev_close).abs(),
        (pl.col("low") - prev_close).abs(),
    )
    atr20 = tr.rolling_mean(window_size=n_f)

    # 5) Trend strength (close vs EMA, normalized)
    trend_strength = _clip01((close - ema20) / (atr20 + 1e-12) * 0.2 + 0.5)

    # 6) Vol regime (relative vol: fast/slow)
    vol_regime = _clip01((rv20 / (rv100 + 1e-12)).clip(0, 3) / 3)

    # 7) Drawdown pressure (from rolling max)
    rolling_max = close.rolling_max(window_size=252)
    drawdown = (rolling_max - close) / (rolling_max + 1e-12)
    drawdown_pressure = _clip01(drawdown / 0.20)

    # 8) Downside shock (negative returns, rolling)
    downside_ret = pl.when(returns < 0).then(returns).otherwise(0.0)
    downside_shock = _clip01((-downside_ret.rolling_mean(window_size=20) * 10).clip(0, 1))

    # 9) Asymmetry / skew (simplified: negative vs positive return ratio)
    neg_vol = pl.when(returns < 0).then(returns).otherwise(0.0).rolling_std(window_size=20)
    pos_vol = pl.when(returns > 0).then(returns).otherwise(0.0).rolling_std(window_size=20)
    asymmetry = _clip01((neg_vol / (pos_vol + 1e-12)).clip(0, 2) / 2)

    # 10) Momentum state (EMA slope proxy)
    ema_slope = (ema20 - ema20.shift(5)) / (atr20 + 1e-12)
    momentum_state = _clip01(ema_slope * 2 + 0.5)

    # 11) Structural score (efficiency ratio proxy: net move / total move)
    net_move = (close - close.shift(20)).abs()
    total_move = (close - close.shift(1)).abs().rolling_sum(window_size=20)
    er = net_move / (total_move + 1e-12)
    structural_score = _clip01(er)

    # 12) Liquidity (volume relative to rolling mean)
    vol_ma = pl.col("volume").rolling_mean(window_size=20)
    liquidity = _clip01(pl.col("volume") / (vol_ma + 1))

    # 13) Gap risk (|open - prev_close| / ATR)
    gap = (pl.col("open") - prev_close).abs() / (atr20 + 1e-12)
    gap_risk = _clip01(gap.clip(0, 2) / 2)

    # 14) Key-level pressure (placeholder: use drawdown as proxy)
    key_level_pressure = drawdown_pressure

    # 15) Breadth proxy (placeholder: use trend strength)
    breadth_proxy = trend_strength

    # Regime state: simple trend classification
    regime_state = (
        pl.when(ema20 > ema100)
        .then(pl.lit("TRENDING_BULL"))
        .when(ema20 < ema100)
        .then(pl.lit("TRENDING_BEAR"))
        .otherwise(pl.lit("TRANSITION"))
    )

    df = df.with_columns([
        returns.alias("returns"),
        sma20.alias("sma20"),
        sma100.alias("sma100"),
        ema20.alias("ema20"),
        ema100.alias("ema100"),
        rv20.alias("rv20"),
        atr20.alias("atr20"),
        trend_strength.alias("trend_strength"),
        vol_regime.alias("vol_regime"),
        drawdown_pressure.alias("drawdown_pressure"),
        downside_shock.alias("downside_shock"),
        asymmetry.alias("asymmetry"),
        momentum_state.alias("momentum_state"),
        structural_score.alias("structural_score"),
        liquidity.alias("liquidity"),
        gap_risk.alias("gap_risk"),
        key_level_pressure.alias("key_level_pressure"),
        breadth_proxy.alias("breadth_proxy"),
        regime_state.alias("regime_state"),
    ])

    return df
