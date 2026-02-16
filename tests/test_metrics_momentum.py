import numpy as np
import pandas as pd

from regime_engine.metrics import compute_momentum_state


def make_df_up(n=400):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    close = np.linspace(100, 150, n)
    open_ = close
    high = close * 1.01
    low = close * 0.99
    volume = np.full(n, 1_000_000)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def make_df_down(n=400):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    close = np.linspace(150, 100, n)
    open_ = close
    high = close * 1.01
    low = close * 0.99
    volume = np.full(n, 1_000_000)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_momentum_bounds_and_state_valid():
    df = make_df_up()
    out = compute_momentum_state(df, mb=0.5, ss=0.5, vrs=0.4, bp_up=0.3, bp_dn=0.2)
    assert -1.0 <= out["cms"] <= 1.0
    assert 0.0 <= out["ii"] <= 1.0
    assert 0.0 <= out["er"] <= 1.0
    assert out["state"] in {
        "STRONG_UP_IMPULSE",
        "WEAK_UP_DRIFT",
        "NEUTRAL_RANGE",
        "WEAK_DOWN_DRIFT",
        "STRONG_DOWN_IMPULSE",
    }


def test_bearish_inputs_tend_to_negative_cms():
    df = make_df_down()
    out = compute_momentum_state(df, mb=-0.8, ss=-0.6, vrs=0.4, bp_up=0.1, bp_dn=0.3)
    assert out["cms"] < 0
