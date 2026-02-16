import pandas as pd
import numpy as np

from regime_engine.metrics import compute_market_bias, compute_risk_level


def make_df_trending_up(n=300):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    close = np.linspace(100, 200, n)
    open_ = close * (1 + 0.001)  # tiny gap
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    volume = np.full(n, 1_000_000)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def make_df_trending_down(n=300):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    close = np.linspace(200, 100, n)
    open_ = close * (1 - 0.001)
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    volume = np.full(n, 1_000_000)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_market_bias_positive_for_uptrend():
    df = make_df_trending_up()
    mb = compute_market_bias(df, n_f=20, n_s=100)
    assert mb > 0.2  # should be bullish


def test_market_bias_negative_for_downtrend():
    df = make_df_trending_down()
    mb = compute_market_bias(df, n_f=20, n_s=100)
    assert mb < -0.2  # should be bearish


def test_risk_level_in_bounds():
    df = make_df_trending_up()
    rl = compute_risk_level(df, n_f=20, n_s=100, peak_window=252)
    assert 0.0 <= rl <= 1.0
