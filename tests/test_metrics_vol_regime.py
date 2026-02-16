import numpy as np
import pandas as pd

from regime_engine.metrics import compute_volatility_regime


def make_df_low_vol(n=400):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    close = np.linspace(100, 105, n)  # smooth drift
    open_ = close
    high = close * 1.001
    low = close * 0.999
    volume = np.full(n, 1_000_000)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def make_df_high_vol(n=400):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    rng = np.random.default_rng(123)
    steps = rng.normal(0, 1.5, n)  # big swings
    close = 100 + np.cumsum(steps)
    close = np.maximum(close, 1.0)

    open_ = close * (1 + rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * 1.02
    low = np.minimum(open_, close) * 0.98
    volume = np.full(n, 1_000_000)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_vrs_in_bounds_and_label_valid():
    df = make_df_low_vol()
    out = compute_volatility_regime(df, rl=0.2)
    assert 0.0 <= out["vrs"] <= 1.0
    assert out["label"] in {"CALM", "NORMAL", "ELEVATED", "STRESSED"}
    assert out["trend"] in {"RISING", "FALLING", "FLAT"}


def test_high_vol_gives_higher_vrs():
    df_low = make_df_low_vol()
    df_high = make_df_high_vol()

    out_low = compute_volatility_regime(df_low, rl=0.2)
    out_high = compute_volatility_regime(df_high, rl=0.2)

    assert out_high["vrs"] > out_low["vrs"]
