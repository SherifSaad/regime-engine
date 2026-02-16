import numpy as np
import pandas as pd

from regime_engine.metrics import compute_downside_shock_risk


def make_df_with_down_shocks(n=400, shock_days=5):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    close = np.full(n, 100.0)

    # gentle drift
    for i in range(1, n):
        close[i] = close[i - 1] * 1.0005

    # inject big downside shocks in last 60 bars
    shock_idx = np.linspace(n - 60, n - 2, shock_days, dtype=int)
    for j in shock_idx:
        close[j] = close[j - 1] * 0.90  # -10% day

    open_ = close.copy()
    high = close * 1.01
    low = close * 0.99
    volume = np.full(n, 1_000_000)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def make_df_calm(n=400):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    close = np.linspace(100, 110, n)
    open_ = close
    high = close * 1.001
    low = close * 0.999
    volume = np.full(n, 1_000_000)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_dsr_in_bounds():
    df = make_df_calm()
    dsr = compute_downside_shock_risk(df, mb=0.0, rl=0.2)
    assert 0.0 <= dsr <= 1.0


def test_dsr_higher_with_shocks_and_bearish_bias():
    df_shock = make_df_with_down_shocks()
    df_calm = make_df_calm()

    dsr_shock_bear = compute_downside_shock_risk(df_shock, mb=-0.8, rl=0.4)
    dsr_calm_bull = compute_downside_shock_risk(df_calm, mb=0.8, rl=0.1)

    assert dsr_shock_bear > dsr_calm_bull
